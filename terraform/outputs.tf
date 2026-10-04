# ─── Lambda Outputs ──────────────────────────────────────────────────────────

output "lambda_function_arn" {
  description = "ARN of the RSS notifier Lambda function"
  value       = aws_lambda_function.notifier.arn
}

output "lambda_function_name" {
  description = "Name of the RSS notifier Lambda function"
  value       = aws_lambda_function.notifier.function_name
}

# ─── EventBridge Outputs ─────────────────────────────────────────────────────

output "eventbridge_rule_name" {
  description = "Name of the EventBridge rule that triggers Lambda"
  value       = var.enable_daily_notifications ? aws_cloudwatch_event_rule.schedule[0].name : "Daily notifications disabled"
}

output "eventbridge_rule_arn" {
  description = "ARN of the EventBridge rule"
  value       = var.enable_daily_notifications ? aws_cloudwatch_event_rule.schedule[0].arn : "Daily notifications disabled"
}

output "eventbridge_schedule_expression" {
  description = "The schedule expression for the EventBridge rule (cron format)"
  value       = var.enable_daily_notifications ? aws_cloudwatch_event_rule.schedule[0].schedule_expression : "Daily notifications disabled"
}

# ─── SQS Dead Letter Queue Outputs ───────────────────────────────────────────

output "dlq_url" {
  description = "URL of the Dead Letter Queue (SQS)"
  value       = aws_sqs_queue.dlq.url
}

output "dlq_arn" {
  description = "ARN of the Dead Letter Queue (SQS)"
  value       = aws_sqs_queue.dlq.arn
}

# ─── CloudWatch Logs Outputs ─────────────────────────────────────────────────

output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group for Lambda logs"
  value       = aws_cloudwatch_log_group.lambda_logs.name
}

# ─── SSM Parameters Outputs ──────────────────────────────────────────────────

output "ssm_bot_token_parameter_name" {
  description = "SSM Parameter name for Telegram bot token"
  value       = aws_ssm_parameter.bot_token.name
}

output "ssm_chat_id_parameter_name" {
  description = "SSM Parameter name for Telegram chat ID"
  value       = aws_ssm_parameter.chat_id.name
}

# ─── Weekly Digest Outputs (if enabled) ──────────────────────────────────────

output "weekly_digest_lambda_arn" {
  description = "ARN of the weekly digest Lambda function"
  value       = var.enable_weekly_digest ? aws_lambda_function.weekly_digest_sender[0].arn : "Weekly digest disabled"
}

output "weekly_digest_eventbridge_rule_name" {
  description = "Name of the EventBridge rule that triggers weekly digest"
  value       = var.enable_weekly_digest ? aws_cloudwatch_event_rule.weekly_digest[0].name : "Weekly digest disabled"
}

output "dynamodb_table_name" {
  description = "DynamoDB table name for weekly digest entries"
  value       = var.enable_weekly_digest ? aws_dynamodb_table.weekly_digest_entries[0].name : "Weekly digest disabled"
}
