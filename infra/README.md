# IBrary AWS infrastructure

Terraform and setup notes for hosting the **reviewer portal**, **RDS PostgreSQL**, and integrating with existing **S3** textbook image storage.

## What to provision

| Component | Purpose | Terraform module |
|-----------|---------|------------------|
| **Amazon Cognito** | Reviewer login; groups `admin` / `reviewer`; admin user API | [`terraform/modules/cognito`](terraform/modules/cognito) |
| **RDS PostgreSQL** | Production Postgres for `ibrary` schema (curated content, judge scores) | [`terraform/modules/rds`](terraform/modules/rds) |
| **S3** | Already used: `ibrary-content` for textbook images; optional bucket for reviewer UI static files | Manual / extend `modules/s3` later |
| **Secrets Manager** | Store `DATABASE_URL` for the reviewer API | Referenced in RDS module |
| **ECS Fargate / App Runner** | Run reviewer FastAPI (phase 1 — not in Terraform yet) | See plan doc |

**Local development:** keep using Docker Compose Postgres (`make up`). You only need AWS for Cognito + S3 images until you deploy the reviewer API.

## Prerequisites

1. **AWS account** with permissions to create Cognito, RDS, IAM, and Secrets Manager.
2. **AWS CLI** configured (`aws configure` or `AWS_PROFILE=ibrary-dev`).
3. **Terraform** ≥ 1.5 installed.
4. **Existing S3 bucket** for textbook images (e.g. `ibrary-content` in `eu-west-1`) — created manually or already present from pipeline extract.

## Quick start (dev environment)

```bash
cd infra/terraform/environments/dev

# Copy and edit variables
cp terraform.tfvars.example terraform.tfvars
# Set db_password, allowed reviewer emails, region

terraform init
terraform plan
terraform apply
```

After apply, note outputs:

- `cognito_user_pool_id`, `cognito_app_client_id`, `cognito_hosted_ui_url`
- `rds_endpoint`, `database_url_secret_arn` (if RDS enabled)

Run Alembic against RDS:

```bash
export DATABASE_URL="postgresql://ibrary:YOUR_PASSWORD@RDS_ENDPOINT:5432/ibrary"
uv run alembic upgrade head
uv run python scripts/load_curated_to_postgres.py
```

## Region and naming

- Default region in examples: **`eu-west-1`** (match your `ibrary-content` bucket).
- Resource prefix: `ibrary` + environment (`dev`, `staging`, `prod`).

## IAM for pipeline (existing)

Your local **extract** step needs S3 write on `s3://ibrary-content/{subject}/textbook-images/`. See [SETUP.md](../SETUP.md) § AWS access key and S3 bucket.

The **reviewer API** task role needs:

- `s3:GetObject` on `arn:aws:s3:::ibrary-content/biology/textbook-images/*`
- Read `secretsmanager:GetSecretValue` for database URL
- No write to S3 unless you add asset upload later

## Hosting the portal (~$6–12/mo)

See **[HOSTING.md](HOSTING.md)** for Fly.io / Render / Cloudflare Pages + Neon + Cognito.

## Cost notes (dev)

- **Cognito:** free tier covers most reviewer testing.
- **RDS `db.t4g.micro`:** ~$12–15/month if left running 24/7; stop or destroy when not needed.
- **NAT Gateway** (if you use private subnets): significant cost; dev template uses **public RDS** optional flag to avoid NAT for MVP.

## Implementation plan

See [docs/plans/2026-05-16-reviewer-portal.md](../docs/plans/2026-05-16-reviewer-portal.md) for the full reviewer UI/API roadmap.

## Directory layout

```
infra/
├── README.md                 # this file
└── terraform/
    ├── README.md             # Terraform commands and module index
    ├── versions.tf
    ├── variables.tf
    ├── outputs.tf
    ├── main.tf               # wires modules for default env
    ├── modules/
    │   ├── cognito/
    │   └── rds/
    └── environments/
        └── dev/
            ├── main.tf
            ├── variables.tf
            ├── outputs.tf
            └── terraform.tfvars.example
```
