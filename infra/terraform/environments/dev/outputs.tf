output "aws_account_id" {
  value       = data.aws_caller_identity.current.account_id
  description = "Should be 681986854278 when using content-dev role"
}

output "aws_caller_arn" {
  value = data.aws_caller_identity.current.arn
}

output "cognito_user_pool_id" {
  value = module.cognito.user_pool_id
}

output "cognito_app_client_id" {
  value = module.cognito.app_client_id
}

output "cognito_hosted_ui_url" {
  value = module.cognito.hosted_ui_base_url
}

output "cognito_group_admin" {
  value = module.cognito.group_admin_name
}

output "cognito_group_reviewer" {
  value = module.cognito.group_reviewer_name
}

output "cognito_admin_api_policy_arn" {
  value = module.cognito.cognito_admin_api_policy_arn
}

output "cognito_admin_api_policy_json" {
  value       = module.cognito.cognito_admin_api_policy_json
  description = "Attach to API role or ask admin to grant cognito-idp admin on this pool"
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
    Cognito (after terraform apply):
      1. Create admin: aws cognito-idp admin-create-user --user-pool-id ${module.cognito.user_pool_id} --username admin@your.org --user-attributes Name=email,Value=admin@your.org Name=email_verified,Value=true
      2. Set password: aws cognito-idp admin-set-user-password --user-pool-id ${module.cognito.user_pool_id} --username admin@your.org --password 'CHANGE_ME' --permanent
      3. Add to group: aws cognito-idp admin-add-user-to-group --user-pool-id ${module.cognito.user_pool_id} --username admin@your.org --group-name ${module.cognito.group_admin_name}
      4. Or use portal: sign in as admin → Manage users (after COGNITO_USER_POOL_ID is set on API)

    Data:
      5. DATABASE_URL / DATABASE_URL_REVIEW + alembic upgrade head
      6. uv run python scripts/load_curated_to_postgres.py

    Hosting (~$6–12/mo): see infra/HOSTING.md
  EOT
}

# --- Reviewer portal hosting outputs (set when enable_portal_hosting = true) ---

output "portal_ecr_repository_url" {
  value       = try(module.ecr[0].repository_url, null)
  description = "Docker push target: <this>:<tag>"
}

output "portal_ui_bucket" {
  value       = try(module.s3_ui[0].bucket_name, null)
  description = "aws s3 sync review-ui/dist s3://<this>"
}

output "portal_cloudfront_url" {
  value       = try("https://${module.cloudfront[0].distribution_domain_name}", null)
  description = "Public reviewer portal URL"
}

output "portal_cloudfront_distribution_id" {
  value = try(module.cloudfront[0].distribution_id, null)
}

output "portal_instance_id" {
  value       = try(module.ec2_portal[0].instance_id, null)
  description = "EC2 instance ID for make portal-start/stop"
}

output "portal_dynamodb_table_arn" {
  value = try(module.dynamodb[0].table_arn, null)
}

output "portal_ssm_path_prefix" {
  value = try(module.ssm_params[0].parameter_path_prefix, null)
}
