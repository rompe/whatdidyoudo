"""A Flask app that shows OSM tasks done by a user on a specific day."""
import datetime
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
import requests

from flask import Flask, render_template
from flask_caching import Cache
from flask_limiter import Limiter, RateLimitExceeded
from flask_limiter.util import get_remote_address

__version__ = "0.2.1"

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


def get_changes(user: str, date: str):
    """Return a ({app: Changes} dictionary, [changeset_ids]) tuple."""
    changes: defaultdict[str, Changes] = defaultdict(Changes)
    changeset_ids: list[str] = []
    datetime_date = datetime.date.fromisoformat(date)
    start_time = f"{datetime_date}T00:00:00Z"
    end_time = f"{datetime_date + datetime.timedelta(days=1)}T00:00:00Z"

    changeset_url = ("https://api.openstreetmap.org/api/0.6/changesets?"
                     f"display_name={user}&time={start_time},{end_time}")
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
@app.route('/<user>/<date>')
def whatdidyoudo(user: str | None = None, date: str | None = None) -> str:
    """shows OSM tasks done by a user on a specific day."""
    changes: defaultdict[str, defaultdict[str, Changes]] = \
        defaultdict(lambda: defaultdict(Changes))
    changesets: dict[str, int] = {}
    errors: list[str] = []
    today = datetime.date.today().isoformat()
    if not date:
        date = today

    changeset_ids: list[str] = []
    for name in [item.strip() for item in (user or "").split(",")
                 if item.strip()]:
        cache_key = f"changes_{name}_{date}"
        cur_data = cache.get(cache_key)  # type: ignore
        if not cur_data:
            try:
                with limiter.limit("10 per minute"):
                    cur_data = get_changes(name, date)
                if date != today:
                    cache.set(cache_key, cur_data)  # type: ignore
            except requests.HTTPError:
                errors.append(
                    f"Can't determine changes for user {name} on {date}.")
            except RateLimitExceeded as msg:
                errors.append("Rate limit exceeded while processing user "
                              f"{name}: {msg}")
        if cur_data:
            cur_changes, cur_ids = cur_data
            changes[name] = cur_changes
            changeset_ids.extend(cur_ids)

    return render_template('form.html', user=user, date=date, changes=changes,
                           changesets=changesets, errors=errors,
                           version=__version__, changeset_ids=changeset_ids)


def main():
    """Run in debug mode."""
    app.run(host="0.0.0.0", debug=True)


if __name__ == "__main__":
    main()
