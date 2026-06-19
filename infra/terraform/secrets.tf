# AWS Secrets Manager — all sensitive credentials in one secret

resource "aws_secretsmanager_secret" "app" {
  name                    = "finpilot/${var.environment}/app"
  recovery_window_in_days = var.environment == "production" ? 30 : 0
  description             = "FinPilot application secrets — rotated via Lambda"
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    DATABASE_URL      = "postgresql+asyncpg://finpilot:${var.db_password}@${aws_db_instance.main.endpoint}/finpilot"
    REDIS_URL         = "rediss://:@${aws_elasticache_replication_group.main.primary_endpoint_address}:6379/0"
    JWT_SECRET_KEY    = "<rotate-me>"
    ANTHROPIC_API_KEY = "<set-in-console>"
    PII_TOKEN_KEY     = "<rotate-me>"
    IPINFO_TOKEN      = "<set-in-console>"
  })

  lifecycle {
    # Prevent Terraform from overwriting secrets after initial creation
    ignore_changes = [secret_string]
  }
}
