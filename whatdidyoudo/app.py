"""A Flask app that shows OSM tasks done by a user on a specific day."""
import datetime
import logging
import pathlib
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
import requests

from flask import Flask, render_template
from flask_caching import Cache
from flask_limiter import Limiter, RateLimitExceeded
from flask_limiter.util import get_remote_address

from whatdidyoudo import __version__

static_dir = '/var/www/whatdidyoudo'  # Where your impressum.html snippet is
cache_timeout = 60 * 60 * 24 * 7  # 7 days
app = Flask(__name__)
cache = Cache(app, config={"CACHE_TYPE": "SimpleCache",
                           "CACHE_DEFAULT_TIMEOUT": cache_timeout})
limiter = Limiter(app=app, key_func=get_remote_address)
logger = logging.getLogger(__name__)


@dataclass
class Changes:
    """Represent changes made by a user."""
    changes: int = 0
    changesets: int = 0


def get_static_pages() -> list[str]:
    """Return a list of available static pages."""
    return [entry.stem for entry in pathlib.Path(static_dir).glob('*.html')]


def get_etree_from_url(url: str) -> ET.Element:
    """Fetches XML content from a URL and returns the root Element."""
    response = requests.get(url, timeout=120)
    response.raise_for_status()  # Raise an error for bad responses
    return ET.fromstring(response.content)


def get_changes(user: str, start_date: str, end_date: str | None = None):
    """Return a ({app: Changes}, [changeset_ids]) tuple for a date/time range.

    start_date, end_date are ISO date strings (YYYY-MM-DD or YYYY-MM-DDThh:mm).
    The function builds ISO datetimes for the OSM API (UTC, appended with Z).
    """
    # Ensure end_date defaults to start_date when not provided
    end_date = end_date or start_date
    if 'T' not in start_date:
        start_date += 'T00:00'
    if 'T' not in end_date:
        start_date += 'T23:59'
    changes: defaultdict[str, Changes] = defaultdict(Changes)
    changeset_ids: list[str] = []
    # Build ISO datetime strings expected by the OSM API
    # e.g. 2025-10-24T00:00:00Z
    changeset_url = ("https://api.openstreetmap.org/api/0.6/changesets?"
                     f"display_name={user}&"
                     f"time={start_date}:00Z,"
                     f"{end_date}:00Z")
    root = get_etree_from_url(url=changeset_url)

    for cs in root.findall("changeset"):
        cs_id = cs.attrib["id"]
        changeset_ids.append(cs_id)

        tags = {tag.attrib["k"]: tag.attrib["v"] for tag in cs.findall("tag")}
        editor = tags.get("created_by", "")
        changes[editor].changesets += 1

        diff_url = ("https://api.openstreetmap.org/api/0.6/changeset/"
                    f"{cs_id}/download")
        try:
            root = get_etree_from_url(url=diff_url)
        except requests.HTTPError:
            continue

        for action in root:
            changes[editor].changes += len(action)
    return changes, changeset_ids


@app.route('/')
def index_page() -> str:
    """Render the index page."""
    return render_template('index.html', version=__version__,
                           static_pages=get_static_pages())


@app.route('/-/<page>')
def static_page(page: str) -> str:
    """Render a static page using content from /var/www/whatdidyoudo."""
    content_file = pathlib.Path(static_dir) / f'{page}.html'
    if content_file.is_file():
        content = content_file.read_text(encoding='utf-8')
    else:
        content = ("<h1>Page not found</h1>"
                   "<p>The requested page does not exist.</p>")
    return render_template('static_page.html', content=content,
                           version=__version__,
                           static_pages=get_static_pages())


@app.route('/<user>/')
@app.route('/<user>')
@app.route('/<user>/<start_date>/')
@app.route('/<user>/<start_date>')
@app.route('/<user>/<start_date>/<end_date>')
def whatdidyoudo(user: str | None = None, start_date: str | None = None,
                 end_date: str | None = None) -> str:
    """Show OSM tasks done by a user within a date/time range."""
    changes: defaultdict[str, defaultdict[str, Changes]] = \
        defaultdict(lambda: defaultdict(Changes))
    changesets: dict[str, int] = {}
    errors: list[str] = []
    today = datetime.date.today().isoformat()
    date_str = (f"between {start_date} and {end_date}"
                if end_date else f"on {start_date or today}")

    expert = bool(end_date)  # if end_date was given, expert mode is active
    start_date = start_date or today
    end_date = end_date or start_date
    if 'T' not in start_date:
        start_date += 'T00:00'
    if 'T' not in end_date:
        end_date += 'T23:59'

    logger.warning("getting changes for %s between %s and %s",
                   user, start_date, end_date)

    changeset_ids: list[str] = []
    for name in [item.strip() for item in (user or "").split(",")
                 if item.strip()]:
        cache_key = f"changes_{name}_{start_date}_{end_date}"
        cur_data = cache.get(cache_key)  # type: ignore
        if not cur_data:
            try:
                with limiter.limit("10 per minute"):
                    cur_data = get_changes(user=name,
                                           start_date=start_date or today,
                                           end_date=end_date)
                # Only cache results when the range does not include today
                if ((start_date and start_date != today) or
                        (end_date and end_date != today)):
                    cache.set(cache_key, cur_data)  # type: ignore
            except requests.HTTPError:
                errors.append(
                    f"Can't determine changes for user {name} {date_str}.")
            except RateLimitExceeded as msg:
                errors.append("Rate limit exceeded while processing user "
                              f"{name}: {msg}")
        if cur_data:
            cur_changes, cur_ids = cur_data
            changes[name] = cur_changes
            changeset_ids.extend(cur_ids)

    return render_template('result.html', user=user, start_date=start_date,
                           end_date=end_date, expert=expert,
                           changes=changes, changesets=changesets,
                           errors=errors, date_str=date_str,
                           version=__version__, changeset_ids=changeset_ids,
                           static_pages=get_static_pages())
