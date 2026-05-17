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
  value = "https://${aws_cognito_user_pool_domain.reviewers.domain}.auth.${data.aws_region.current.name}.amazoncognito.com"
}

data "aws_region" "current" {}
