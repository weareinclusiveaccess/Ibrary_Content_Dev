resource "aws_ecr_repository" "review_api" {
  name                 = var.repository_name
  image_tag_mutability = "MUTABLE"

  encryption_configuration {
    encryption_type = "AES256"
  }

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
    Purpose     = "reviewer-portal-api-image"
  }
}

resource "aws_ecr_lifecycle_policy" "review_api" {
  repository = aws_ecr_repository.review_api.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last ${var.keep_images} images; expire older untagged"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = var.keep_images
        }
        action = { type = "expire" }
      }
    ]
  })
}
