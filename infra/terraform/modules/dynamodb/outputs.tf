output "table_name" {
  value = aws_dynamodb_table.curated_content.name
}

output "table_arn" {
  value = aws_dynamodb_table.curated_content.arn
}
