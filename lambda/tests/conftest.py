"""Shared fixtures and Hypothesis strategies for aws-news-telegram-notifier tests."""
import sys
import os

# 'lambda' is a Python reserved keyword so it cannot be used in a normal import
# statement. We add the lambda/ directory itself to sys.path so that modules
# inside it (models, handler, …) can be imported by their bare names.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from hypothesis import strategies as st
from hypothesis.strategies import composite

from models import FeedEntry


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

@composite
def rss_entry_xml(draw):
    """Generate a single <item> XML block with title, link, guid, and pubDate."""
    title = draw(st.text(min_size=1, max_size=80).filter(lambda s: "<" not in s and "&" not in s))
    link = draw(st.from_regex(r"https?://[a-z0-9\-]+\.[a-z]{2,6}(/[a-z0-9\-]*){0,4}", fullmatch=True))
    guid = draw(st.text(min_size=1, max_size=80).filter(lambda s: "<" not in s and "&" not in s))
    pub_date = draw(st.from_regex(
        r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun), \d{2} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) 20[0-2]\d \d{2}:\d{2}:\d{2} \+0000",
        fullmatch=True,
    ))
    return (
        f"<item>"
        f"<title>{title}</title>"
        f"<link>{link}</link>"
        f"<guid>{guid}</guid>"
        f"<pubDate>{pub_date}</pubDate>"
        f"</item>",
        {"title": title, "link": link, "guid": guid, "published": pub_date},
    )


@composite
def rss_feed_xml(draw, min_entries=1, max_entries=5):
    """Generate a complete RSS 2.0 XML document with one or more items.

    Returns a tuple of (xml_string, list_of_entry_dicts).
    """
    entries = draw(st.lists(rss_entry_xml(), min_size=min_entries, max_size=max_entries))
    items_xml = "".join(item_xml for item_xml, _ in entries)
    entry_dicts = [meta for _, meta in entries]
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<rss version=\"2.0\">"
        "<channel>"
        "<title>AWS What's New</title>"
        "<link>https://aws.amazon.com/about-aws/whats-new/recent/</link>"
        "<description>AWS announcements</description>"
        f"{items_xml}"
        "</channel>"
        "</rss>"
    )
    return xml, entry_dicts


@composite
def feed_entry(draw):
    """Generate a FeedEntry instance with non-empty fields."""
    printable = st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")), min_size=1, max_size=60)
    guid = draw(printable)
    title = draw(printable)
    link = draw(st.from_regex(r"https?://[a-z0-9\-]+\.[a-z]{2,6}(/[a-z0-9\-]*){0,4}", fullmatch=True))
    published = draw(st.from_regex(
        r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun), \d{2} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) 20[0-2]\d \d{2}:\d{2}:\d{2} \+0000",
        fullmatch=True,
    ))
    return FeedEntry(guid=guid, title=title, link=link, published=published)


@composite
def feed_url_list(draw, min_size=1, max_size=5):
    """Generate a non-empty list of feed URL strings."""
    url = st.from_regex(r"https?://[a-z0-9\-]+\.[a-z]{2,6}(/[a-z0-9\-]*){0,4}", fullmatch=True)
    return draw(st.lists(url, min_size=min_size, max_size=max_size, unique=True))


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_rss_xml():
    """Return a minimal valid RSS XML string with two entries."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0">'
        "<channel>"
        "<title>AWS What's New</title>"
        "<link>https://aws.amazon.com/about-aws/whats-new/recent/</link>"
        "<description>AWS announcements</description>"
        "<item>"
        "<title>New Feature A</title>"
        "<link>https://aws.amazon.com/about-aws/whats-new/2024/01/feature-a/</link>"
        "<guid>https://aws.amazon.com/about-aws/whats-new/2024/01/feature-a/</guid>"
        "<pubDate>Mon, 01 Jan 2024 12:00:00 +0000</pubDate>"
        "</item>"
        "<item>"
        "<title>New Feature B</title>"
        "<link>https://aws.amazon.com/about-aws/whats-new/2024/01/feature-b/</link>"
        "<guid>https://aws.amazon.com/about-aws/whats-new/2024/01/feature-b/</guid>"
        "<pubDate>Sun, 31 Dec 2023 12:00:00 +0000</pubDate>"
        "</item>"
        "</channel>"
        "</rss>"
    )


@pytest.fixture
def sample_feed_entry():
    """Return a single FeedEntry for use in unit tests."""
    return FeedEntry(
        guid="https://aws.amazon.com/about-aws/whats-new/2024/01/feature-a/",
        title="New Feature A",
        link="https://aws.amazon.com/about-aws/whats-new/2024/01/feature-a/",
        published="Mon, 01 Jan 2024 12:00:00 +0000",
    )
