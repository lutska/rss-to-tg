"""Collector — fetches RSS entries hourly and stores them in DynamoDB for weekly digest."""
import hashlib
import json
import logging
import os
import time

import boto3
import feedparser

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

FEED_URLS = [u.strip() for u in os.environ.get("FEED_URLS", "").split(",") if u.strip()]
STATE_PREFIX = os.environ.get("SSM_STATE_PATH_PREFIX", "/notifier/state")
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE_NAME", "")
ENTRY_TTL_DAYS = int(os.environ.get("ENTRY_TTL_DAYS", "14"))


# ── Helpers ──────────────────────────────────────────────────────────────────

def feed_hash(feed_url):
    """Generate a consistent hash for a feed URL."""
    return hashlib.md5(feed_url.encode()).hexdigest()

def state_path(feed_url):
    """SSM parameter path for storing last-seen entry ID."""
    return f"{STATE_PREFIX}/{feed_hash(feed_url)}"

def get_param(ssm, name):
    """Get SSM parameter value."""
    try:
        return ssm.get_parameter(Name=name)["Parameter"]["Value"]
    except ssm.exceptions.ParameterNotFound:
        return None

def put_param(ssm, name, value):
    """Store SSM parameter value."""
    ssm.put_parameter(Name=name, Value=value, Type="String", Overwrite=True)


# ── RSS Processing ───────────────────────────────────────────────────────────

def fetch_entries(feed_url):
    """Fetch and parse RSS feed entries."""
    feed = feedparser.parse(feed_url)
    if getattr(feed, "status", 200) != 200:
        logger.error("HTTP error fetching feed", extra={"url": feed_url, "status": feed.status})
        return []
    
    entries = []
    for e in feed.entries:
        # Extract category/service name
        category = "General"
        if hasattr(e, "tags") and e.tags:
            category = ",".join(tag.get("term", "") for tag in e.tags) or "General"
        
        entries.append({
            "guid": e.get("id") or e.get("link", ""),
            "title": e.get("title", ""),
            "link": e.get("link", ""),
            "category": category,
            "published": e.get("published", ""),
        })
    
    return entries

def filter_new(entries, last_seen_id):
    """Return entries newer than last_seen_id."""
    if not entries:
        return []
    if last_seen_id is None:
        # First run: take just the latest to establish baseline
        return [entries[0]]
    
    new = []
    for e in entries:
        if e["guid"] == last_seen_id:
            break
        new.append(e)
    return new


# ── DynamoDB Storage ─────────────────────────────────────────────────────────

def store_entries(dynamodb, table_name, feed_url, entries):
    """Store new entries in DynamoDB."""
    table = dynamodb.Table(table_name)
    current_time = int(time.time())
    ttl_time = current_time + (ENTRY_TTL_DAYS * 86400)
    
    fhash = feed_hash(feed_url)
    
    for entry in entries:
        try:
            table.put_item(
                Item={
                    "feed_hash": fhash,
                    "entry_guid": entry["guid"],
                    "title": entry["title"],
                    "link": entry["link"],
                    "category": entry["category"],
                    "published": entry["published"],
                    "timestamp": current_time,
                    "ttl": ttl_time,
                    "feed_url": feed_url,
                }
            )
        except Exception as e:
            logger.error("Failed to store entry", extra={
                "entry_guid": entry["guid"],
                "error": str(e)
            })


# ── Lambda Handler ───────────────────────────────────────────────────────────

def lambda_handler(event, context):
    """Collect RSS entries and store in DynamoDB."""
    ssm = boto3.client("ssm")
    dynamodb = boto3.resource("dynamodb")
    
    total_new = 0
    
    for feed_url in FEED_URLS:
        logger.info("Processing feed", extra={"feed_url": feed_url})
        
        # Fetch entries
        entries = fetch_entries(feed_url)
        if not entries:
            logger.warning("No entries fetched", extra={"feed_url": feed_url})
            continue
        
        # Get last seen entry
        last_seen = get_param(ssm, state_path(feed_url))
        
        # Filter new entries
        new_entries = filter_new(entries, last_seen)
        
        if new_entries:
            # Store in DynamoDB
            store_entries(dynamodb, DYNAMODB_TABLE, feed_url, new_entries)
            
            # Update last seen
            put_param(ssm, state_path(feed_url), new_entries[0]["guid"])
            
            total_new += len(new_entries)
            logger.info("Stored new entries", extra={
                "feed_url": feed_url,
                "count": len(new_entries)
            })
        else:
            logger.info("No new entries", extra={"feed_url": feed_url})
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Collection complete",
            "total_new_entries": total_new
        })
    }
