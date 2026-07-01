# Hosting the reviewer portal (~$0–12/month)

The portal is two parts: **static React UI** (`review-ui/`) and **FastAPI API** (`uvicorn ibrary.review.api:app`). Postgres can stay on **Neon** (free tier). Auth uses **Cognito** (free tier for small teams).

> **Scope:** The production image and AWS footprint contain **only** what is required to run the reviewer portal end-to-end. None of the content pipeline (`alignment/`, `textbook/`, `evaluation/`, `judging/`, `prompts/`, `pipeline/`, etc.) is deployed. See Decision 14 below.

## Live deployment (2026-05-18)

Dev environment is deployed and serving the reviewer portal end-to-end. Live values:

| What | Value |
|------|-------|
| Portal URL | `https://d52pmztlzpw34.cloudfront.net` |
| CloudFront distribution | `E2J7Q9XCZKFILO` |
| EC2 instance | `i-072319bb6a312ad56` (t3.micro, `eu-west-1`) |
| ECR repo | `681986854278.dkr.ecr.eu-west-1.amazonaws.com/ibrary-review-api` |
| UI S3 bucket | `ibrary-review-ui-dev-681986854278` |
| Cognito User Pool | `eu-west-1_JFzqPXIkr` (groups: `admin`, `reviewer`) |
| Cognito App Client | `17q8sg0nq0g8esmmqrbdv5l2gi` |
| DynamoDB table | `CuratedContent` (on-demand, deletion-protected) |
| SSM path | `/ibrary/review/*` |
| EC2 instance role | `ibrary-dev-portal-instance` |

### Operational runbook

**Restart the container** (after env / SSM change):

```powershell
Set-Location 'C:\Users\Motunrayo Ibiyo\Documents\IBrary\infra\terraform\environments\dev'
$instance = terraform output -raw portal_instance_id

@'
{ "commands": ["systemctl restart ibrary-portal.service","sleep 8","systemctl is-active ibrary-portal.service","docker ps --format \"{{.Names}} {{.Status}}\"","curl -sf http://localhost/health && echo HEALTH_OK || echo HEALTH_FAIL"] }
'@ | Out-File C:\temp\ssm-restart.json -Encoding ascii

$cmdId = aws ssm send-command --instance-ids $instance --document-name "AWS-RunShellScript" --parameters file://C:/temp/ssm-restart.json --query "Command.CommandId" --output text
Start-Sleep -Seconds 15
aws ssm get-command-invocation --command-id $cmdId --instance-id $instance --query "StandardOutputContent" --output text | Out-File C:\temp\ssm-out.txt -Encoding utf8
Get-Content C:\temp\ssm-out.txt
```

**Tail container logs:**

```powershell
@'
{ "commands": ["docker logs portal --tail 80 2>&1 || true"] }
'@ | Out-File C:\temp\ssm-logs.json -Encoding ascii
$cmdId = aws ssm send-command --instance-ids $instance --document-name "AWS-RunShellScript" --parameters file://C:/temp/ssm-logs.json --query "Command.CommandId" --output text
Start-Sleep -Seconds 8
aws ssm get-command-invocation --command-id $cmdId --instance-id $instance --query "StandardOutputContent" --output text | Out-File C:\temp\ssm-out.txt -Encoding utf8
Get-Content C:\temp\ssm-out.txt
```

**Push a new image and roll the container:**

```powershell
Set-Location 'C:\Users\Motunrayo Ibiyo\Documents\IBrary'
$registry = "681986854278.dkr.ecr.eu-west-1.amazonaws.com"
$repo     = "ibrary-review-api"

$token = aws ecr get-login-password --region eu-west-1
docker login --username AWS --password $token $registry
docker build -t "${repo}:latest" .
docker tag  "${repo}:latest" "$registry/${repo}:latest"
docker push "$registry/${repo}:latest"

# On EC2: pull + restart
Set-Location 'C:\Users\Motunrayo Ibiyo\Documents\IBrary\infra\terraform\environments\dev'
$instance = terraform output -raw portal_instance_id
@'
{ "commands": ["docker pull 681986854278.dkr.ecr.eu-west-1.amazonaws.com/ibrary-review-api:latest","systemctl restart ibrary-portal.service"] }
'@ | Out-File C:\temp\ssm-roll.json -Encoding ascii
aws ssm send-command --instance-ids $instance --document-name "AWS-RunShellScript" --parameters file://C:/temp/ssm-roll.json --query "Command.CommandId" --output text
```

**Update a single SSM parameter:**

```powershell
aws ssm put-parameter --name "/ibrary/review/<KEY>" --value "<VALUE>" --type SecureString --overwrite
# then restart the container (see above)
```

### Gotchas resolved during initial deploy

These are written down so the next operator doesn't re-discover them.

1. **`terraform.tfvars` seeds SSM with placeholder values.** After the first `terraform apply` you **must** overwrite `/ibrary/review/COGNITO_USER_POOL_ID`, `/ibrary/review/COGNITO_APP_CLIENT_ID`, and `/ibrary/review/DATABASE_URL_REVIEW` via `aws ssm put-parameter --overwrite` (the Terraform resource has `lifecycle.ignore_changes = [value]` so future applies won't reset them). Without this the container starts but every Cognito call returns `User pool client REPLACE_ME does not exist`.
2. **Cognito admin IAM policy is *not* attached by default** because `cognito_create_admin_iam_policy = false` (`content-dev` typically lacks `iam:CreatePolicy`). Manual attach as **inline policy** on the EC2 role:
   ```powershell
   # Source of truth: infra/terraform/modules/cognito/iam.tf
   aws iam put-role-policy --role-name ibrary-dev-portal-instance \
     --policy-name CognitoAdminAPI --policy-document file://infra/terraform/modules/cognito/policy.json
   ```
   The policy must include `cognito-idp:AdminListGroupsForUser` (the portal calls it to populate the Users page; not strictly admin-write but needs the action). Already in the Terraform module.
3. **`PORTAL_PUBLISH_ENABLED` defaults to `false`** so admins can't publish to DynamoDB until JWT is verified live. Flip on with:
   ```powershell
   aws ssm put-parameter --name "/ibrary/review/PORTAL_PUBLISH_ENABLED" --value "true" --type SecureString --overwrite
   # then restart the container
   ```
4. **EC2 user-data replaces the instance on user_data changes** (`user_data_replace_on_change = true`). The new instance has a different public DNS, so after replacement run `uv run python scripts/portal_update_cloudfront_origin.py` to repoint CloudFront. The script is idempotent.
5. **`docker login --password-stdin` fails from PowerShell** because `|` pipe encoding mangles the ECR token (UTF-16 BOM). Use `docker login --username AWS --password $token $registry` instead.
6. **AWS CLI on Windows emits Unicode (`●` from `systemctl`)** which the cp1252 console can't render. Either set `$OutputEncoding = [System.Text.UTF8Encoding]::new(); chcp 65001 | Out-Null` for the session, or pipe to a UTF-8 file: `... --output text | Out-File C:\temp\out.txt -Encoding utf8; Get-Content C:\temp\out.txt`.
7. **SSM `--parameters` with embedded quotes is fragile.** Use `--parameters file://path/to/commands.json` and write commands as a JSON array.

## Confirmed deployment plan (2026-05-17)

This project deploys the reviewer portal on **AWS free tier**, designed for short reviewer sprints with the EC2 box stopped between sessions. Total active cost during a sprint: **$0**. Dormant cost between sprints: **~$0.65/month** (EBS root volume only).

| Piece | Choice | Why |
|--------|--------|-----|
| **DB** | Neon (existing) | Free tier; already configured |
| **API host** | **EC2 t3.micro** (Docker container) | 750 hr/mo free for 12 months; stop instance to drop to $0 compute |
| **UI host** | **S3 + CloudFront** (one distribution fronting both UI and API) | Free tier covers all expected traffic; UI uses relative API paths |
| **Public URL** | `*.cloudfront.net` for v1 | Custom domain deferred |
| **Auth** | Cognito user pool (eu-west-1) + JWT (Bearer) on every `/review/*` request | API key + role header removed; mock users removed |
| **Login UI** | Custom form (existing); forgot-password added; Hosted UI deferred to Phase 2 | Reviewers are admin-invited; no self-signup |
| **User provisioning** | Portal `/admin/users` page (admin calls Cognito via API); CLI as fallback | Code already exists |
| **Images** | S3 presigned URLs (15 min) via EC2 instance role | Already implemented |
| **Container artifacts** | Manual `docker push` to ECR; pull on EC2; CI/CD (GitHub Actions + OIDC + SSM) deferred to Phase 2 | Fastest path to first deploy |
| **Secrets** | SSM Parameter Store (SecureString) under `/ibrary/review/*`; EC2 instance role reads them | Free; audited; no plaintext on box |
| **Review workflow** | 5 statuses — `draft` / `draft_curriculum_only` / `rejected` / `verified` / `published` | Reviewers can explicitly reject |
| **DynamoDB publish** | Admin button in portal calls `POST /review/units/{id}/publish-to-dynamodb`, gated by `PORTAL_PUBLISH_ENABLED` flag (off until JWT auth lands) | One-click release; flag prevents accidental exposure |
| **DynamoDB table** | `CuratedContent` in `eu-west-1` (same account as Cognito + EC2); `PAY_PER_REQUEST`; AWS-managed encryption; deletion protection on; PITR off (Postgres is source of truth); provisioned by Terraform; **DynamoDB Local for dev** via `DYNAMODB_ENDPOINT_URL` | Stays inside permanent DynamoDB free tier (no 12-month limit); local dev never touches prod table |
| **Lifecycle** | `make portal-start` / `portal-stop` / `portal-status` | Manual stop between sprints |
| **Local dev** | Real Cognito dev pool + `.env` + `uv run` / `npm run dev`; no mock auth | Production-faithful |

Options A–D below remain documented as alternatives for future moves. They are **not** the chosen path. The full decision log is at the end of this document.

## Recommended cheap stack (~$6–12/month)

| Piece | Service | Typical cost |
|--------|---------|----------------|
| Database | **Neon** (you already use this) | $0 free tier, or ~$19 if you outgrow it |
| API | **Fly.io** or **Render** web service | ~$5–7/mo (512MB) |
| UI | **Cloudflare Pages** or **Netlify** | $0 |
| Auth | **Cognito** (Terraform) | $0 (MAU free tier) |
| Images | Existing **S3** | pennies |

**Total:** about **$5–7/month** if Neon stays free; up to **~$12** with a small paid DB or slightly larger API VM.

## Option A — Fly.io API + Cloudflare Pages UI (good default)

### 1. API on Fly.io

```bash
# From repo root — add a Dockerfile for review API if not present, then:
fly launch --name ibrary-review-api --region lhr
fly secrets set DATABASE_URL_REVIEW="postgresql://..." COGNITO_USER_POOL_ID="..." COGNITO_APP_CLIENT_ID="..." COGNITO_REGION="eu-west-1"
fly deploy
```

- Attach IAM via Fly’s AWS integration or run with static AWS keys for Cognito admin + S3 presign (prefer instance role on AWS instead if you move API to App Runner).

### 2. UI on Cloudflare Pages

```bash
cd review-ui
npm run build
# Connect GitHub repo in Cloudflare dashboard → Pages → build command: npm run build, output: dist
```

Set environment variable for build (optional if you proxy in `vite.config` only at dev):

- Production API URL: configure `review-ui` to call your Fly URL, or put **Cloudflare Pages `_redirects` / proxy** so `/review/*` forwards to the API.

Update `vite.config.ts` `server.proxy` is dev-only; for production set `VITE_REVIEW_API_URL` and prefix fetches in `api.ts` (future step).

### 3. Cognito callback URLs

In Terraform `cognito_callback_urls`, add:

- `https://your-project.pages.dev/`
- `http://localhost:5173/` (local)

## Option B — Render (single platform, ~$7/mo)

- **Web service** for FastAPI (Docker or `uv run`).
- **Static site** for `review-ui/dist` (free).
- Neon for Postgres.

Render free tier sleeps after inactivity (cold starts); **$7 Starter** avoids sleep.

## Option C — All AWS (~$10–15/mo)

- **App Runner** for API (~$5–10)
- **S3 + CloudFront** for UI (~$1)
- **Neon** or **RDS** (RDS adds cost; Neon cheaper)
- Cognito from Terraform

More integrated if you already live in AWS; not the absolute cheapest.

## Option D — Local / demo only ($0)

- API: `uv run python scripts/run_review_portal.py`
- UI: `cd review-ui && npm run dev`
- DB: Docker or Neon free

## What not to use for this app

- **Vercel serverless alone** — long-running FastAPI + DB connections fit a small VM better.
- **Lambda-only** — possible but more work (RDS Proxy, API Gateway); not worth it for $6 budget.

## Checklist before going live (confirmed plan)

1. [x] `terraform apply` in `infra/terraform/environments/dev` (Cognito + groups) — done for dev pool.
2. [x] ECR repo, S3 UI bucket + CloudFront distribution, EC2 t3.micro + instance role, SSM parameters, **DynamoDB `CuratedContent` table** all in Terraform (`enable_portal_hosting = true`).
3. [x] Build & push API image to ECR; bring EC2 up; container fetches secrets from SSM.
4. [x] Build `review-ui` (Node 22+); upload `dist/` to the S3 bucket; create CloudFront invalidation.
5. [x] Replace API key + role header with Cognito JWT verification on `/review/*`; remove mock users from the SPA build.
6. [x] Add `rejected` status + admin `/review/units/{id}/publish-to-dynamodb` route behind `PORTAL_PUBLISH_ENABLED`.
7. [x] Flip `PORTAL_PUBLISH_ENABLED=true` (after JWT auth verified live).
8. [x] Add the CloudFront URL to Cognito `callback_urls` and `logout_urls`.
9. [x] Wire `make portal-start` / `portal-stop` / `portal-status` so the EC2 box can be paused between sprints.

**Remaining work (Phase 2):**

- Custom domain in front of CloudFront (Route 53 or external DNS + ACM cert in `us-east-1`).
- GitHub Actions + OIDC for CI/CD docker push (Decision 5 → 5C migration).
- Cognito Hosted UI + PKCE.
- WAF in front of CloudFront.

See [terraform/README.md](terraform/README.md) and [README.md](README.md).

## Decisions log (2026-05-17)

| # | Decision | Notes |
|---|----------|-------|
| 1 | All-AWS free tier: EC2 t3.micro + S3 + CloudFront + Neon + Cognito | Stop EC2 between sprints; ~$0.65/mo dormant |
| 2 | Cognito JWT (Bearer) on every `/review/*`; JWKS verify; drop `X-Review-Api-Key` and `X-Review-User-Role`; drop mock users | Use existing `cognito_auth.sign_in`, extend to return tokens; add `/review/auth/refresh` |
| 3 | Custom login form for MVP; Hosted UI deferred to Phase 2 | Add `forgot-password` / `confirm-forgot-password` via Cognito client APIs |
| 4 | CloudFront fronts both UI (S3) and API (EC2); `*.cloudfront.net` URL for v1 | UI keeps relative API paths — no `VITE_REVIEW_API_URL` work needed |
| 5 | Dockerfile + ECR + manual `docker push` for v1; GitHub Actions + OIDC + SSM deferred to Phase 2 | 5B → 5C is ~1 hour of additive work later |
| 6 | SSM Parameter Store (SecureString) for secrets via EC2 instance role | `/ibrary/review/<KEY>`; default `alias/aws/ssm` KMS; no Secrets Manager |
| 7 | 5 statuses (`+rejected`) + admin Publish-to-DynamoDB button behind `PORTAL_PUBLISH_ENABLED`; light audit row | Audit reuses `content_manual_quality_check`; no migration |
| 8 | Portal `/admin/users` canonical for Cognito provisioning; CLI as fallback | EC2 instance role uses existing `cognito_admin_api_policy_arn` |
| 9 | S3 presigned URLs (15 min) for textbook images via EC2 instance role | Already implemented |
| 10 | Real Cognito locally + `.env`; no `LOCAL_DEV_BYPASS_AUTH` flag | Docker available for prod-image smoke tests only |
| 11 | Manual `make portal-start` / `portal-stop` / `portal-status` Makefile targets | EventBridge schedule deferred; auto-stop-on-inactivity not pursued |
| 12 | DynamoDB `CuratedContent` lives in same AWS account + region as Cognito + EC2 (`eu-west-1`); Terraform-managed; on-demand billing; PITR off; deletion protection on; DynamoDB Local for dev via `DYNAMODB_ENDPOINT_URL` | Permanent free tier covers our volume (no 12-mo expiry); Postgres `curated_content` is the source of truth, so PITR not needed; dev publishes are isolated from prod |
| 13 | EC2 keeps ephemeral public DNS; `scripts/portal_update_cloudfront_origin.py` swaps the CloudFront `ec2-api` origin after each `make portal-start`. CloudFront module sets `lifecycle.ignore_changes = [origin]` so `terraform apply` doesn't fight the script. | Keeps Decision 1's `$0` dormant promise (no Elastic IP / ALB / VPC origin). ~5–10 min CloudFront propagation per start is acceptable for sprint workflow. |
| 14 | **Portal-only deployment surface.** AWS hosting contains only what the reviewer UI needs end-to-end: FastAPI portal app, the React UI, Cognito, DynamoDB writer for the publish action, S3 read for textbook images, and SSM-stored portal secrets. Pipeline / curation / extraction code stays out of production. | Concretely: (a) `pyproject.toml` splits deps into `core` (portal) vs `pipeline` extra; the container only installs `core` (~600 MB vs ~25 GB with ML libs). (b) `Dockerfile` does selective `COPY` of `src/ibrary/{__init__,config,db,models}.py + review/ + serving/ + curation/{__init__,schemas,curated_postgres}.py` — every other subpackage is left out. (c) `portal_ssm_secrets` default is portal-only: `DATABASE_URL_REVIEW`, `COGNITO_USER_POOL_ID`, `COGNITO_APP_CLIENT_ID`, `COGNITO_APP_CLIENT_SECRET`. **No `OPENAI_API_KEY` or other pipeline secrets in the portal's SSM scope.** (d) EC2 instance role is scoped: DynamoDB `PutItem/UpdateItem/GetItem/DescribeTable` on the `CuratedContent` table only, S3 `GetObject` on `${images_bucket}/biology/*` only, SSM read on `/ibrary/review/*` only. Pipeline runs locally against Neon + the user's `.env`; nothing in AWS can invoke the pipeline. |
| 15 | **Cognito admin IAM policy attached as inline** on the EC2 role (not via managed policy) because the `content-dev` AWS principal lacks `iam:CreatePolicy`. Terraform variable `cognito_create_admin_iam_policy = false`; the operator runs `aws iam put-role-policy --role-name ibrary-dev-portal-instance --policy-name CognitoAdminAPI --policy-document file://...` once after the first apply. | Avoids needing elevated IAM perms during normal apply. Source of truth for the policy actions: `infra/terraform/modules/cognito/iam.tf`. |

Cost summary:

| State | Monthly cost |
|-------|---------------|
| Active sprint (EC2 running) | **$0** within free tier |
| Between sprints (EC2 stopped) | ~$0.65 (EBS volume) |
| After 12-month free-tier expiry, EC2 always-on | ~$8 |
| After 12-month expiry, EC2 stopped | ~$0.65 |
