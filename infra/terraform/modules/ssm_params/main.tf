resource "aws_ssm_parameter" "secret" {
  for_each = toset(nonsensitive(keys(var.secrets)))

  name        = "${var.path_prefix}/${each.key}"
  description = "Reviewer portal secret (${each.key})"
  type        = "SecureString"
  value       = var.secrets[each.key]
  key_id      = "alias/aws/ssm"
  overwrite   = true

  tags = {
    Project     = var.project_name
    Environment = var.environment
    Purpose     = "reviewer-portal"
  }

  lifecycle {
    ignore_changes = [value]
  }
}
