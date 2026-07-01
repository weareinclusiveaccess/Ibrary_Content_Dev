resource "aws_cloudfront_origin_access_control" "ui" {
  name                              = "${var.project_name}-${var.environment}-ui-oac"
  description                       = "OAC for reviewer portal UI bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "portal" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "${var.project_name}-${var.environment} reviewer portal (UI + API)"
  default_root_object = "index.html"
  price_class         = "PriceClass_100" # NA + EU only — cheapest

  origin {
    origin_id                = "s3-ui"
    domain_name              = var.ui_bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.ui.id
  }

  origin {
    origin_id   = "ec2-api"
    domain_name = var.ec2_public_dns

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  # SPA static assets
  default_cache_behavior {
    target_origin_id       = "s3-ui"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    # Managed cache policy: CachingOptimized
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"
  }

  # API: never cache, forward everything
  ordered_cache_behavior {
    path_pattern           = "/review/*"
    target_origin_id       = "ec2-api"
    allowed_methods        = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods         = ["GET", "HEAD"]
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    # Managed: CachingDisabled
    cache_policy_id = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
    # Managed: AllViewerExceptHostHeader — forwards everything except Host
    origin_request_policy_id = "b689b0a8-53d0-40ab-baf2-68738e2966ac"
  }

  ordered_cache_behavior {
    path_pattern             = "/health"
    target_origin_id         = "ec2-api"
    allowed_methods          = ["GET", "HEAD"]
    cached_methods           = ["GET", "HEAD"]
    viewer_protocol_policy   = "redirect-to-https"
    cache_policy_id          = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
    origin_request_policy_id = "b689b0a8-53d0-40ab-baf2-68738e2966ac"
  }

  # SPA client-side routing: serve index.html on 403/404 from S3.
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }
  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
    Purpose     = "reviewer-portal"
  }

  # The EC2 public DNS changes on stop/start; scripts/portal_update_cloudfront_origin.py
  # rewrites the ec2-api origin out-of-band. Don't fight that in subsequent applies.
  lifecycle {
    ignore_changes = [origin]
  }
}

# OAC bucket policy references this distribution ARN — declare here so the count
# is never derived from unknown values across modules (fixes first-apply failures).
resource "aws_s3_bucket_policy" "ui_cloudfront_read" {
  bucket = var.ui_bucket_id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowCloudFrontOACReadOnly"
        Effect    = "Allow"
        Principal = { Service = "cloudfront.amazonaws.com" }
        Action    = ["s3:GetObject"]
        Resource  = "${var.ui_bucket_arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.portal.arn
          }
        }
      }
    ]
  })

  depends_on = [aws_cloudfront_distribution.portal]
}
