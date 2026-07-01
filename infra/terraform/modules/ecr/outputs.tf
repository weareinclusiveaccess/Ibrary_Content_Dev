output "repository_url" {
  value       = aws_ecr_repository.review_api.repository_url
  description = "Push target: <repository_url>:<tag>"
}

output "repository_arn" {
  value = aws_ecr_repository.review_api.arn
}

output "repository_name" {
  value = aws_ecr_repository.review_api.name
}
