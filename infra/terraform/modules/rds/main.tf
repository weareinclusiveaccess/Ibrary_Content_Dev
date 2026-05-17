resource "aws_db_subnet_group" "this" {
  name       = "${var.project_name}-${var.environment}-pg"
  subnet_ids = var.subnet_ids

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_security_group" "postgres" {
  name        = "${var.project_name}-${var.environment}-postgres"
  description = "PostgreSQL access for IBrary reviewer API"
  vpc_id      = var.vpc_id

  ingress {
    description = "PostgreSQL from allowed CIDRs"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  egress {
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

resource "aws_db_instance" "postgres" {
  identifier = "${var.project_name}-${var.environment}-pg"

  engine         = "postgres"
  engine_version = "16"
  instance_class = var.instance_class

  allocated_storage = var.allocated_storage_gb
  storage_type      = "gp3"

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.postgres.id]
  publicly_accessible    = var.publicly_accessible

  skip_final_snapshot = var.environment == "dev"
  deletion_protection = var.environment != "dev"

  backup_retention_period = var.environment == "prod" ? 7 : 1

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

locals {
  database_url = "postgresql://${var.db_username}:${var.db_password}@${aws_db_instance.postgres.address}:5432/${var.db_name}"
}

resource "aws_secretsmanager_secret" "database_url" {
  name = "${var.project_name}/${var.environment}/database-url"

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id     = aws_secretsmanager_secret.database_url.id
  secret_string = local.database_url
}
