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
}

module "rds" {
  count  = var.enable_rds ? 1 : 0
  source = "../../modules/rds"

  project_name = var.project_name
  environment  = var.environment

  vpc_id     = local.vpc_id
  subnet_ids = local.subnet_ids

  db_password           = var.db_password
  allowed_cidr_blocks   = var.db_allowed_cidr_blocks
  publicly_accessible   = true
}
