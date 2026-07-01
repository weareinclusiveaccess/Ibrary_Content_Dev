variable "project_name" {
  type        = string
  description = "Resource name prefix"
}

variable "environment" {
  type        = string
  description = "Environment label (dev, staging, prod)"
}

variable "instance_type" {
  type        = string
  description = "EC2 instance size (t3.micro = free tier)"
  default     = "t3.micro"
}

variable "root_volume_gb" {
  type        = number
  description = "Root EBS gp3 volume size in GB (30 GB included in free tier)"
  default     = 30
}

variable "ecr_image_uri" {
  type        = string
  description = "Full ECR image URI to run; e.g. <account>.dkr.ecr.<region>.amazonaws.com/ibrary-review-api:latest"
}

variable "ssm_path_prefix" {
  type        = string
  description = "SSM Parameter Store path prefix to fetch into the container env"
  default     = "/ibrary/review"
}

variable "portal_publish_enabled" {
  type        = string
  description = "Whether the Publish-to-DynamoDB admin endpoint is enabled. Keep 'false' until JWT auth ships."
  default     = "false"
}

variable "dynamodb_table_arn" {
  type        = string
  description = "ARN of the CuratedContent table — granted PutItem/UpdateItem on the instance role"
}

variable "images_bucket" {
  type        = string
  description = "S3 bucket name holding textbook images (existing). Instance role gets read access."
  default     = "ibrary-content"
}

variable "images_prefix" {
  type        = string
  description = "Key prefix inside images_bucket the portal needs to read (e.g. biology)"
  default     = "biology"
}

variable "cognito_admin_policy_arn" {
  type        = string
  description = "If set, attached to the instance role for Cognito user admin (from cognito module). Empty if attached manually."
  default     = ""
}
