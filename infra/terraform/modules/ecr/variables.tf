variable "project_name" {
  type        = string
  description = "Resource name prefix"
}

variable "environment" {
  type        = string
  description = "Environment label (dev, staging, prod)"
}

variable "repository_name" {
  type        = string
  description = "ECR repo name (push tag will be <account>.dkr.ecr.<region>.amazonaws.com/<name>)"
  default     = "ibrary-review-api"
}

variable "keep_images" {
  type        = number
  description = "Lifecycle policy: keep this many most-recent images, expire the rest"
  default     = 10
}
