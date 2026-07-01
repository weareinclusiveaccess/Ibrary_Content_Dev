output "user_pool_id" {
  value = aws_cognito_user_pool.reviewers.id
}

output "user_pool_arn" {
  value = aws_cognito_user_pool.reviewers.arn
}

output "app_client_id" {
  value = aws_cognito_user_pool_client.reviewer_spa.id
}

output "hosted_ui_base_url" {
  value = "https://${var.domain_prefix}.auth.${data.aws_region.current.name}.amazoncognito.com"
}

output "group_admin_name" {
  value = aws_cognito_user_group.admin.name
}

output "group_reviewer_name" {
  value = aws_cognito_user_group.reviewer.name
}

output "cognito_admin_api_policy_arn" {
  value       = try(aws_iam_policy.cognito_admin_api[0].arn, null)
  description = "Attach to reviewer API IAM role for AdminCreateUser / ListUsers (null if create_admin_iam_policy = false)"
}

output "cognito_admin_api_policy_json" {
  value       = data.aws_iam_policy_document.cognito_admin_api.json
  description = "Use when create_admin_iam_policy = false — attach manually to API role or local credentials"
}

data "aws_region" "current" {}
