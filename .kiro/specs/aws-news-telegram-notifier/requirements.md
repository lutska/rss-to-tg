# Requirements Document

## Introduction

This feature implements an automated notification system that monitors AWS news and announcements via RSS feeds and delivers new items to a Telegram channel or bot. The system runs on AWS infrastructure provisioned with Terraform, using a serverless architecture (Lambda + EventBridge) to periodically poll RSS feeds, detect new entries, and forward them to Telegram via the Bot API.

## Glossary

- **Notifier**: The AWS Lambda function responsible for polling RSS feeds and dispatching Telegram messages
- **RSS_Feed**: An XML-formatted web feed providing AWS news and announcements (e.g., https://aws.amazon.com/about-aws/whats-new/recent/feed/)
- **Telegram_Bot**: A Telegram bot configured via BotFather that sends messages to a target Telegram channel
- **State_Store**: An AWS SSM Parameter Store parameter that persists the last-seen RSS entry identifier (GUID or link) per feed URL to avoid duplicate notifications
- **Scheduler**: An Amazon EventBridge rule that triggers the Notifier on a defined schedule
- **Dead_Letter_Queue**: An Amazon SQS queue that captures failed Lambda invocation events for later inspection
- **Secret_Store**: AWS Secrets Manager or SSM Parameter Store holding the Telegram bot token and chat ID

## Requirements

### Requirement 1: RSS Feed Polling

**User Story:** As a DevOps engineer, I want the system to periodically poll AWS RSS feeds, so that new announcements are detected automatically without manual intervention.

#### Acceptance Criteria

1. THE Scheduler SHALL trigger the Notifier at a configurable interval (default: every 60 minutes).
2. WHEN the Notifier is triggered, THE Notifier SHALL fetch the RSS_Feed from the configured URL and parse it into a list of feed entries.
3. IF the RSS_Feed URL is unreachable or returns a non-200 HTTP status, THEN THE Notifier SHALL log the error and exit without modifying the State_Store.
4. THE Notifier SHALL support configuration of one or more RSS_Feed URLs via environment variables.
5. WHEN parsing the RSS_Feed, THE Notifier SHALL extract at minimum the entry title, URL link, and publication date for each item.

### Requirement 2: Duplicate Detection

**User Story:** As a DevOps engineer, I want the system to track which entries have already been sent, so that users do not receive duplicate notifications.

#### Acceptance Criteria

1. THE State_Store SHALL persist the identifier (GUID or link) of the most recently processed RSS entry per feed URL.
2. WHEN the Notifier fetches a feed, THE Notifier SHALL compare each entry identifier against the State_Store and process only entries newer than the stored identifier.
3. AFTER successfully dispatching all new entries, THE Notifier SHALL update the State_Store with the identifier of the most recent entry processed.
4. IF the State_Store contains no record for a given feed URL, THEN THE Notifier SHALL send only the most recent entry and record its identifier (bootstrap behaviour).

### Requirement 3: Telegram Notification Delivery

**User Story:** As a team member, I want to receive formatted AWS news notifications in a Telegram channel, so that I stay informed about relevant AWS updates.

#### Acceptance Criteria

1. WHEN a new RSS entry is detected, THE Notifier SHALL send a message to the configured Telegram channel using the Telegram Bot API `sendMessage` endpoint.
2. THE Notifier SHALL format each message to include the entry title and the entry URL link.
3. IF the Telegram Bot API returns a non-200 response, THEN THE Notifier SHALL log the error details and retry the request up to 3 times with exponential back-off before marking the entry as failed.
4. THE Notifier SHALL retrieve the Telegram bot token and chat ID exclusively from the Secret_Store at runtime.
5. WHERE multiple new entries are detected in a single poll, THE Notifier SHALL send one Telegram message per entry in chronological order (oldest first).

### Requirement 4: Secrets and Configuration Management

**User Story:** As a DevOps engineer, I want all sensitive credentials stored securely, so that the Telegram bot token and chat ID are never exposed in source code or environment variables in plain text.

#### Acceptance Criteria

1. THE Secret_Store SHALL hold the Telegram bot token and target chat ID as separate secret values.
2. THE Notifier SHALL be granted least-privilege IAM permissions to read only the required secrets from the Secret_Store.
3. IF the Secret_Store is unavailable or the secret value is missing, THEN THE Notifier SHALL log the error and terminate without sending any messages.
4. THE Notifier SHALL accept the RSS_Feed URL(s) and polling schedule as non-sensitive Terraform-managed environment variables.

### Requirement 5: Infrastructure Provisioning

**User Story:** As a DevOps engineer, I want all system components defined as Terraform code, so that the infrastructure is reproducible, version-controlled, and deployable to any AWS account.

#### Acceptance Criteria

1. THE Notifier infrastructure SHALL be defined entirely in Terraform files located in the `terraform/` directory.
2. THE Terraform configuration SHALL provision: a Lambda function (Python runtime), an EventBridge scheduled rule, an SSM Parameter Store parameter (State_Store), an SSM Parameter or Secrets Manager secret (Secret_Store), an IAM role with least-privilege policies, and a Dead_Letter_Queue.
3. THE Terraform configuration SHALL expose configurable input variables for: AWS region, polling interval, RSS feed URL(s), Lambda runtime, and resource name prefix.
4. WHEN `terraform apply` is executed, THE Terraform configuration SHALL create all required resources without manual post-deployment steps.
5. THE Terraform configuration SHALL tag all provisioned resources with at minimum a `project` tag and an `environment` tag.

### Requirement 6: Observability and Error Handling

**User Story:** As a DevOps engineer, I want the system to log its activity and route failures to a dead-letter queue, so that I can diagnose issues without losing failed events.

#### Acceptance Criteria

1. THE Notifier SHALL emit structured log entries to Amazon CloudWatch Logs for each poll cycle, including feed URL, number of new entries found, and dispatch status.
2. WHEN the Notifier raises an unhandled exception, THE Scheduler SHALL route the failed invocation event to the Dead_Letter_Queue.
3. THE Dead_Letter_Queue SHALL retain failed messages for a configurable retention period (default: 14 days).
4. THE Terraform configuration SHALL set a configurable Lambda timeout (default: 60 seconds) and memory size (default: 128 MB).

### Requirement 7: RSS Feed Parsing Round-Trip

**User Story:** As a DevOps engineer, I want the RSS parser to be reliable and verifiable, so that feed data is never silently corrupted or lost.

#### Acceptance Criteria

1. WHEN a valid RSS_Feed XML document is provided, THE Notifier SHALL parse it into a structured list of feed entry objects.
2. IF an RSS_Feed XML document is malformed, THEN THE Notifier SHALL log a descriptive parse error and skip that feed for the current poll cycle.
3. FOR ALL valid RSS_Feed XML documents, parsing the document and re-serialising the extracted entry fields SHALL produce values equivalent to those in the original document (round-trip property).
