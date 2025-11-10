"""A Flask app that shows OSM tasks done by a user on a specific day."""
import datetime
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
import requests

from flask import Flask, render_template, request
from flask_caching import Cache
from flask_limiter import Limiter, RateLimitExceeded
from flask_limiter.util import get_remote_address

from whatdidyoudo import __version__

app = Flask(__name__)
cache = Cache(app, config={"CACHE_TYPE": "SimpleCache",
                           "CACHE_DEFAULT_TIMEOUT": 60 * 60 * 24 * 7})
limiter = Limiter(app=app, key_func=get_remote_address)


@dataclass
class Changes:
    """Represent changes made by a user."""
    changes: int = 0
    changesets: int = 0


def get_etree_from_url(url: str) -> ET.Element:
    """Fetches XML content from a URL and returns the root Element."""
    response = requests.get(url, timeout=120)
    response.raise_for_status()  # Raise an error for bad responses
    return ET.fromstring(response.content)


def get_changes(user: str, start_date: str, end_date: str | None = None,
                start_time: str = "00:00", end_time: str = "23:59"):
    """Return a ({app: Changes}, [changeset_ids]) tuple for a date/time range.

    start_date, end_date are ISO date strings (YYYY-MM-DD). start_time and
    end_time are HH:MM strings. The function builds ISO datetimes for the OSM
    API (UTC, appended with Z).
    """
    changes: defaultdict[str, Changes] = defaultdict(Changes)
    changeset_ids: list[str] = []
    # Ensure end_date defaults to start_date when not provided
    end_date = end_date or start_date
    # Build ISO datetime strings expected by the OSM API
    # e.g. 2025-10-24T00:00:00Z
    start_time_iso = f"{start_date}T{start_time}:00Z"
    end_time_iso = f"{end_date}T{end_time}:00Z"

    changeset_url = ("https://api.openstreetmap.org/api/0.6/changesets?"
                     f"display_name={user}&"
                     f"time={start_time_iso},{end_time_iso}")
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
@app.route('/<user>/')
@app.route('/<user>')
@app.route('/<user>/<start_date>/')
@app.route('/<user>/<start_date>')
@app.route('/<user>/<start_date>/<end_date>')
def whatdidyoudo(user: str | None = None, start_date: str | None = None,
                 end_date: str | None = None) -> str:
    """
    Show OSM tasks done by a user within a date/time range.

    Expert mode allows finer-grained start/end times via query params:
    expert=1, start_time=HH:MM, end_time=HH:MM
    """
    changes: defaultdict[str, defaultdict[str, Changes]] = \
        defaultdict(lambda: defaultdict(Changes))
    changesets: dict[str, int] = {}
    errors: list[str] = []
    # Read expert mode and time params from query string
    expert = request.args.get('expert', '0') in ('1', 'true', 'True')
    start_time = request.args.get('start_time', '00:00')
    end_time = request.args.get('end_time', '23:59')

    today = datetime.date.today().isoformat()
    date_str = (f"between {start_date} {start_time} and {end_date} {end_time}"
                if end_date or expert else f"on {start_date or today}")

    changeset_ids: list[str] = []
    for name in [item.strip() for item in (user or "").split(",")
                 if item.strip()]:
        cache_key = (f"changes_{name}_{start_date}_{end_date}_"
                     f"{start_time}_{end_time}")
        cur_data = cache.get(cache_key)  # type: ignore
        if not cur_data:
            try:
                with limiter.limit("10 per minute"):
                    cur_data = get_changes(user=name,
                                           start_date=start_date or today,
                                           end_date=end_date,
                                           start_time=start_time,
                                           end_time=end_time)
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

    return render_template('form.html', user=user, start_date=start_date,
                           end_date=end_date, start_time=start_time,
                           end_time=end_time, expert=expert,
                           changes=changes, changesets=changesets,
                           errors=errors, date_str=date_str,
                           version=__version__, changeset_ids=changeset_ids)


def main():
    """Run in debug mode."""
    app.run(host="0.0.0.0", debug=True)


if __name__ == "__main__":
    main()
