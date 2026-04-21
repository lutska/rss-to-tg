"""Lambda entry point — orchestrates the full RSS poll cycle."""
import json
import logging
import os

import boto3
import requests

from secret_store import load_secrets
from state_store import read_last_seen, write_last_seen
from rss_parser import fetch_and_parse, filter_new_entries
from telegram import format_message, send_message

logger = logging.getLogger(__name__)
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))


def lambda_handler(event, context):
    """Orchestrate a single RSS poll cycle.

    1. Load Telegram credentials from SSM — raises on failure (routes to DLQ).
    2. Parse FEED_URLS env var into a list of feed URLs (Requirement 1.4).
    3. For each feed URL:
       a. Fetch and parse the RSS feed.
       b. Read the last-seen GUID from SSM.
       c. Filter to new entries only.
       d. Reverse so oldest entry is first (Requirement 3.5).
       e. Send each entry to Telegram.
       f. Persist the newest GUID back to SSM (Requirement 2.3).
       g. Emit a structured log record (Requirement 6.1).
    """
    ssm_client = boto3.client("ssm")
    session = requests.Session()

    # Step 1: load secrets — any failure raises and routes the invocation to DLQ
    secrets = load_secrets(ssm_client)
    bot_token = secrets["bot_token"]
    chat_id = secrets["chat_id"]

    # Step 2: parse feed URLs from environment variable
    feed_urls_raw = os.environ.get("FEED_URLS", "")
    feed_urls = [url.strip() for url in feed_urls_raw.split(",") if url.strip()]

    logger.info("Starting poll cycle", extra={"feed_count": len(feed_urls)})

    # Step 3: process each feed
    for feed_url in feed_urls:
        dispatch_status = "ok"
        new_entries_count = 0

        try:
            # a. Fetch and parse
            entries = fetch_and_parse(feed_url)

            # b. Read last-seen GUID
            last_seen_id = read_last_seen(feed_url, ssm_client)

            # c. Filter to new entries only
            new_entries = filter_new_entries(entries, last_seen_id)

            # d. Reverse so oldest is sent first (Requirement 3.5)
            new_entries = list(reversed(new_entries))

            new_entries_count = len(new_entries)

            # e. Send each entry to Telegram
            for entry in new_entries:
                text = format_message(entry)
                send_message(bot_token, chat_id, text, session)

            # f. Update state with the most recent entry's GUID (last after reversal)
            if new_entries:
                write_last_seen(feed_url, new_entries[-1].guid, ssm_client)

        except Exception as exc:
            dispatch_status = f"error: {exc}"
            logger.error(
                "Unhandled error processing feed",
                extra={"feed_url": feed_url, "error": str(exc)},
                exc_info=True,
            )

        # g. Structured log record (Requirement 6.1)
        logger.info(
            json.dumps({
                "feed_url": feed_url,
                "new_entries_count": new_entries_count,
                "dispatch_status": dispatch_status,
            })
        )
