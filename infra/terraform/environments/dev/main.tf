data "aws_vpc" "default" {
  count   = var.enable_rds ? 1 : 0
  default = true
}

data "aws_subnets" "default" {
  count = var.enable_rds ? 1 : 0
  filter {
    name   = "vpc-id"
    values = [local.vpc_id]
  }
}

locals {
  vpc_id     = var.enable_rds ? coalesce(var.vpc_id, try(data.aws_vpc.default[0].id, "")) : ""
  subnet_ids = var.enable_rds ? (length(var.subnet_ids) > 0 ? var.subnet_ids : data.aws_subnets.default[0].ids) : []
}

module "cognito" {
  source = "../../modules/cognito"

  project_name  = var.project_name
  environment   = var.environment
  domain_prefix = var.cognito_domain_prefix

  callback_urls = var.cognito_callback_urls
  logout_urls   = var.cognito_logout_urls

  create_admin_iam_policy = var.cognito_create_admin_iam_policy
}

module "rds" {
  count  = var.enable_rds ? 1 : 0
  source = "../../modules/rds"

  project_name = var.project_name
  environment  = var.environment

  vpc_id     = local.vpc_id
  subnet_ids = local.subnet_ids

  db_password         = var.db_password
  allowed_cidr_blocks = var.db_allowed_cidr_blocks
  publicly_accessible = true
}

# --- Reviewer portal hosting --------------------------------------------------
# Toggle via `enable_portal_hosting = true`. Apply order inside the DAG:
#   dynamodb + ecr + ssm_params → s3_ui + ec2_portal → cloudfront (writes S3 OAC bucket policy)

module "dynamodb" {
  count  = var.enable_portal_hosting ? 1 : 0
  source = "../../modules/dynamodb"

  project_name = var.project_name
  environment  = var.environment
  table_name   = var.dynamodb_table_name
}

module "ecr" {
  count  = var.enable_portal_hosting ? 1 : 0
  source = "../../modules/ecr"

  project_name    = var.project_name
  environment     = var.environment
  repository_name = var.portal_ecr_repo_name
}

module "ssm_params" {
  count  = var.enable_portal_hosting ? 1 : 0
  source = "../../modules/ssm_params"

  project_name = var.project_name
  environment  = var.environment
  secrets      = var.portal_ssm_secrets
}

locals {
  default_ui_bucket_name = "${var.project_name}-review-ui-${var.environment}-${data.aws_caller_identity.current.account_id}"
  ui_bucket_name         = var.portal_ui_bucket_name != "" ? var.portal_ui_bucket_name : local.default_ui_bucket_name

  ecr_image_uri = var.enable_portal_hosting ? "${module.ecr[0].repository_url}:latest" : ""
}

module "s3_ui" {
  count  = var.enable_portal_hosting ? 1 : 0
  source = "../../modules/s3_ui"

  project_name = var.project_name
  environment  = var.environment
  bucket_name  = local.ui_bucket_name
}

module "ec2_portal" {
  count  = var.enable_portal_hosting ? 1 : 0
  source = "../../modules/ec2_portal"

  project_name           = var.project_name
  environment            = var.environment
  instance_type          = var.portal_instance_type
  ecr_image_uri          = local.ecr_image_uri
  ssm_path_prefix        = module.ssm_params[0].parameter_path_prefix
  portal_publish_enabled = var.portal_publish_enabled
  dynamodb_table_arn     = module.dynamodb[0].table_arn
  images_bucket          = var.images_bucket
  images_prefix          = "biology"
  # IAM policy ARN is omitted when cognito_create_admin_iam_policy = false (outputs null).
  # Do NOT use coalesce(.., "") — Terraform's coalesce drops both null and "", so you'd get no value.
  cognito_admin_policy_arn = module.cognito.cognito_admin_api_policy_arn != null ? module.cognito.cognito_admin_api_policy_arn : ""
}

module "cloudfront" {
  count  = var.enable_portal_hosting ? 1 : 0
  source = "../../modules/cloudfront"

  project_name                   = var.project_name
  environment                    = var.environment
  ui_bucket_regional_domain_name = module.s3_ui[0].bucket_regional_domain_name
  ui_bucket_id                   = module.s3_ui[0].bucket_name
  ui_bucket_arn                  = module.s3_ui[0].bucket_arn
  ec2_public_dns                 = module.ec2_portal[0].instance_public_dns
}
