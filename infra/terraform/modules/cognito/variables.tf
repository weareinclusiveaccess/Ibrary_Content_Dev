variable "project_name" {
  type        = string
  description = "Resource name prefix"
}

variable "environment" {
  type        = string
  description = "Environment label (dev, staging, prod)"
}

variable "domain_prefix" {
  type        = string
  description = "Cognito hosted UI domain prefix (must be globally unique)"
}

variable "callback_urls" {
  type        = list(string)
  description = "OAuth callback URLs for the reviewer SPA"
  default     = ["http://localhost:5173/"]
}

variable "logout_urls" {
  type        = list(string)
  description = "OAuth logout URLs"
  default     = ["http://localhost:5173/"]
}
