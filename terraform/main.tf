terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}

provider "aws" {
  region = var.region
}

locals {
  common_tags = {
    project     = var.project
    environment = var.environment
  }
}

# ─── IAM ────────────────────────────────────────────────────────────────────

resource "aws_iam_role" "lambda_exec" {
  name = "${var.name_prefix}-lambda-exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.name_prefix}-lambda-policy"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["ssm:GetParameter"]
        Resource = [
          "arn:aws:ssm:${var.region}:*:parameter/notifier/telegram/bot_token",
          "arn:aws:ssm:${var.region}:*:parameter/notifier/telegram/chat_id",
          "arn:aws:ssm:${var.region}:*:parameter/notifier/state/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["ssm:PutParameter"]
        Resource = "arn:aws:ssm:${var.region}:*:parameter/notifier/state/*"
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.lambda_logs.arn}:*"
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.dlq.arn
      }
    ]
  })
}

# ─── SQS Dead Letter Queue ───────────────────────────────────────────────────

resource "aws_sqs_queue" "dlq" {
  name                      = "${var.name_prefix}-dlq"
  message_retention_seconds = var.dlq_retention_days * 86400

  tags = local.common_tags
}

# ─── CloudWatch Log Group ────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.name_prefix}"
  retention_in_days = 14

  tags = local.common_tags
}

# ─── SSM Parameters ──────────────────────────────────────────────────────────

resource "aws_ssm_parameter" "bot_token" {
  name  = "/notifier/telegram/bot_token"
  type  = "SecureString"
  value = "PLACEHOLDER_BOT_TOKEN"

  tags = local.common_tags

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "chat_id" {
  name  = "/notifier/telegram/chat_id"
  type  = "SecureString"
  value = "PLACEHOLDER_CHAT_ID"

  tags = local.common_tags

  lifecycle {
    ignore_changes = [value]
  }
}

# ─── Lambda Function ─────────────────────────────────────────────────────────

resource "aws_lambda_function" "notifier" {
  function_name    = var.name_prefix
  filename         = "${path.module}/../lambda/function.zip"
  source_code_hash = try(filebase64sha256("${path.module}/../lambda/function.zip"), "")
  runtime          = "python3.12"
  handler          = "handler.lambda_handler"
  role             = aws_iam_role.lambda_exec.arn
  timeout          = var.lambda_timeout
  memory_size      = var.lambda_memory

  environment {
    variables = {
      FEED_URLS             = var.feed_urls
      SSM_BOT_TOKEN_PATH    = aws_ssm_parameter.bot_token.name
      SSM_CHAT_ID_PATH      = aws_ssm_parameter.chat_id.name
      SSM_STATE_PATH_PREFIX = "/notifier/state"
      LOG_LEVEL             = "INFO"
    }
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.dlq.arn
  }

  depends_on = [aws_cloudwatch_log_group.lambda_logs]

  tags = local.common_tags
}

# ─── EventBridge Schedule ────────────────────────────────────────────────────

resource "aws_cloudwatch_event_rule" "schedule" {
  name                = "${var.name_prefix}-schedule"
  schedule_expression = var.schedule_expression

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "lambda" {
  rule = aws_cloudwatch_event_rule.schedule.name
  arn  = aws_lambda_function.notifier.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.notifier.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.schedule.arn
}
