output "cognito_user_pool_id" {
  value = module.cognito.user_pool_id
}

output "cognito_app_client_id" {
  value = module.cognito.app_client_id
}

output "cognito_hosted_ui_url" {
  value = module.cognito.hosted_ui_base_url
}

output "rds_endpoint" {
  value       = try(module.rds[0].endpoint, null)
  description = "Set when enable_rds = true"
}

output "database_url_secret_arn" {
  value       = try(module.rds[0].secret_arn, null)
  sensitive   = true
  description = "Secrets Manager ARN for DATABASE_URL"
}

output "next_steps" {
  value = <<-EOT
    1. Create a Cognito user: aws cognito-idp admin-create-user --user-pool-id ${module.cognito.user_pool_id} --username reviewer@example.com
    2. Set DATABASE_URL (local Docker or RDS secret) and run: uv run alembic upgrade head
    3. Load content: uv run python scripts/load_curated_to_postgres.py
    4. Implement reviewer API per docs/plans/2026-05-16-reviewer-portal.md
  EOT
}
