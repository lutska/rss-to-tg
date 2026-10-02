# rss-to-tg

Serverless AWS news notifier that polls RSS feeds and sends new entries to a Telegram channel. Supports both real-time daily notifications and curated weekly digests. Built with Python (AWS Lambda), DynamoDB, and Terraform.

## Architecture

### Mode 1: Daily Notifications Only

```
EventBridge (schedule)
    └── Lambda (Python 3.12)
            ├── RSS Feeds (HTTP fetch)
            ├── SSM Parameter Store — bot token, chat ID (SecureString)
            ├── SSM Parameter Store — last-seen entry state per feed
            ├── Telegram Bot API — sendMessage
            ├── CloudWatch Logs — structured logs
            └── SQS Dead Letter Queue — failed invocations
```

### Mode 2: Weekly Digest Only (Default)

```
EventBridge (daily collection)
  ├── Primary (Midnight UTC)
  └── Backup (6 AM UTC)
       └── Collector Lambda (Python 3.12 - collector.py)
           ├── RSS Feeds (HTTP fetch)
           ├── Category Normalization & Emoji Assignment
           ├── SSM Parameter Store — last-seen entry state per feed
           ├── DynamoDB Table — rss-to-tg-weekly-entries
           │   ├── Composite key: (feed_hash, entry_guid)
           │   ├── TimestampIndex for 7-day queries
           │   └── TTL: 14 days automatic cleanup
           ├── CloudWatch Logs — structured logs
           └── SQS Dead Letter Queue — failed invocations

(Monday - Sunday: Entries accumulate in DynamoDB)

EventBridge (Sunday 9 PM UTC)
    └── Digest Sender Lambda (Python 3.12 - digest_sender.py)
        ├── DynamoDB Query — retrieve past 7 days
        ├── Category Grouping & Emoji Assignment
        ├── Message Formatting
        ├── SSM Parameter Store — bot token, chat ID (SecureString)
        ├── Telegram Bot API — sendMessage (HTML formatted)
        ├── Cleanup — delete old entries
        ├── CloudWatch Logs — structured logs
        └── SQS Dead Letter Queue — failed invocations
```

### Mode 3: Both (Daily + Weekly)

```
Daily Path (if enabled):
    EventBridge (e.g., rate(60 minutes))
        └── Daily Lambda → Sends immediately to Telegram

Weekly Path (if enabled):
    EventBridge (daily) → Collector Lambda → DynamoDB
    EventBridge (Sunday) → Digest Sender Lambda → Telegram

Shared Resources:
    ├── SSM Parameter Store — credentials & state
    ├── DynamoDB (weekly mode only) — entry storage
    ├── CloudWatch Logs — all Lambda execution logs
    ├── SQS Dead Letter Queue — failed invocations
    └── IAM Role — shared permissions
```

## Project Structure

```
.
├── lambda/
│   ├── handler.py             # Daily notifier (daily mode)
│   ├── collector.py           # Weekly collector (stores in DynamoDB)
│   ├── digest_sender.py       # Weekly digest formatter & sender (weekly mode)
│   ├── rss_parser.py          # RSS fetch & parse (shared)
│   ├── state_store.py         # SSM state read/write (shared)
│   ├── secret_store.py        # SSM SecureString loader (shared)
│   ├── telegram.py            # Telegram Bot API client (shared)
│   ├── models.py              # FeedEntry / FeedState dataclasses
│   ├── requirements.txt       # feedparser, requests, boto3
│   ├── build.sh               # Builds function.zip (daily mode)
│   ├── build-weekly-digest.sh # Builds weekly-digest.zip (weekly mode)
│   └── tests/            	   # pytest + hypothesis tests
│   ├── check_feed.py          # Debug utility to fetch latest RSS entry (GUID)
├── terraform/
│   ├── main.tf                # Daily notifications resources
│   ├── weekly_digest.tf       # Weekly digest system resources
│   ├── outputs.tf             # Resource IDs & useful exports
│   ├── variables.tf           # Input variables for both modes
│   └── .terraform/            # Terraform state & providers
└── .gitignore
```

## Prerequisites

- AWS CLI configured with credentials and required IAM permissions
- Terraform >= 1.0
- Python 3.12
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
- A Telegram channel where the bot is an admin
- RSS feed URL(s) to monitor

## Setup

### 1. Create a Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Run `/newbot` and follow the prompts
3. Copy the bot token
4. Add the bot as an admin to your channel
5. Get your channel ID:
   - For a public channel: `@yourchannel`
   - For a private channel: numeric ID (e.g., `-1001234567890`)
   - Find it via [@userinfobot](https://t.me/userinfobot) or API endpoint

**Test the bot:**
```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage" \
  -d "chat_id=<YOUR_CHAT_ID>" \
  -d "text=Hello from AWS News!"
```

### 2. Build the Lambda Packages

Build both packages (one will be used based on your configuration):

```bash
# For daily notifications mode
bash lambda/build.sh

# For weekly digest mode
bash lambda/build-weekly-digest.sh
```

This creates:
- `lambda/function.zip` — for daily notifications (handler.py)
- `lambda/weekly-digest.zip` — for weekly digest (collector.py + digest_sender.py)

### 3. Deploy Infrastructure

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### 4. Configure Telegram Credentials in SSM

After `terraform apply`, set your real secrets in SSM Parameter Store:

```bash
# Bot token (from @BotFather)
# Format: <bot_id>:<random_string>
# Example: 7123456789:AAFabcdefghijklmnopqrstuvwxyz123456
aws ssm put-parameter \
  --name /notifier/telegram/bot_token \
  --value "YOUR_BOT_TOKEN" \
  --type SecureString \
  --overwrite \
  --region eu-west-1

# Chat ID (public: @channel, private: -1001234567890)
# Get numeric ID by forwarding a message to @userinfobot
# Or via: https://api.telegram.org/bot<bot_token>/getUpdates
aws ssm put-parameter \
  --name /notifier/telegram/chat_id \
  --value "YOUR_CHANNEL_ID" \
  --type SecureString \
  --overwrite \
  --region eu-west-1
```

## Configuration

All values are configurable via `terraform.tfvars`:

```hcl
region      = "eu-west-1"
name_prefix = "rss-to-tg"
feed_urls   = "https://aws.amazon.com/about-aws/whats-new/recent/feed/"


# ═══════════════════════════════════════════════════════════════════════════
# NOTIFICATION MODES - Choose One or Both
# ═══════════════════════════════════════════════════════════════════════════

# Option 1: Daily Instant Notifications (sends immediately when entries found)
enable_daily_notifications = false

# Option 2: Weekly Digest (collects throughout week, sends Sunday 9 PM)
enable_weekly_digest = true

# ─── DAILY NOTIFICATIONS (if enabled) ──────────────────────────────────────
daily_collector_schedule = "rate(60 minutes)"  # Check every hour

# ─── WEEKLY DIGEST (if enabled) ────────────────────────────────────────────
# Collector runs daily to accumulate entries throughout the week
collector_schedule_primary = "cron(0 0 ? * * *)"   # Daily at midnight UTC
collector_schedule_backup  = "cron(0 6 ? * * *)"   # Daily at 6 AM UTC

# Digest sends on Sunday at 9 PM UTC
digest_schedule_expression = "cron(0 21 ? * SUN *)"
digest_title               = "AWS Weekly"
digest_days                = 7

# Common Settings
lambda_timeout     = 60
lambda_memory      = 128
dlq_retention_days = 14
entry_ttl_days     = 14
environment        = "dev"
project            = "rss-to-tg"
```

### Notification Mode Options

**Option A: Daily Notifications Only**
```hcl
enable_daily_notifications = true
enable_weekly_digest       = false
daily_collector_schedule   = "rate(60 minutes)"
```
- Sends entries immediately when found
- Hourly polling (configurable)
- No digest formatting

**Option B: Weekly Digest Only** (default, recommended)
```hcl
enable_daily_notifications = false
enable_weekly_digest       = true
collector_schedule_primary = "cron(0 0 ? * * *)"
digest_schedule_expression = "cron(0 21 ? * SUN *)"
```
- Formatted weekly digest
- No notification spam
- Grouped by category
- Wait until Sunday for digest

**Option C: Both (Daily + Weekly)**
```hcl
enable_daily_notifications = true
enable_weekly_digest        = true
daily_collector_schedule   = "rate(6 hours)"  # Less frequent to save costs
collector_schedule_primary = "cron(0 0 ? * * *)"
digest_schedule_expression = "cron(0 21 ? * SUN *)"
```
- Instant notifications for urgent items
- Weekly summary for comprehensive review
- More Telegram messages

## How It Works

### Hourly Checks (if enable_daily_notifications = true)

1. **EventBridge triggers** the Daily Collector Lambda on your configured schedule (default: every 60 minutes)
2. **Fetch RSS feeds**: Lambda retrieves entries from configured feed URLs
3. **Filter new entries**: Compares entries against last-seen ID in SSM Parameter Store
   - First run: stores only the latest entry to establish baseline (avoids backfill)
   - Subsequent runs: returns all entries newer than the last-seen ID
4. **Format entry**: Creates a simple message with title and link
5. **Send to Telegram**: Sends each new entry immediately to Telegram
6. **Update SSM state**: Last-seen entry ID stored for next check
7. **No duplicates**: Same entry won't be sent twice across invocations

**When to use:**
- Breaking news alerts
- Urgent updates
- Real-time notifications
- Frequent monitoring (every 30-60 minutes)


---

### Weekly Digest System (if enable_weekly_digest = true)

**Collection Phase (Daily: Midnight & 6 AM UTC)**

1. **EventBridge triggers** the Collector Lambda daily at midnight UTC (primary) and 6 AM UTC (backup)
2. **Fetch RSS feeds**: Collector retrieves entries from configured feed URLs
3. **Filter new entries**: Compares entries against last-seen ID in SSM Parameter Store
   - First run: stores only the latest entry to establish baseline
   - Subsequent runs: stores only entries newer than the last-seen ID
4. **Normalize categories**: Converts raw RSS tags to clean names with emojis
   - `"aws-news"` → `"📌 AWS News"`
   - `"machine-learning"` → `"🤖 Machine Learning"`
   - `"cloud-security"` → `"🔒 Cloud Security"`
5. **Store in DynamoDB**: Each entry includes:
   - `feed_hash` + `entry_guid` (composite primary key)
   - title, link, category, published date
   - timestamp (storage time), TTL (expiry)
6. **Update SSM state**: Last-seen entry ID stored for next run
7. **No duplicates**: Same entry won't be stored twice across invocations

**Why dual collection (primary + backup)?**
- Primary (midnight) catches all daily entries
- Backup (6 AM) handles network/RSS feed failures
- Ensures at least one collection succeeds
- Cost: 8 extra invocations/month (negligible)

**Digest Phase (Sunday 9 PM UTC)**

1. **EventBridge triggers** the Digest Sender Lambda every Sunday at 9 PM UTC
2. **Query DynamoDB**: Retrieve all entries stored in the past 7 days
3. **Group by category**: Organize entries with their emoji prefix
4. **Format message**: Create a structured digest with:
   - Header: `📬 AWS Weekly | Week #2026-40 | 25 Sep 2026 to 02 Oct 2026`
   - Entry counts per category: `🔒 Cloud Security (5)`
   - Hyperlinked article titles
   - Total article count
5. **Send to Telegram**: HTML-formatted message with clickable links
6. **Cleanup**: Delete entries older than 7 days (automatic TTL + manual delete)

**When to use:**
- Weekly digest summary
- Curated review
- Less notification spam
- Cost-conscious setup


---

## Digest Format

Example of a weekly digest message:

```
📬 AWS Weekly
Issue #2026-40 | 25 Sep 2026 to 02 Oct 2026
Total articles: 11

🤖 Machine Learning (3)
  ▸ SageMaker Auto Training Features
  ▸ New ML Model Deployment Options
  ▸ AI-Powered Anomaly Detection

🔒 Cloud Security (3)
  ▸ EC2 Security Group Best Practices
  ▸ IAM Policy Deep Dive
  ▸ GuardDuty Runtime Monitoring

⚙️ Devops (2)
  ▸ CloudFormation Updates
  ▸ Lambda Performance Improvements

📌 AWS News (3)
  ▸ S3 New Features Released
  ▸ RDS Updates
  ▸ DynamoDB Improvements
```

**Features:**
- Categories normalized and emoji-prefixed
- Entry count per category shown in parentheses
- Total article count in header
- Alphabetically sorted categories
- Clickable links to full articles
- Messages over 4000 characters are truncated gracefully



## AWS IAM Permissions Required

**Quick option — attach these AWS managed policies:**
- `IAMFullAccess`
- `AWSLambda_FullAccess`
- `AmazonSSMFullAccess`
- `AmazonSQSFullAccess`
- `AmazonDynamoDBFullAccess` (only if using weekly digest)
- `CloudWatchLogsFullAccess`
- `AmazonEventBridgeFullAccess`

**Minimal custom policy (recommended):**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "IAM",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:GetRole",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:PassRole"
      ],
      "Resource": "arn:aws:iam::*:role/rss-to-tg-*"
    },
    {
      "Sid": "Lambda",
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction",
        "lambda:DeleteFunction",
        "lambda:GetFunction",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:AddPermission",
        "lambda:RemovePermission"
      ],
      "Resource": "arn:aws:lambda:eu-west-1:*:function:rss-to-tg-*"
    },
    {
      "Sid": "DynamoDB",
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateTable",
        "dynamodb:DeleteTable",
        "dynamodb:DescribeTable",
        "dynamodb:UpdateTable",
        "dynamodb:UpdateTimeToLive",
		"dynamodb:DescribeTimeToLive",
		"dynamodb:UpdateTimeToLive"
      ],
      "Resource": "arn:aws:dynamodb:eu-west-1:*:table/rss-to-tg-*"
    },
    {
      "Sid": "EventBridge",
      "Effect": "Allow",
      "Action": [
        "events:PutRule",
        "events:DeleteRule",
        "events:DescribeRule",
        "events:PutTargets",
        "events:RemoveTargets"
      ],
      "Resource": "arn:aws:events:eu-west-1:*:rule/rss-to-tg-*"
    },
    {
      "Sid": "SSM",
      "Effect": "Allow",
      "Action": [
        "ssm:PutParameter",
        "ssm:GetParameter",
        "ssm:DeleteParameter"
      ],
      "Resource": "arn:aws:ssm:eu-west-1:*:parameter/notifier/*"
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:DeleteLogGroup",
        "logs:PutRetentionPolicy"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SQS",
      "Effect": "Allow",
      "Action": [
        "sqs:CreateQueue",
        "sqs:DeleteQueue",
        "sqs:GetQueueAttributes",
        "sqs:SetQueueAttributes"
      ],
      "Resource": "arn:aws:sqs:eu-west-1:*:rss-to-tg-*"
    }
  ]
}
```

## Cost Estimate

Based on default settings (daily collection + Sunday digest):

| Service | Usage | Est. Monthly Cost |
|---------|-------|-------------------|
| Lambda | 60 collector + 4 digest invocations | ~$0.001 |
| DynamoDB | On-demand, ~10-20 items/day stored | ~$0.001 |
| EventBridge | 64 scheduled rule invocations | ~$0.00 |
| SSM | ~50 API calls (standard tier) | ~$0.00 |
| CloudWatch Logs | ~1 MB ingested/month | ~$0.001 |
| SQS (DLQ) | Near zero (only on failures) | ~$0.00 |

**Total: ~$0.003-$0.01/month** — essentially free!

### Cost Comparison

| Mode | Lambda Invocations/Month | Monthly Cost |
|------|--------------------------|--------------|
| Daily Only | 1,440 | $0.02-$0.05 |
| Weekly Only | 64 | $0.003-$0.01 |
| Both (hourly) | 1,504 | $0.05-$0.10 |
| Both (6h) | 368 | $0.01-$0.03 |


## Cleanup

```bash
cd terraform
terraform destroy
```

## License

MIT

