output "endpoint" {
  value = aws_db_instance.postgres.address
}

output "port" {
  value = aws_db_instance.postgres.port
}

output "database_name" {
  value = var.db_name
}

output "secret_arn" {
  value = aws_secretsmanager_secret.database_url.arn
}

output "security_group_id" {
  value = aws_security_group.postgres.id
}
