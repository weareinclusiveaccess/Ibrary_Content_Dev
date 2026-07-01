variable "project_name" {
  type        = string
  description = "Resource name prefix"
}

variable "environment" {
  type        = string
  description = "Environment label (dev, staging, prod)"
}

variable "path_prefix" {
  type        = string
  description = "Parameter path prefix; e.g. /ibrary/review"
  default     = "/ibrary/review"
}

variable "secrets" {
  type        = map(string)
  sensitive   = true
  description = <<-EOT
    Map of secret name -> initial value. After first apply, values are managed out-of-band
    (lifecycle ignore_changes [value]); terraform won't reset them on subsequent applies.

    Recommended keys to seed (reviewer portal only — DO NOT seed pipeline
    secrets like OPENAI_API_KEY here; the portal does not call those services
    and the EC2 instance role should not be able to read them):
      DATABASE_URL_REVIEW       - Neon (or RDS) connection string for portal
      COGNITO_USER_POOL_ID      - from cognito module output
      COGNITO_APP_CLIENT_ID     - from cognito module output
      COGNITO_APP_CLIENT_SECRET - read once from Cognito console after first apply
    Seed with placeholder "REPLACE_ME" and rotate via AWS Console / CLI before flipping the portal on.
  EOT
  default     = {}
}
