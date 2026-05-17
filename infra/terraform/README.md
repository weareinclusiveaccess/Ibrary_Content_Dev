# Terraform — IBrary reviewer platform (dev)

Provisions **Cognito** (reviewer auth) and optional **RDS PostgreSQL** for the reviewer portal. Textbook images stay in your existing S3 bucket (`ibrary-content`).

## Commands

```bash
cd infra/terraform/environments/dev
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — set db_password (if enable_rds = true)

terraform init
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
```

Destroy dev stack:

```bash
terraform destroy
```

## Modules

### `modules/cognito`

- User pool with email sign-in
- App client (no secret — SPA-friendly)
- Optional hosted UI domain prefix: `ibrary-review-dev`

**Outputs:** `user_pool_id`, `app_client_id`, `hosted_ui_base_url`

### `modules/rds`

- PostgreSQL 16 on `db.t4g.micro` (configurable)
- Database name `ibrary`, user `ibrary`
- Password stored in **Secrets Manager** (`ibrary/dev/database-url`)
- Security group: PostgreSQL port open to `allowed_cidr_blocks` (default: your IP for dev)

**Outputs:** `endpoint`, `secret_arn`

Set `enable_rds = false` in tfvars to provision **Cognito only** and keep Postgres on Docker locally.

## Wiring the reviewer API (manual, post-Terraform)

1. Create ECS task role or App Runner instance role with:
   - `secretsmanager:GetSecretValue` on the DB secret
   - `s3:GetObject` on textbook image prefix
2. Set environment variables on the API service:
   - `DATABASE_URL` from Secrets Manager
   - `COGNITO_USER_POOL_ID`, `COGNITO_APP_CLIENT_ID`, `COGNITO_REGION`
   - `AWS_DEFAULT_REGION`
3. Configure reviewer SPA:
   - `VITE_COGNITO_USER_POOL_ID`, `VITE_COGNITO_CLIENT_ID`, `VITE_API_BASE_URL`

## State backend (recommended before team use)

Add an S3 + DynamoDB lock backend in `environments/dev/main.tf`:

```hcl
terraform {
  backend "s3" {
    bucket         = "ibrary-terraform-state"
    key            = "reviewer-portal/dev/terraform.tfstate"
    region         = "eu-west-1"
    dynamodb_table = "ibrary-terraform-locks"
    encrypt        = true
  }
}
```

Create the state bucket and lock table once per account.

## Variables reference

See `environments/dev/terraform.tfvars.example` and `environments/dev/variables.tf`.
