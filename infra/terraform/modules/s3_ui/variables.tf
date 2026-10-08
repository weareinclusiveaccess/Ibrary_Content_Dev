variable "project_name" {
  type        = string
  description = "Resource name prefix"
}

variable "environment" {
  type        = string
  description = "Environment label (dev, staging, prod)"
}

variable "bucket_name" {
  type        = string
  description = "Globally unique S3 bucket name for the UI dist (e.g. ibrary-review-ui-dev-<account>)"
}

variable "force_destroy" {
  type        = bool
  description = "Allow terraform destroy to nuke the bucket even with objects. Convenient for dev."
  default     = true
}
