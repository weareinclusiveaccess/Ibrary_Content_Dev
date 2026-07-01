data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

data "aws_vpc" "default" {
  default = true
}

data "aws_ssm_parameter" "al2023_ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_security_group" "portal" {
  name        = "${var.project_name}-${var.environment}-portal-api"
  description = "Reviewer portal API on EC2 - HTTP from CloudFront only"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "HTTP from CloudFront (origin-facing managed prefix list)"
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    prefix_list_ids = [data.aws_ec2_managed_prefix_list.cloudfront.id]
  }

  egress {
    description = "All egress (Cognito, S3, DynamoDB, SSM, ECR, OpenAI)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "portal" {
  name               = "${var.project_name}-${var.environment}-portal-instance"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# Session Manager (no SSH key needed)
resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.portal.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Pull container from ECR
resource "aws_iam_role_policy_attachment" "ecr_read" {
  role       = aws_iam_role.portal.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

# Optional Cognito admin policy (only attached when the cognito module emits a real ARN).
# We intentionally avoid `coalesce(.., "")` — Terraform's coalesce drops BOTH null and ""
# from its arg list and then errors if nothing valid remains. A plain conditional is safe.
resource "aws_iam_role_policy_attachment" "cognito_admin" {
  count      = (var.cognito_admin_policy_arn != null && var.cognito_admin_policy_arn != "") ? 1 : 0
  role       = aws_iam_role.portal.name
  policy_arn = var.cognito_admin_policy_arn
}

data "aws_iam_policy_document" "portal_runtime" {
  statement {
    sid     = "ReadSsmSecrets"
    effect  = "Allow"
    actions = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"]
    # GetParametersByPath authorizes against the *path* arn itself (no /*), while
    # GetParameter authorizes against each child arn. We need both forms.
    resources = [
      "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_path_prefix}",
      "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_path_prefix}/*"
    ]
  }

  statement {
    sid       = "DecryptSsmDefaultKey"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = ["arn:aws:kms:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:alias/aws/ssm"]
  }

  statement {
    sid       = "WriteDynamoCuratedContent"
    effect    = "Allow"
    actions   = ["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem", "dynamodb:DescribeTable"]
    resources = [var.dynamodb_table_arn]
  }

  statement {
    sid       = "ReadTextbookImages"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["arn:aws:s3:::${var.images_bucket}/${var.images_prefix}/*"]
  }
}

resource "aws_iam_role_policy" "portal_runtime" {
  name   = "${var.project_name}-${var.environment}-portal-runtime"
  role   = aws_iam_role.portal.id
  policy = data.aws_iam_policy_document.portal_runtime.json
}

resource "aws_iam_instance_profile" "portal" {
  name = "${var.project_name}-${var.environment}-portal-instance"
  role = aws_iam_role.portal.name
}

locals {
  user_data = <<-EOT
    #!/bin/bash
    set -euxo pipefail

    # Bootstrap Docker + SSM agent (AL2023 has SSM preinstalled).
    dnf install -y docker
    systemctl enable --now docker
    usermod -a -G docker ec2-user

    # Place runtime entrypoint that fetches secrets from SSM and starts container.
    mkdir -p /opt/ibrary
    cat >/opt/ibrary/portal.env <<'ENVEOF'
    AWS_REGION=${data.aws_region.current.name}
    ECR_IMAGE=${var.ecr_image_uri}
    SSM_PATH_PREFIX=${var.ssm_path_prefix}
    PORTAL_PUBLISH_ENABLED=${var.portal_publish_enabled}
    ENVEOF

    cat >/opt/ibrary/start.sh <<'SHEOF'
    #!/bin/bash
    set -euo pipefail
    . /opt/ibrary/portal.env
    aws ecr get-login-password --region "$AWS_REGION" \
      | docker login --username AWS --password-stdin "$(echo "$ECR_IMAGE" | cut -d/ -f1)"
    docker pull "$ECR_IMAGE"
    SECRETS=$(aws ssm get-parameters-by-path --path "$SSM_PATH_PREFIX" --with-decryption --region "$AWS_REGION" --output json \
      | python3 -c 'import json,sys,os; ps=json.load(sys.stdin)["Parameters"]; [print(os.path.basename(p["Name"])+"="+p["Value"]) for p in ps]')
    ENVFILE=/opt/ibrary/runtime.env
    : >"$ENVFILE"
    # AWS region — required for boto3 inside the container (Cognito, DynamoDB, S3 presign)
    echo "AWS_REGION=$AWS_REGION" >>"$ENVFILE"
    echo "AWS_DEFAULT_REGION=$AWS_REGION" >>"$ENVFILE"
    echo "$SECRETS" >>"$ENVFILE"
    echo "PORTAL_PUBLISH_ENABLED=$PORTAL_PUBLISH_ENABLED" >>"$ENVFILE"
    docker rm -f portal 2>/dev/null || true
    docker run -d --name portal --restart=unless-stopped -p 80:8090 --env-file "$ENVFILE" "$ECR_IMAGE"
    SHEOF
    chmod +x /opt/ibrary/start.sh

    # systemd unit so the container comes back up on reboot.
    cat >/etc/systemd/system/ibrary-portal.service <<'UNITEOF'
    [Unit]
    Description=IBrary Reviewer Portal container
    After=docker.service network-online.target
    Requires=docker.service
    [Service]
    Type=oneshot
    RemainAfterExit=yes
    ExecStart=/opt/ibrary/start.sh
    [Install]
    WantedBy=multi-user.target
    UNITEOF
    systemctl daemon-reload
    systemctl enable --now ibrary-portal.service
  EOT
}

resource "aws_instance" "portal" {
  ami                         = data.aws_ssm_parameter.al2023_ami.value
  instance_type               = var.instance_type
  vpc_security_group_ids      = [aws_security_group.portal.id]
  iam_instance_profile        = aws_iam_instance_profile.portal.name
  associate_public_ip_address = true
  user_data                   = local.user_data
  user_data_replace_on_change = true

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_gb
    encrypted             = true
    delete_on_termination = true
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-portal"
    Project     = var.project_name
    Environment = var.environment
  }

  lifecycle {
    ignore_changes = [ami]
  }
}
