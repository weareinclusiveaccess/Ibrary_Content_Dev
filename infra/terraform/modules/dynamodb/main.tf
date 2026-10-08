resource "aws_dynamodb_table" "curated_content" {
  name         = var.table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  point_in_time_recovery {
    enabled = var.point_in_time_recovery
  }

  server_side_encryption {
    enabled = true
  }

  deletion_protection_enabled = var.deletion_protection

  tags = {
    Project     = var.project_name
    Environment = var.environment
    Purpose     = "reviewer-portal-publish"
  }
}
