"""A Flask app that shows OSM tasks done by a user on a specific day."""
import datetime
import xml.etree.ElementTree as ET
from collections import defaultdict
import requests
from flask import Flask, render_template

app = Flask(__name__)


def get_etree_from_url(url: str) -> ET.Element:
    """Fetches XML content from a URL and returns the root Element."""
    response = requests.get(url, timeout=120)
    response.raise_for_status()  # Raise an error for bad responses
    return ET.fromstring(response.content)


def get_changes(user: str, date: str):
    """Return a {app: num of changes} dictionary and the changesets amount."""
    changes: defaultdict[str, int] = defaultdict(int)
    changesets = 0
    datetime_date = datetime.date.fromisoformat(date)
    start_time = f"{datetime_date}T00:00:00Z"
    end_time = f"{datetime_date + datetime.timedelta(days=1)}T00:00:00Z"

    changeset_url = ("https://api.openstreetmap.org/api/0.6/changesets?"
                     f"display_name={user}&time={start_time},{end_time}")
    root = get_etree_from_url(url=changeset_url)

    for cs in root.findall("changeset"):
        cs_id = cs.attrib["id"]

        tags = {tag.attrib["k"]: tag.attrib["v"] for tag in cs.findall("tag")}
        editor = tags.get("created_by", "")
        changesets += 1

        diff_url = ("https://api.openstreetmap.org/api/0.6/changeset/"
                    f"{cs_id}/download")
        try:
            root = get_etree_from_url(url=diff_url)
        except requests.HTTPError:
            continue

        for action in root:
            changes[editor] += len(action)
    return changes, changesets


@app.route('/')
@app.route('/<user>')
@app.route('/<user>/<date>')
def whatdidyoudo(user: str | None = None, date: str | None = None) -> str:
    """shows OSM tasks done by a user on a specific day."""
    changes: defaultdict[str, int] = defaultdict(int)
    changesets = 0
    error = ""
    if user and date:
        try:
            changes, changesets = get_changes(user, date)
        except requests.HTTPError:
            error = f"Can't determine changes for user {user} on {date}."

    return render_template('form.html', user=user, date=date, changes=changes,
                           changesets=changesets, error=error)
