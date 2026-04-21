# Implementation Plan: AWS News Telegram Notifier

## Overview

Implement the serverless AWS news notifier in incremental steps: core Python Lambda modules first, then tests, then Terraform infrastructure, and finally packaging and wiring everything together.

## Tasks

- [x] 1. Set up Lambda project structure and data models
  - Create `lambda/` directory with `__init__.py` files
  - Define `FeedEntry` and `FeedState` dataclasses in `lambda/models.py`
  - Create `lambda/requirements.txt` with `feedparser` and `requests`
  - Create `lambda/tests/conftest.py` with shared fixtures and Hypothesis strategies for generating RSS XML, FeedEntry instances, and URL lists
  - _Requirements: 1.5, 2.1_

- [x] 2. Implement `rss_parser.py`
  - [x] 2.1 Implement `fetch_and_parse(feed_url) -> list[FeedEntry]` using `feedparser`
    - Return empty list and log error on HTTP non-200 or connection failure (Requirement 1.3)
    - Log parse error and return empty list on malformed XML (Requirement 7.2)
    - Extract `guid` (fallback to `link`), `title`, `link`, `published` for each entry (Requirement 1.5)
    - _Requirements: 1.2, 1.3, 1.5, 7.1, 7.2_

  - [ ]* 2.2 Write property test for RSS parsing round-trip (Property 1)
    - **Property 1: RSS Parsing Round-Trip**
    - **Validates: Requirements 7.3, 1.2**
    - `# Feature: aws-news-telegram-notifier, Property 1: RSS Parsing Round-Trip`

  - [ ]* 2.3 Write property test for required fields on all parsed entries (Property 2)
    - **Property 2: Parsed Entries Have Required Fields**
    - **Validates: Requirements 1.5**
    - `# Feature: aws-news-telegram-notifier, Property 2: Parsed Entries Have Required Fields`

  - [ ]* 2.4 Write unit tests for `rss_parser.py` error conditions
    - Test HTTP 4xx/5xx response → empty list + error log
    - Test malformed XML → empty list + error log
    - Test valid RSS snippet → expected `FeedEntry` list
    - _Requirements: 1.3, 7.2_

- [x] 3. Implement `state_store.py`
  - [x] 3.1 Implement `read_last_seen(feed_url, ssm_client) -> str | None` and `write_last_seen(feed_url, guid, ssm_client)`
    - Derive SSM parameter path from MD5 hex digest of feed URL
    - Return `None` when parameter does not exist (bootstrap case)
    - _Requirements: 2.1, 2.3, 2.4_

  - [ ]* 3.2 Write property test for state store round-trip (Property 4)
    - **Property 4: State Store Round-Trip**
    - **Validates: Requirements 2.1**
    - `# Feature: aws-news-telegram-notifier, Property 4: State Store Round-Trip`

  - [ ]* 3.3 Write unit tests for `state_store.py`
    - Test SSM `GetParameter` exception → propagates error
    - Test missing parameter → returns `None`
    - Test successful write/read cycle with mocked SSM client
    - _Requirements: 2.1, 4.3_

- [x] 4. Implement entry filtering logic in `rss_parser.py`
  - [x] 4.1 Implement `filter_new_entries(entries, last_seen_id) -> list[FeedEntry]`
    - Return only entries appearing before `last_seen_id` in the list (newer entries)
    - When `last_seen_id` is `None`, return only the single most recent entry (bootstrap)
    - _Requirements: 2.2, 2.4_

  - [ ]* 4.2 Write property test for new entry filtering (Property 5)
    - **Property 5: New Entry Filtering**
    - **Validates: Requirements 2.2**
    - `# Feature: aws-news-telegram-notifier, Property 5: New Entry Filtering`

  - [ ]* 4.3 Write property test for bootstrap behaviour (Property 6)
    - **Property 6: Bootstrap Returns Single Entry**
    - **Validates: Requirements 2.4**
    - `# Feature: aws-news-telegram-notifier, Property 6: Bootstrap Returns Single Entry`

- [x] 5. Implement `secret_store.py`
  - Implement `load_secrets(ssm_client) -> dict` that reads `bot_token` and `chat_id` from SSM `SecureString` parameters
  - Raise exception immediately if either parameter is missing or SSM call fails (Requirement 4.3)
  - Read parameter paths from environment variables `SSM_BOT_TOKEN_PATH` and `SSM_CHAT_ID_PATH`
  - _Requirements: 3.4, 4.1, 4.2, 4.3_

  - [x]* 5.1 Write unit tests for `secret_store.py`
    - Test SSM unavailable → exception raised, no messages sent
    - Test missing secret value → exception raised
    - Test successful load returns correct dict keys
    - _Requirements: 4.3_

- [x] 6. Implement `telegram.py`
  - [x] 6.1 Implement `format_message(entry: FeedEntry) -> str` and `send_message(token, chat_id, text, session) -> None`
    - Format: `"📢 {title}\n\n{link}"` with `parse_mode=HTML`
    - Retry up to 3 times with backoff delays 1s, 2s, 4s on non-200 response (Requirement 3.3)
    - Log each retry at `WARNING`, log final failure at `ERROR`
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ]* 6.2 Write property test for message format (Property 8)
    - **Property 8: Message Format Contains Title and Link**
    - **Validates: Requirements 3.2, 3.1**
    - `# Feature: aws-news-telegram-notifier, Property 8: Message Format Contains Title and Link`

  - [ ]* 6.3 Write unit tests for `telegram.py`
    - Test non-200 response triggers exactly 3 retries with correct backoff delays (mock `time.sleep`)
    - Test successful send on first attempt
    - Test all retries exhausted → error logged, no exception raised
    - _Requirements: 3.3_

- [x] 7. Checkpoint — Ensure all module tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement `handler.py`
  - [x] 8.1 Implement `lambda_handler(event, context)` orchestrating the full poll cycle
    - Load secrets via `secret_store.load_secrets`; raise on failure (routes to DLQ)
    - Parse `FEED_URLS` env var (comma-separated) into list of URLs (Requirement 1.4)
    - For each URL: fetch+parse → filter new entries → send oldest-first → update state
    - Emit structured log record per feed with `feed_url`, `new_entries_count`, `dispatch_status` (Requirement 6.1)
    - _Requirements: 1.1, 1.4, 2.2, 2.3, 2.4, 3.5, 6.1_

  - [ ]* 8.2 Write property test for feed URL config round-trip (Property 3)
    - **Property 3: Feed URL Config Round-Trip**
    - **Validates: Requirements 1.4**
    - `# Feature: aws-news-telegram-notifier, Property 3: Feed URL Config Round-Trip`

  - [ ]* 8.3 Write property test for state updated to most recent entry (Property 7)
    - **Property 7: State Updated to Most Recent Entry**
    - **Validates: Requirements 2.3**
    - `# Feature: aws-news-telegram-notifier, Property 7: State Updated to Most Recent Entry`

  - [ ]* 8.4 Write property test for chronological send order (Property 9)
    - **Property 9: Entries Sent in Chronological Order**
    - **Validates: Requirements 3.5**
    - `# Feature: aws-news-telegram-notifier, Property 9: Entries Sent in Chronological Order`

  - [ ]* 8.5 Write property test for structured log fields (Property 10)
    - **Property 10: Structured Log Contains Required Fields**
    - **Validates: Requirements 6.1**
    - `# Feature: aws-news-telegram-notifier, Property 10: Structured Log Contains Required Fields`

  - [ ]* 8.6 Write integration unit tests for `handler.py`
    - Mock all AWS and Telegram calls; invoke `lambda_handler`; assert correct SSM writes and Telegram call sequence
    - Test bootstrap run: assert exactly one Telegram message sent and state written
    - Test SSM secrets failure: assert exception raised and no Telegram calls made
    - _Requirements: 2.4, 4.3, 6.2_

- [x] 9. Checkpoint — Ensure all Lambda tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Create Lambda deployment package
  - Add `lambda/build.sh` (or `Makefile` target) that installs dependencies into a `package/` directory and zips `lambda/*.py` + dependencies into `lambda/function.zip`
  - Ensure `function.zip` is referenced by the Terraform `filename` attribute
  - _Requirements: 5.1, 5.4_

- [x] 11. Implement Terraform infrastructure in `terraform/`
  - [x] 11.1 Add/update `terraform/variables.tf` with all variables from the design
    - `region`, `name_prefix`, `feed_urls`, `schedule_expression`, `lambda_timeout`, `lambda_memory`, `dlq_retention_days`, `environment`, `project`
    - _Requirements: 5.3_

  - [x] 11.2 Implement IAM role and least-privilege policy in `terraform/main.tf`
    - Lambda execution role with trust policy for `lambda.amazonaws.com`
    - Inline policy granting `ssm:GetParameter` on secrets paths, `ssm:GetParameter` + `ssm:PutParameter` on state path prefix, `kms:Decrypt` on AWS-managed SSM key, `logs:*` on log group, `sqs:SendMessage` on DLQ
    - _Requirements: 4.2, 5.2_

  - [x] 11.3 Implement SQS Dead Letter Queue and CloudWatch Log Group in `terraform/main.tf`
    - SQS queue with `message_retention_seconds` from `dlq_retention_days` variable
    - CloudWatch log group `/aws/lambda/${var.name_prefix}` with appropriate retention
    - Tag both resources with `project` and `environment`
    - _Requirements: 5.2, 5.5, 6.2, 6.3_

  - [x] 11.4 Implement SSM parameters for secrets and state in `terraform/main.tf`
    - `SecureString` parameters for `bot_token` and `chat_id` (placeholder values, updated out-of-band)
    - `String` parameter for state prefix (initial empty value)
    - Tag with `project` and `environment`
    - _Requirements: 4.1, 5.2, 5.5_

  - [x] 11.5 Implement Lambda function resource in `terraform/main.tf`
    - `aws_lambda_function` using `function.zip`, Python runtime, IAM role, environment variables, timeout, memory, DLQ config
    - _Requirements: 5.2, 5.4, 6.4_

  - [x] 11.6 Implement EventBridge scheduled rule and Lambda permission in `terraform/main.tf`
    - `aws_cloudwatch_event_rule` with `schedule_expression` variable
    - `aws_cloudwatch_event_target` pointing to Lambda ARN
    - `aws_lambda_permission` allowing EventBridge to invoke the function
    - Tag rule with `project` and `environment`
    - _Requirements: 1.1, 5.2, 5.5_

- [x] 12. Final checkpoint — Validate full implementation
  - Ensure all Python tests pass, ask the user if questions arise.
  - Run `terraform validate` and `terraform fmt` in the `terraform/` directory.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Property tests use `hypothesis` and are tagged with `# Feature: aws-news-telegram-notifier, Property N: ...`
- All Terraform files go in `terraform/` per workspace conventions
- Lambda source lives in `lambda/` at the repo root
- `function.zip` should be built before `terraform apply`
