variable "region" {
  type        = string
  default     = "eu-west-1"
  description = "AWS deployment region"
}

variable "name_prefix" {
  type        = string
  default     = "rss-to-tg"
  description = "Prefix for all resource names"
}

variable "feed_urls" {
  type        = string
  default     = "https://aws.amazon.com/about-aws/whats-new/recent/feed/"
  description = "Comma-separated list of RSS feed URLs"
}

variable "schedule_expression" {
  type        = string
  default     = "rate(60 minutes)"
  description = "EventBridge schedule expression for the polling interval"
}

variable "lambda_timeout" {
  type        = number
  default     = 60
  description = "Lambda function timeout in seconds"
}

variable "lambda_memory" {
  type        = number
  default     = 128
  description = "Lambda function memory size in MB"
}

variable "dlq_retention_days" {
  type        = number
  default     = 14
  description = "SQS Dead Letter Queue message retention period in days"
}

variable "environment" {
  type        = string
  default     = "dev"
  description = "Environment tag value"
}

variable "project" {
  type        = string
  default     = "rss-to-tg"
  description = "Project tag value"
}

# ═══════════════════════════════════════════════════════════════════════════
# NOTIFICATION SYSTEM CONFIGURATION (Choose: daily, weekly, or both)
# ═══════════════════════════════════════════════════════════════════════════

variable "enable_daily_notifications" {
  type        = bool
  default     = false
  description = "Enable daily instant notifications (sends immediately when entries are found)"
}

variable "enable_weekly_digest" {
  type        = bool
  default     = true
  description = "Enable weekly digest system (collects entries throughout the week, sends on Sunday)"
}

variable "daily_collector_schedule" {
  type        = string
  default     = "rate(60 minutes)"
  description = "Polling interval for daily notifications (e.g., 'rate(60 minutes)' or 'cron(0 * * * ? *)')"
}

variable "collector_schedule_primary" {
  type        = string
  default     = "cron(0 0 ? * * *)"
  description = "Primary collection schedule - runs daily at midnight UTC to collect throughout the week"
}

variable "collector_schedule_backup" {
  type        = string
  default     = "cron(0 6 ? * * *)"
  description = "Backup collection schedule - runs daily at 6 AM UTC for redundancy"
}

variable "digest_schedule_expression" {
  type        = string
  default     = "cron(0 21 ? * SUN *)"
  description = "Weekly digest delivery schedule (Sunday at 9 PM UTC)"
}

variable "digest_title" {
  type        = string
  default     = "AWS Weekly"
  description = "Title for the weekly digest"
}

variable "digest_days" {
  type        = number
  default     = 7
  description = "Number of days to include in digest"
}

variable "entry_ttl_days" {
  type        = number
  default     = 14
  description = "DynamoDB entry TTL in days"
}
