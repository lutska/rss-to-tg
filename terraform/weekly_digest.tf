# ═══════════════════════════════════════════════════════════════════════════
# WEEKLY DIGEST SYSTEM (New Addition - Parallel to Existing Hourly System)
# ═══════════════════════════════════════════════════════════════════════════
# Toggle this entire system with: var.enable_weekly_digest

# ─── DynamoDB Table for Weekly Digest ────────────────────────────────────────

resource "aws_dynamodb_table" "weekly_digest_entries" {
  count = var.enable_weekly_digest ? 1 : 0

  name         = "${var.name_prefix}-weekly-entries"
  billing_mode = "PAY_PER_REQUEST"

  attribute {
    name = "feed_hash"
    type = "S"
  }

  attribute {
    name = "entry_guid"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  hash_key  = "feed_hash"
  range_key = "entry_guid"

  global_secondary_index {
    name            = "TimestampIndex"
    hash_key        = "feed_hash"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = merge(local.common_tags, {
    system = "weekly-digest"
  })
}

# ─── CloudWatch Log Groups ───────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "weekly_collector_logs" {
  count = var.enable_weekly_digest ? 1 : 0

  name              = "/aws/lambda/${var.name_prefix}-weekly-collector"
  retention_in_days = 14

  tags = merge(local.common_tags, {
    system = "weekly-digest"
  })
}

resource "aws_cloudwatch_log_group" "weekly_digest_logs" {
  count = var.enable_weekly_digest ? 1 : 0

  name              = "/aws/lambda/${var.name_prefix}-weekly-digest"
  retention_in_days = 14

  tags = merge(local.common_tags, {
    system = "weekly-digest"
  })
}

# ─── Lambda Functions ────────────────────────────────────────────────────────

resource "aws_lambda_function" "weekly_collector" {
  count = var.enable_weekly_digest ? 1 : 0

  function_name    = "${var.name_prefix}-weekly-collector"
  filename         = "${path.module}/../lambda/weekly-digest.zip"
  source_code_hash = try(filebase64sha256("${path.module}/../lambda/weekly-digest.zip"), "")
  runtime          = "python3.12"
  handler          = "collector.lambda_handler"
  role             = aws_iam_role.lambda_exec.arn
  timeout          = var.lambda_timeout
  memory_size      = var.lambda_memory

  environment {
    variables = {
      FEED_URLS             = var.feed_urls
      SSM_STATE_PATH_PREFIX = "/notifier/state/weekly"
      DYNAMODB_TABLE_NAME   = aws_dynamodb_table.weekly_digest_entries[0].name
      ENTRY_TTL_DAYS        = tostring(var.entry_ttl_days)
      LOG_LEVEL             = "INFO"
    }
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.dlq.arn
  }

  depends_on = [aws_cloudwatch_log_group.weekly_collector_logs]

  tags = merge(local.common_tags, {
    system = "weekly-digest"
  })
}

resource "aws_lambda_function" "weekly_digest_sender" {
  count = var.enable_weekly_digest ? 1 : 0

  function_name    = "${var.name_prefix}-weekly-digest"
  filename         = "${path.module}/../lambda/weekly-digest.zip"
  source_code_hash = try(filebase64sha256("${path.module}/../lambda/weekly-digest.zip"), "")
  runtime          = "python3.12"
  handler          = "digest_sender.lambda_handler"
  role             = aws_iam_role.lambda_exec.arn
  timeout          = var.lambda_timeout
  memory_size      = var.lambda_memory

  environment {
    variables = {
      FEED_URLS           = var.feed_urls
      SSM_BOT_TOKEN_PATH  = aws_ssm_parameter.bot_token.name
      SSM_CHAT_ID_PATH    = aws_ssm_parameter.chat_id.name
      DYNAMODB_TABLE_NAME = aws_dynamodb_table.weekly_digest_entries[0].name
      DIGEST_TITLE        = var.digest_title
      DIGEST_DAYS         = tostring(var.digest_days)
      LOG_LEVEL           = "INFO"
    }
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.dlq.arn
  }

  depends_on = [aws_cloudwatch_log_group.weekly_digest_logs]

  tags = merge(local.common_tags, {
    system = "weekly-digest"
  })
}

# ─── EventBridge Schedules ───────────────────────────────────────────────────

# Primary collection (2 hours before digest)
resource "aws_cloudwatch_event_rule" "weekly_collector_primary" {
  count = var.enable_weekly_digest ? 1 : 0

  name                = "${var.name_prefix}-weekly-collector-primary"
  description         = "Weekly digest collector - primary (2h before digest)"
  schedule_expression = var.collector_schedule_primary

  tags = merge(local.common_tags, {
    system = "weekly-digest"
  })
}

resource "aws_cloudwatch_event_target" "weekly_collector_primary" {
  count = var.enable_weekly_digest ? 1 : 0

  rule = aws_cloudwatch_event_rule.weekly_collector_primary[0].name
  arn  = aws_lambda_function.weekly_collector[0].arn
}

resource "aws_lambda_permission" "weekly_collector_primary" {
  count = var.enable_weekly_digest ? 1 : 0

  statement_id  = "AllowEventBridgePrimary"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.weekly_collector[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.weekly_collector_primary[0].arn
}

# Backup collection (1 hour before digest)
resource "aws_cloudwatch_event_rule" "weekly_collector_backup" {
  count = var.enable_weekly_digest ? 1 : 0

  name                = "${var.name_prefix}-weekly-collector-backup"
  description         = "Weekly digest collector - backup (1h before digest)"
  schedule_expression = var.collector_schedule_backup

  tags = merge(local.common_tags, {
    system = "weekly-digest"
  })
}

resource "aws_cloudwatch_event_target" "weekly_collector_backup" {
  count = var.enable_weekly_digest ? 1 : 0

  rule = aws_cloudwatch_event_rule.weekly_collector_backup[0].name
  arn  = aws_lambda_function.weekly_collector[0].arn
}

resource "aws_lambda_permission" "weekly_collector_backup" {
  count = var.enable_weekly_digest ? 1 : 0

  statement_id  = "AllowEventBridgeBackup"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.weekly_collector[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.weekly_collector_backup[0].arn
}

# Digest sender
resource "aws_cloudwatch_event_rule" "weekly_digest" {
  count = var.enable_weekly_digest ? 1 : 0

  name                = "${var.name_prefix}-weekly-digest-schedule"
  description         = "Weekly digest sender"
  schedule_expression = var.digest_schedule_expression

  tags = merge(local.common_tags, {
    system = "weekly-digest"
  })
}

resource "aws_cloudwatch_event_target" "weekly_digest" {
  count = var.enable_weekly_digest ? 1 : 0

  rule = aws_cloudwatch_event_rule.weekly_digest[0].name
  arn  = aws_lambda_function.weekly_digest_sender[0].arn
}

resource "aws_lambda_permission" "weekly_digest" {
  count = var.enable_weekly_digest ? 1 : 0

  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.weekly_digest_sender[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.weekly_digest[0].arn
}
