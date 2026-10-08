output "distribution_id" {
  value = aws_cloudfront_distribution.portal.id
}

output "distribution_arn" {
  value = aws_cloudfront_distribution.portal.arn
}

output "distribution_domain_name" {
  value       = aws_cloudfront_distribution.portal.domain_name
  description = "Public URL: https://<this>/"
}

output "ui_oac_id" {
  value = aws_cloudfront_origin_access_control.ui.id
}
