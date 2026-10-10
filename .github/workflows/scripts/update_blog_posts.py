#!/usr/bin/env python3
"""Update the blog-post list between the README markers from RSS/Atom feeds."""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
import sys
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


FEEDS = (
    "https://dzlab.github.io/feed.xml",
    "https://dzlab.github.io/notebooks/feed.xml",
    "https://dzlab.github.io/dltips/feed.xml",
)
START_MARKER = "<!-- BLOG-POST-LIST:START -->"
END_MARKER = "<!-- BLOG-POST-LIST:END -->"
POST_LIMIT = 5


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def child_text(element, *names):
    wanted = {name.lower() for name in names}
    for child in element:
        if local_name(child.tag).lower() in wanted and child.text:
            return child.text.strip()
    return ""


def post_link(element):
    for child in element:
        if local_name(child.tag).lower() != "link":
            continue
        href = child.attrib.get("href")
        if href and child.attrib.get("rel", "alternate") == "alternate":
            return href.strip()
        if child.text:
            return child.text.strip()
    return ""


def parse_date(value):
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def read_feed(url):
    request = Request(url, headers={"User-Agent": "dzlab-readme-blog-updater/1.0"})
    with urlopen(request, timeout=30) as response:
        root = ET.fromstring(response.read())

    posts = []
    for element in root.iter():
        if local_name(element.tag).lower() not in {"item", "entry"}:
            continue
        title = child_text(element, "title")
        link = post_link(element)
        if not title or not link:
            continue
        published = child_text(element, "pubDate", "published", "updated", "date")
        posts.append((parse_date(published), title, link))
    return posts


def update_readme(path):
    readme = path.read_text(encoding="utf-8")
    if readme.count(START_MARKER) != 1 or readme.count(END_MARKER) != 1:
        raise ValueError("README must contain exactly one start and end marker")
    start = readme.index(START_MARKER) + len(START_MARKER)
    end = readme.index(END_MARKER)
    if start > end:
        raise ValueError("README blog-post markers are out of order")

    posts = []
    for feed in FEEDS:
        posts.extend(read_feed(feed))
    if not posts:
        raise ValueError("RSS/Atom feeds did not contain any blog posts")

    unique_posts = {}
    for published, title, link in posts:
        unique_posts.setdefault(link, (published, title, link))
    latest = sorted(unique_posts.values(), key=lambda post: post[0], reverse=True)
    lines = []
    for _, title, link in latest[:POST_LIMIT]:
        escaped_title = title.replace("\\", "\\\\").replace("]", "\\]")
        lines.append(f"- [{escaped_title}]({link})")
    replacement = "\n" + "\n".join(lines) + "\n"
    path.write_text(readme[:start] + replacement + readme[end:], encoding="utf-8")


if __name__ == "__main__":
    readme_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("README.md")
    update_readme(readme_path)
