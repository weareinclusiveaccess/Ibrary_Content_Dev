variable "aws_region" {
  type    = string
  default = "eu-west-1"
}

variable "aws_account_id" {
  type        = string
  description = "Expected AWS account (verified after assume_role). IBrary content dev: 681986854278"
  default     = "681986854278"
}

variable "aws_profile" {
  type        = string
  description = "Usually leave empty. MFA profiles break Terraform — run scripts/terraform-aws-env.sh first."
  default     = ""
}

variable "assume_role_arn" {
  type        = string
  description = "Only when NOT using aws_profile. IAM role ARN for Terraform to assume directly."
  default     = ""
}

variable "assume_role_session_name" {
  type    = string
  default = "ibrary-terraform-review-portal"
}

variable "project_name" {
  type    = string
  default = "ibrary"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "cognito_domain_prefix" {
  type        = string
  description = "Globally unique Cognito domain prefix"
}

variable "cognito_callback_urls" {
  type    = list(string)
  default = ["http://localhost:5173/"]
}

variable "cognito_logout_urls" {
  type    = list(string)
  default = ["http://localhost:5173/"]
}

variable "cognito_create_admin_iam_policy" {
  type        = bool
  description = "Requires iam:CreatePolicy on content-dev. Leave false; attach cognito_admin_api_policy_json manually."
  default     = false
}

variable "enable_rds" {
  type        = bool
  description = "Provision RDS PostgreSQL (false = Cognito only; use local Docker Postgres)"
  default     = false
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "RDS master password (required when enable_rds = true)"
  default     = ""
}

variable "db_allowed_cidr_blocks" {
  type        = list(string)
  description = "IPs allowed to connect to RDS (use your public IP /32 for dev)"
  default     = ["0.0.0.0/0"]
}

variable "vpc_id" {
  type        = string
  description = "Default VPC ID (required when enable_rds = true)"
  default     = ""
}

variable "subnet_ids" {
  type        = list(string)
  description = "Subnet IDs for RDS (default VPC subnets when enable_rds = true)"
  default     = []
}

# --- Reviewer portal hosting (EC2 + S3 + CloudFront + ECR + SSM + DynamoDB) ---

variable "enable_portal_hosting" {
  type        = bool
  description = "Provision full portal hosting (ECR, S3 UI, CloudFront, EC2, SSM, DynamoDB)"
  default     = false
}

variable "portal_ui_bucket_name" {
  type        = string
  description = "Globally unique S3 bucket name for the UI dist (default uses project+env+account suffix below)"
  default     = ""
}

variable "portal_ecr_repo_name" {
  type        = string
  description = "ECR repository name"
  default     = "ibrary-review-api"
}

variable "portal_instance_type" {
  type    = string
  default = "t3.micro"
}

variable "portal_publish_enabled" {
  type        = string
  description = "Initial value for PORTAL_PUBLISH_ENABLED in the container. Keep 'false' until JWT auth ships."
  default     = "false"
}

variable "portal_ssm_secrets" {
  type        = map(string)
  sensitive   = true
  description = <<-EOT
    Initial SSM SecureString values seeded into /ibrary/review/* on first apply.
    The container loads these as env vars at boot. Rotate via the AWS Console or
    `aws ssm put-parameter ... --overwrite` after first apply — terraform won't
    reset existing values on subsequent applies.

    Scope: portal-only. Do NOT seed pipeline secrets (OPENAI_API_KEY,
    ANTHROPIC_API_KEY, LANGSMITH_API_KEY, etc.) here — the portal does not
    call those services and they should not be reachable from the EC2 role.
  EOT
  default = {
    # Postgres / Neon connection string the portal reads curated content from
    DATABASE_URL_REVIEW = "REPLACE_ME"
    # Cognito (Cognito module outputs the real values — overwrite via SSM after apply)
    COGNITO_USER_POOL_ID      = "REPLACE_ME"
    COGNITO_APP_CLIENT_ID     = "REPLACE_ME"
    COGNITO_APP_CLIENT_SECRET = "REPLACE_ME"
  }
}

variable "dynamodb_table_name" {
  type        = string
  description = "DynamoDB table name (matches src/ibrary/serving/dynamodb_writer.py)"
  default     = "CuratedContent"
}

variable "images_bucket" {
  type        = string
  description = "Existing S3 bucket holding textbook images — instance role gets read access"
  default     = "ibrary-content"
}
