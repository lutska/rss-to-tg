from dataclasses import dataclass


@dataclass
class FeedEntry:
    guid: str        # Unique identifier (GUID element or link fallback)
    title: str       # Entry title
    link: str        # Entry URL
    published: str   # Publication date string (ISO 8601 or RFC 2822)


@dataclass
class FeedState:
    feed_url: str       # Original feed URL
    last_seen_id: str   # GUID of the most recently processed entry
