"""Digest Sender — queries DynamoDB for the week's entries and sends formatted digest to Telegram."""
import hashlib
import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta

import boto3
import requests

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

FEED_URLS = [u.strip() for u in os.environ.get("FEED_URLS", "").split(",") if u.strip()]
BOT_TOKEN_PATH = os.environ.get("SSM_BOT_TOKEN_PATH", "/notifier/telegram/bot_token")
CHAT_ID_PATH = os.environ.get("SSM_CHAT_ID_PATH", "/notifier/telegram/chat_id")
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE_NAME", "")
DIGEST_TITLE = os.environ.get("DIGEST_TITLE", "AWS Weekly")
DIGEST_DAYS = int(os.environ.get("DIGEST_DAYS", "7"))


# ── Helpers ──────────────────────────────────────────────────────────────────

def feed_hash(feed_url):
    """Generate a consistent hash for a feed URL."""
    return hashlib.md5(feed_url.encode()).hexdigest()

def get_param(ssm, name, decrypt=False):
    """Get SSM parameter value."""
    return ssm.get_parameter(Name=name, WithDecryption=decrypt)["Parameter"]["Value"]


# ── DynamoDB Query ───────────────────────────────────────────────────────────

def get_weekly_entries(dynamodb, table_name, feed_url, days=7):
    """Retrieve entries from the last N days for a given feed."""
    table = dynamodb.Table(table_name)
    fhash = feed_hash(feed_url)
    
    cutoff_time = int(time.time()) - (days * 86400)
    
    try:
        response = table.query(
            IndexName="TimestampIndex",
            KeyConditionExpression="feed_hash = :fhash AND #ts >= :cutoff",
            ExpressionAttributeNames={
                "#ts": "timestamp"
            },
            ExpressionAttributeValues={
                ":fhash": fhash,
                ":cutoff": cutoff_time
            }
        )
        return response.get("Items", [])
    except Exception as e:
        logger.error("Failed to query DynamoDB", extra={
            "feed_url": feed_url,
            "error": str(e)
        })
        return []


# ── Message Formatting ───────────────────────────────────────────────────────

def normalize_category(category_str):
    """Normalize and beautify category name for display.
    
    Converts:
    - "aws-news" → "AWS News"
    - "machine-learning" → "Machine Learning"
    - "cloud-security" → "Cloud Security"
    - "General" → "General News"
    - "general:products/aws/..." → "AWS Security"
    """
    category_str = str(category_str or "").strip()
    if not category_str or category_str.lower() == "general":
        return "📰 General News"

    # The feed can put several tags in one category; use a product tag for
    # display while leaving the original value untouched in DynamoDB.
    products = [tag.strip().split("general:products/", 1)[1]
                for tag in category_str.split(",")
                if tag.strip().startswith("general:products/")]
    services = [product for product in products if product != "aws-govcloud-us"]
    if services:
        category_str = services[0].replace("-", " ")

    known_topics = {
        "aws-news", "aws news", "machine-learning", "machine learning",
        "cloud-security", "cloud security", "devops", "database",
        "storage", "serverless", "networking", "general news",
    }
    if not services and category_str.lower() not in known_topics:
        return "📰 General News"
    
    # Replace hyphens and underscores with spaces
    normalized = category_str.replace("-", " ").replace("_", " ")
    
    # Title case each word
    words = normalized.split()
    capitalized = []
    
    for word in words:
        word_upper = word.upper()
        if word_upper == "AWS":
            capitalized.append("AWS")
        elif word_upper == "ML":
            capitalized.append("ML")
        elif word_upper == "AI":
            capitalized.append("AI")
        elif word_upper == "AND":
            capitalized.append("&")  # Replace "and" with "&"
        elif word_upper in {"EKS", "ECS", "EC2", "S3", "IAM", "EMR", "RDS"}:
            capitalized.append(word_upper)
        elif word_upper == "DYNAMODB":
            capitalized.append("DynamoDB")
        elif word_upper == "GUARDDUTY":
            capitalized.append("GuardDuty")
        else:
            capitalized.append(word.capitalize())
    
    result = " ".join(capitalized).strip()
    
    # Add emoji based on category
    if "security" in result.lower():
        emoji = "🔒"
    elif "machine" in result.lower() or "ai" in result.lower() or "ml" in result.lower():
        emoji = "🤖"
    elif "devops" in result.lower() or "infrastructure" in result.lower():
        emoji = "⚙️"
    elif "database" in result.lower() or "data" in result.lower():
        emoji = "💾"
    elif "serverless" in result.lower() or "lambda" in result.lower():
        emoji = "⚡"
    elif "cost" in result.lower() or "optimize" in result.lower():
        emoji = "💰"
    elif "network" in result.lower() or "vpc" in result.lower():
        emoji = "🌐"
    elif "storage" in result.lower() or "s3" in result.lower():
        emoji = "📦"
    else:
        emoji = "📌"
    
    # Keep length reasonable (max 40 chars for display)
    if len(result) > 40:
        result = result[:37] + "..."
    
    return f"{emoji} {result}"


def format_digest(entries, title, start_date, end_date, issue_number):
    """Format entries into a digest message similar to AWS Weekly."""
    if not entries:
        return None
    
    # Group entries by category
    by_category = defaultdict(list)
    for entry in entries:
        raw_category = entry.get("category", "General")
        category = normalize_category(raw_category)
        by_category[category].append(entry)
    
    # Build message header
    header = f"📬 <b>{title}</b>\n"
    header += f"<i>Week #{issue_number} | {start_date} to {end_date}</i>\n"
    header += f"<i>Total articles: {len(entries)}</i>\n\n"
    
    # Build categorized sections
    sections = []
    for category in sorted(by_category.keys()):
        category_entries = by_category[category]
        section = f"<b>{category}</b> ({len(category_entries)})\n"
        
        for entry in category_entries:
            title_text = entry.get("title", "Untitled")
            link = entry.get("link", "")
            section += f"  ▸ <a href='{link}'>{title_text}</a>\n"
        
        sections.append(section)
    
    message = header + "\n".join(sections)
    
    # Telegram has a 4096 character limit
    if len(message) > 4000:
        message = message[:3950] + "\n\n<i>... (message truncated)</i>"
    
    return message


# ── Telegram Sender ──────────────────────────────────────────────────────────

def send_digest(token, chat_id, message):
    """Send formatted digest to Telegram."""
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        },
        timeout=10,
    )
    
    if not resp.ok:
        logger.error("Telegram error", extra={"response": resp.text})
        raise Exception(f"Telegram API error: {resp.status_code}")
    
    return resp.json()


# ── Cleanup Old Entries ──────────────────────────────────────────────────────

def cleanup_old_entries(dynamodb, table_name, feed_url, days=7):
    """Delete entries older than N days (belt-and-suspenders with TTL)."""
    table = dynamodb.Table(table_name)
    fhash = feed_hash(feed_url)
    
    cutoff_time = int(time.time()) - (days * 86400)
    
    try:
        response = table.query(
            IndexName="TimestampIndex",
            KeyConditionExpression="feed_hash = :fhash AND #ts < :cutoff",
            ExpressionAttributeNames={
                "#ts": "timestamp"
            },
            ExpressionAttributeValues={
                ":fhash": fhash,
                ":cutoff": cutoff_time
            }
        )
        
        items = response.get("Items", [])
        
        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(
                    Key={
                        "feed_hash": item["feed_hash"],
                        "entry_guid": item["entry_guid"]
                    }
                )
        
        logger.info("Cleaned up old entries", extra={
            "feed_url": feed_url,
            "count": len(items)
        })
        
    except Exception as e:
        logger.error("Failed to cleanup old entries", extra={
            "feed_url": feed_url,
            "error": str(e)
        })


# ── Lambda Handler ───────────────────────────────────────────────────────────

def lambda_handler(event, context):
    """Generate and send weekly digest."""
    ssm = boto3.client("ssm")
    dynamodb = boto3.resource("dynamodb")
    
    # Load secrets
    token = get_param(ssm, BOT_TOKEN_PATH, decrypt=True)
    chat_id = get_param(ssm, CHAT_ID_PATH, decrypt=True)
    
    # Calculate date range for the PAST week (what we collected)
    # Shows from 7 days ago through today (inclusive)
    today = datetime.now()
    end_date_obj = today  # Today (inclusive)
    start_date_obj = today - timedelta(days=6)  # 7 days ago
    
    end_date = end_date_obj.strftime("%d %b %Y")
    start_date = start_date_obj.strftime("%d %b %Y")
    
    # Issue number: Year-Week format
    # e.g., "2026-40" = year 2026, week 40
    week_number = today.strftime("%V")
    year = today.strftime("%Y")
    issue_number = f"{year}-{week_number}"
    
    # Collect entries from all feeds
    all_entries = []
    for feed_url in FEED_URLS:
        entries = get_weekly_entries(dynamodb, DYNAMODB_TABLE, feed_url, days=DIGEST_DAYS)
        all_entries.extend(entries)
        logger.info("Retrieved entries", extra={
            "feed_url": feed_url,
            "count": len(entries)
        })
    
    if not all_entries:
        logger.info("No entries to send for this week")
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "No entries to send"})
        }
    
    # Sort by timestamp (newest first)
    all_entries.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    
    # Format digest
    message = format_digest(all_entries, DIGEST_TITLE, start_date, end_date, issue_number)
    
    if not message:
        logger.info("No message generated")
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "No message to send"})
        }
    
    # Send to Telegram
    send_digest(token, chat_id, message)
    logger.info("Digest sent successfully", extra={"entry_count": len(all_entries)})
    
    # Cleanup old entries
    for feed_url in FEED_URLS:
        cleanup_old_entries(dynamodb, DYNAMODB_TABLE, feed_url, days=DIGEST_DAYS)
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Digest sent successfully",
            "entry_count": len(all_entries)
        })
    }
