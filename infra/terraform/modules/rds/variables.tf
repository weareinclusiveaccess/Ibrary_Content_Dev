variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "vpc_id" {
  type        = string
  description = "VPC for RDS security group"
}

variable "subnet_ids" {
  type        = list(string)
  description = "Subnet IDs for DB subnet group (at least 2 AZs in prod)"
}

variable "db_name" {
  type    = string
  default = "ibrary"
}

variable "db_username" {
  type    = string
  default = "ibrary"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "allocated_storage_gb" {
  type    = number
  default = 20
}

variable "allowed_cidr_blocks" {
  type        = list(string)
  description = "CIDRs allowed to connect to PostgreSQL (dev: your IP /32)"
}

variable "publicly_accessible" {
  type        = bool
  description = "If true, RDS gets a public IP (simpler dev; disable in prod)"
  default     = true
}
