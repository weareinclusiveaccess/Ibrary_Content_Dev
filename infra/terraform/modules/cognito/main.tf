resource "aws_cognito_user_pool" "reviewers" {
  name = "${var.project_name}-${var.environment}-reviewers"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length    = 10
    require_lowercase = true
    require_numbers   = true
    require_symbols   = false
    require_uppercase = true
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
    Purpose     = "reviewer-portal"
  }
}

resource "aws_cognito_user_pool_client" "reviewer_spa" {
  name         = "${var.project_name}-${var.environment}-reviewer-spa"
  user_pool_id = aws_cognito_user_pool.reviewers.id

  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  supported_identity_providers = ["COGNITO"]

  callback_urls = var.callback_urls
  logout_urls   = var.logout_urls

  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["email", "openid", "profile"]

  prevent_user_existence_errors = "ENABLED"
}

resource "aws_cognito_user_pool_domain" "reviewers" {
  domain       = var.domain_prefix
  user_pool_id = aws_cognito_user_pool.reviewers.id
}
