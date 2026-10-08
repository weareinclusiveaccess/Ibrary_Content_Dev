variable "project_name" {
  type        = string
  description = "Resource name prefix"
}

variable "environment" {
  type        = string
  description = "Environment label (dev, staging, prod)"
}

variable "ui_bucket_regional_domain_name" {
  type        = string
  description = "Regional domain of the S3 UI bucket (from s3_ui module)"
}

variable "ui_bucket_id" {
  type        = string
  description = "S3 bucket name / id — for OAC bucket policy attachment"
}

variable "ui_bucket_arn" {
  type        = string
  description = "S3 bucket ARN — for Objects /* in OAC bucket policy"
}

variable "ec2_public_dns" {
  type        = string
  description = "EC2 instance public DNS at initial apply. Will be overwritten out-of-band on stop/start (lifecycle ignore_changes)."
}
