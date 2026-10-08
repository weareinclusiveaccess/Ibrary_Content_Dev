output "bucket_name" {
  value = aws_s3_bucket.ui.id
}

output "bucket_arn" {
  value = aws_s3_bucket.ui.arn
}

output "bucket_regional_domain_name" {
  value       = aws_s3_bucket.ui.bucket_regional_domain_name
  description = "Use as CloudFront origin domain"
}
