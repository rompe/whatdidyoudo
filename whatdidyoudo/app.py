"""A Flask app that shows OSM tasks done by a user on a specific day."""
import datetime
import logging
import pathlib
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from typing import Mapping
import requests

from flask import Flask, render_template
from flask_caching import Cache
from flask_limiter import Limiter, RateLimitExceeded
from flask_limiter.util import get_remote_address

from whatdidyoudo import __version__

max_changesets_osm = 100  # OSM API limit
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


def get_etree_from_url(url: str, cache_result: bool = False) -> ET.Element:
    """Fetches XML content from a URL and returns the root Element."""
    result = cache.get(url)  # type: ignore
    if not result:
        response = requests.get(url, timeout=120)
        response.raise_for_status()  # Raise an error for bad responses
        result = response.content
        if cache_result:
            cache.set(url, result)  # type: ignore
        else:
            logger.debug("Not caching result for URL: %s", url)
    return ET.fromstring(result)


def get_changesets(user: str, start_date: str, end_date: str,
                   recursion: int = 0) -> tuple[list[ET.Element], str]:
    """
    Return ([changesets], message) for a date/time range.

    start_date, end_date are ISO date strings (YYYY-MM-DDThh:mm).
    This function recurses if the OSM API limit is reached.
    """
    message = ''
    end_timestamp = datetime.datetime.strptime(end_date, "%Y-%m-%dT%H:%M")

    # Build ISO datetime strings expected by the OSM API
    # e.g. 2025-10-24T00:00:00Z
    changeset_url = ("https://api.openstreetmap.org/api/0.6/changesets?"
                     f"display_name={user}&"
                     f"time={start_date}:00Z,"
                     f"{end_date}:00Z")
    logger.debug("Fetching changesets from URL: %s", changeset_url)
    # Don't cache result if today is included in the range
    cache_result = end_timestamp >= datetime.datetime.now()
    root = get_etree_from_url(url=changeset_url, cache_result=cache_result)
    changesets = root.findall("changeset")
    if len(changesets) >= max_changesets_osm:
        if recursion >= 50:
            message = ("Note: Maximum recursion depth reached; "
                       "results may be incomplete.")
        else:
            # OSM API limit reached, set end_date to last changeset's
            # created_at minus one second and repeat
            created_at = changesets[-1].attrib["created_at"]
            created_timestamp = datetime.datetime.strptime(
                created_at, "%Y-%m-%dT%H:%M:%SZ")
            new_end = created_timestamp - datetime.timedelta(seconds=1)
            new_end_date = new_end.strftime("%Y-%m-%dT%H:%M")
            new_changesets, message = get_changesets(user=user,
                                                     start_date=start_date,
                                                     end_date=new_end_date,
                                                     recursion=recursion + 1)
            changesets += new_changesets
    return changesets, message


def get_changes(user: str, start_date: str,
                end_date: str) -> tuple[dict[str, Changes], list[str], str]:
    """
    Return ({app: Changes}, [changeset_ids], message) for a date/time range.

    start_date, end_date are ISO date strings (YYYY-MM-DDThh:mm).
    """
    # Ensure end_date defaults to start_date when not provided
    end_date = end_date or start_date
    if 'T' not in start_date:
        start_date += 'T00:00'
    if 'T' not in end_date:
        start_date += 'T23:59'

    changesets, message = get_changesets(user=user, start_date=start_date,
                                         end_date=end_date)

    changes: defaultdict[str, Changes] = defaultdict(Changes)
    changeset_ids: list[str] = []
    for cs in changesets:
        cs_id = cs.attrib["id"]
        changeset_ids.append(cs_id)

        # Don't cache changesets that are still open
        cache_result = "closed_at" in cs.attrib

        tags = {tag.attrib["k"]: tag.attrib["v"]
                for tag in cs.findall("tag")}
        editor = tags.get("created_by", "")
        changes[editor].changesets += 1

        diff_url = ("https://api.openstreetmap.org/api/0.6/changeset/"
                    f"{cs_id}/download")
        logger.debug("Fetching changeset diff from URL: %s", diff_url)
        try:
            root = get_etree_from_url(url=diff_url, cache_result=cache_result)
            for action in root:
                changes[editor].changes += len(action)
        except requests.HTTPError:
            continue

    return changes, changeset_ids, message


def get_changes_for_all_users(
        users: list[str], start_date: str,
        end_date: str) -> tuple[Mapping[str, Mapping[str, Changes]],
                                list[str], list[str]]:
    """
    Return {user: {app: Changes}} for a date/time range.

    start_date, end_date are ISO date strings (YYYY-MM-DDThh:mm).
    """
    changes: defaultdict[str, defaultdict[str, Changes]] = \
        defaultdict(lambda: defaultdict(Changes))
    changeset_ids: list[str] = []
    errors: list[str] = []
    for name in users:
        try:
            user_changes, user_changesets, message = get_changes(
                user=name, start_date=start_date, end_date=end_date)
            changes[name] = user_changes  # type: ignore
            changeset_ids.extend(user_changesets)
            if message:
                errors.append(message)
        except requests.HTTPError:
            errors.append(f"Can't determine changes for user {name} between "
                          f"{start_date} and {end_date}.")
    return changes, changeset_ids, errors


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
    """
    Show OSM tasks done by a user within a date/time range.

    "start_date", "end_date" are ISO date strings
    (YYYY-MM-DD or YYYY-MM-DDThh:mm).
    "start_date" defaults to today when not provided.
    "end_date" defaults to "start_date" when not provided.
    """
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

    logger.debug("getting changes for %s between %s and %s",
                 user, start_date, end_date)

    changeset_ids: list[str] = []
    users = [item.strip() for item in (user or "").split(",") if item.strip()]
    changes: Mapping[str, Mapping[str, Changes]] = {}
    try:
        with limiter.limit("10 per minute"):
            changes, changeset_ids, errors = get_changes_for_all_users(
                users=users, start_date=start_date, end_date=end_date)
    except RateLimitExceeded as msg:
        errors.append(f"Rate limit exceeded while processing {user}: {msg}")

    return render_template('result.html', user=user, start_date=start_date,
                           end_date=end_date, expert=expert,
                           changes=changes,
                           errors=errors, date_str=date_str,
                           version=__version__, changeset_ids=changeset_ids,
                           static_pages=get_static_pages())
