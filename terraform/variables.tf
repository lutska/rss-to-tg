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
