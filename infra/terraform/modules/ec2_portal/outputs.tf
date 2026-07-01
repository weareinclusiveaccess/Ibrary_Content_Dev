output "instance_id" {
  value = aws_instance.portal.id
}

output "instance_public_dns" {
  value       = aws_instance.portal.public_dns
  description = "Public DNS — changes on stop/start. Use scripts/portal_update_cloudfront_origin.py after start."
}

output "instance_public_ip" {
  value = aws_instance.portal.public_ip
}

output "instance_role_arn" {
  value = aws_iam_role.portal.arn
}

output "security_group_id" {
  value = aws_security_group.portal.id
}
