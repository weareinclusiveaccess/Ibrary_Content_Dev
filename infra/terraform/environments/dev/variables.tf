variable "aws_region" {
  type    = string
  default = "eu-west-1"
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
