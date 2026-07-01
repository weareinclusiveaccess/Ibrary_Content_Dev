variable "project_name" {
  type        = string
  description = "Resource name prefix"
}

variable "environment" {
  type        = string
  description = "Environment label (dev, staging, prod)"
}

variable "table_name" {
  type        = string
  description = "DynamoDB table name (matches src/ibrary/serving/dynamodb_writer.py)"
  default     = "CuratedContent"
}

variable "point_in_time_recovery" {
  type        = bool
  description = "Enable PITR. Default false: Postgres curated_content is source of truth."
  default     = false
}

variable "deletion_protection" {
  type        = bool
  description = "Block accidental terraform destroy / DeleteTable on the table"
  default     = true
}
