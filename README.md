# rss-to-tg

Serverless AWS news notifier that polls an RSS feed and sends new entries to a Telegram channel. Built with Python (AWS Lambda) and Terraform.

## Architecture

```
EventBridge (schedule)
    └── Lambda (Python 3.12)
            ├── SSM Parameter Store  — bot token, chat ID (SecureString)
            ├── SSM Parameter Store  — last-seen entry state per feed
            ├── Telegram Bot API     — sendMessage
            ├── CloudWatch Logs      — structured logs
            └── SQS Dead Letter Queue — failed invocations
```

## Project Structure

```
.
├── lambda/
│   ├── handler.py        # Lambda entry point
│   ├── rss_parser.py     # RSS fetch & parse, entry filtering
│   ├── state_store.py    # SSM state read/write
│   ├── secret_store.py   # SSM SecureString secrets loader
│   ├── telegram.py       # Telegram Bot API client
│   ├── models.py         # FeedEntry / FeedState dataclasses
│   ├── requirements.txt  # feedparser, requests
│   ├── build.sh          # Builds function.zip for Terraform
│   └── tests/            # pytest + hypothesis tests
│   └── check_feed.py     # Debug utility to fetch latest RSS entry (GUID)
├── terraform/
│   ├── main.tf           # All AWS resources
│   └── variables.tf      # Input variables
└── .gitignore
```

## Prerequisites

- AWS CLI configured with credentials and required IAM permissions. Check 'AWS IAM Permissions Required' at the end of this document
- Terraform >= 1.0
- Python 3.12
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
- A Telegram channel where the bot is an admin

## Setup

### 1. Create a Telegram bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Run `/newbot` and follow the prompts
3. Copy the bot token
4. Add the bot as an admin to your channel
5. Get your channel ID (e.g. `@yourchannel` or a numeric ID like `-1001234567890`)
6. test it with:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage" \
  -d "chat_id=<YOUR_CHAT_ID>" \
  -d "text=Hello from test"
```

### 2. Build the Lambda package

```bash
bash lambda/build.sh
```

This creates `lambda/function.zip` ready for Terraform.

### 3. Deploy infrastructure

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### 4. Set real credentials in SSM

After `terraform apply`, replace the placeholder values with your real secrets:

```bash
# bot_token — get this from @BotFather on Telegram after creating a new bot (see step 1)
# format: <bot_id>:<random_string> 
# example value for "YOUR_BOT_TOKEN" is "7123456789:AAFabcdefghijklmnopqrstuvwxyz123456"

aws ssm put-parameter \
  --name /notifier/telegram/bot_token \
  --value "YOUR_BOT_TOKEN" \
  --type SecureString \
  --overwrite \
  --region eu-west-1

# chat_id — your channel username (with @) or numeric ID
# get numeric ID by forwarding a channel message to @userinfobot on Telegram
# Chat ID can be found via:
# https://api.telegram.org/bot<bot_token>/getUpdates

# Note: the "-" symbol must not be omitted
# example value: @myawsnewschannel  or  -1001234567890

aws ssm put-parameter \
  --name /notifier/telegram/chat_id \
  --value "YOUR_CHANNEL_ID" \
  --type SecureString \
  --overwrite \
  --region eu-west-1
```




## Configuration

All values are configurable via Terraform variables. Override them in a `terraform.tfvars` file:

```hcl
region              = "eu-west-1"
name_prefix         = "rss-to-tg"
feed_urls           = "https://aws.amazon.com/about-aws/whats-new/recent/feed/"
schedule_expression = "rate(60 minutes)"
lambda_timeout      = 60
lambda_memory       = 128
dlq_retention_days  = 14
environment         = "dev"
project             = "rss-to-tg"
```

## AWS IAM Permissions Required

Your AWS user/role needs the following permissions to deploy this infrastructure.

**Quick option — attach these AWS managed policies:**
- `IAMFullAccess`
- `AWSLambda_FullAccess`
- `AmazonSSMFullAccess`
- `AmazonSQSFullAccess`
- `CloudWatchLogsFullAccess`
- `AmazonEventBridgeFullAccess`

**Minimal custom policy (recommended):**
(see the file terraform/iam_policy.json for full JSON)


## Running Tests

```bash
python3 -m pytest lambda/tests/ -v
```

## Teardown

```bash
cd terraform
terraform destroy
```

## How It Works

1. EventBridge triggers the Lambda every 60 minutes (configurable)
2. Lambda loads the Telegram "bot_token" and "chat ID" from SSM SecureString parameters
3. For each configured RSS feed URL:
   - Fetches and parses the feed
   - Reads the last-seen entry ID from SSM
   - Filters to only new entries (or just the latest on first run)
   - Sends each new entry to Telegram oldest-first
   - Updates the last-seen ID in SSM
4. All activity is logged to CloudWatch Logs
5. Any unhandled failure routes the event to the SQS Dead Letter Queue

## Troubleshooting. Debug RSS feed locally

Run the local helper script to verify the RSS feed and see the latest entry:

```bash
python3 lambda/check_feed.py
```

## Cost Estimate (eu-west-1, no free tier)

Based on default settings: polling every 60 minutes = 720 invocations/month.

| Service | Usage | Est. monthly cost |
|---|---|---|
| Lambda | 720 invocations × 128 MB × ~3s | ~$0.0005 |
| EventBridge | 720 scheduled rule invocations | ~$0.00 |
| SSM Parameter Store | ~2200 API calls (Standard tier) | ~$0.00 |
| SQS (DLQ) | Near zero (only on failures) | ~$0.00 |
| CloudWatch Logs | ~1 MB ingested/month | ~$0.01 |

**Total: ~$0.01–$0.05/month** — essentially free even without the AWS free tier.


