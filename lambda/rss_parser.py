"""RSS feed fetching and parsing logic."""
import logging
from typing import Optional

import feedparser

from models import FeedEntry

logger = logging.getLogger(__name__)


def fetch_and_parse(feed_url: str) -> list[FeedEntry]:
    """Fetch and parse an RSS feed URL into a list of FeedEntry objects.

    Returns an empty list and logs an error on:
    - HTTP non-200 status or connection failure (Requirement 1.3)
    - Malformed XML / parse error (Requirement 7.2)

    Extracts guid (fallback to link), title, link, and published for each
    entry (Requirement 1.5).
    """
    try:
        feed = feedparser.parse(feed_url)
    except Exception as exc:
        logger.error("Connection failure fetching feed", extra={"feed_url": feed_url, "error": str(exc)})
        return []

    # feedparser surfaces HTTP status in feed.status when it makes an HTTP request
    status = getattr(feed, "status", None)
    if status is not None and status != 200:
        logger.error(
            "Non-200 HTTP status fetching feed",
            extra={"feed_url": feed_url, "status_code": status},
        )
        return []

    # A bozo exception means feedparser encountered a parse error
    if feed.get("bozo") and feed.bozo_exception is not None:
        # Still attempt to use entries if any were recovered, but log the issue
        logger.error(
            "Malformed RSS feed",
            extra={"feed_url": feed_url, "parse_error": str(feed.bozo_exception)},
        )
        if not feed.entries:
            return []

    entries: list[FeedEntry] = []
    for item in feed.entries:
        guid: str = item.get("id") or item.get("link", "")
        title: str = item.get("title", "")
        link: str = item.get("link", "")
        published: str = item.get("published", "")

        entries.append(FeedEntry(guid=guid, title=title, link=link, published=published))

    return entries


def filter_new_entries(entries: list[FeedEntry], last_seen_id: Optional[str]) -> list[FeedEntry]:
    """Return entries that are newer than last_seen_id.

    Feed entries are assumed to be in newest-first order (standard RSS).

    - When last_seen_id is None (bootstrap), return only the single most
      recent entry (Requirement 2.4).
    - Otherwise return all entries that appear before the entry whose guid
      matches last_seen_id (Requirement 2.2).
    """
    if not entries:
        return []

    if last_seen_id is None:
        return [entries[0]]

    new: list[FeedEntry] = []
    for entry in entries:
        if entry.guid == last_seen_id:
            break
        new.append(entry)

    return new
