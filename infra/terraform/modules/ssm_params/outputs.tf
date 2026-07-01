output "parameter_arns" {
  value       = [for p in aws_ssm_parameter.secret : p.arn]
  description = "List of created SSM parameter ARNs (grant ssm:GetParameter on these)"
}

output "parameter_path_prefix" {
  value = var.path_prefix
}
