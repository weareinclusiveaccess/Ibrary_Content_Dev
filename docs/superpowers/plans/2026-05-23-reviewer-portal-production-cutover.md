# Reviewer Portal Production Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the user-specific reviews worktree as a coherent production release across EC2, S3/CloudFront, and Neon.

**Architecture:** The release source is `.worktrees/reviewer-user-specific-reviews`. The EC2 API image and S3-hosted React bundle must come from the same worktree, while EC2 must load Neon production through SSM `/ibrary/review/DATABASE_URL_REVIEW`.

**Tech Stack:** Python/FastAPI, SQLAlchemy, Alembic, React/Vite, AWS ECR, EC2 SSM, S3, CloudFront, Neon Postgres.

---

## File And Surface Map

- Release source: `.worktrees/reviewer-user-specific-reviews`
- Backend tests: `.worktrees/reviewer-user-specific-reviews/tests/review/test_service.py`
- Backend tests: `.worktrees/reviewer-user-specific-reviews/tests/review/test_publish_route.py`
- Frontend build: `.worktrees/reviewer-user-specific-reviews/review-ui`
- Runtime DB config: `.worktrees/reviewer-user-specific-reviews/src/ibrary/config.py`
- Review DB engine: `.worktrees/reviewer-user-specific-reviews/src/ibrary/review/db.py`
- EC2 roll script: `.worktrees/reviewer-user-specific-reviews/scripts/portal_admin.py`
- AWS env helper: `.worktrees/reviewer-user-specific-reviews/scripts/terraform-aws-env.ps1`
- Terraform outputs: `.worktrees/reviewer-user-specific-reviews/infra/terraform/environments/dev/outputs.tf`
- SSM review env path: `/ibrary/review/DATABASE_URL_REVIEW`
- Operator-local prod Neon source: `DATABASE_URL_REVIEW_PROD`

---

### Task 1: Preflight The Release Source

**Files:**
- Read: `.worktrees/reviewer-user-specific-reviews/src/ibrary/review/api.py`
- Read: `.worktrees/reviewer-user-specific-reviews/review-ui/src/lib/api.ts`
- Read: `.worktrees/reviewer-user-specific-reviews/review-ui/src/components/unit-review.tsx`

- [ ] **Step 1: Move to the release worktree**

Run:

```powershell
cd "C:\Users\Motunrayo Ibiyo\Documents\IBrary\.worktrees\reviewer-user-specific-reviews"
git status --short
git branch --show-current
```

Expected:

```text
feature/reviewer-user-specific-reviews
```

Record any dirty files. Do not revert user changes.

- [ ] **Step 2: Confirm the API rejects legacy reviewer notes**

Run:

```powershell
rg "Standalone reviewer notes are no longer supported|Legacy reviewer rejection endpoint is no longer supported|admin-notes|reviewer-scores" src/ibrary/review
```

Expected:

```text
src/ibrary/review/api.py:... Standalone reviewer notes are no longer supported
src/ibrary/review/api.py:... Legacy reviewer rejection endpoint is no longer supported
src/ibrary/review/api.py:... admin-notes
src/ibrary/review/api.py:... reviewer-scores
```

- [ ] **Step 3: Confirm the UI no longer calls legacy note helpers**

Run:

```powershell
rg "fetchNotes|postNote|rejectUnit" review-ui/src
```

Expected: no matches.

- [ ] **Step 4: Confirm the UI uses the new admin/reviewer flow**

Run:

```powershell
rg "fetchAdminNotes|postAdminNote|reviewer-scores|reviewer-rubric|outcome" review-ui/src
```

Expected: matches in `review-ui/src/lib/api.ts` and `review-ui/src/components/unit-review.tsx`.

---

### Task 2: Run Local Release Verification

**Files:**
- Test: `.worktrees/reviewer-user-specific-reviews/tests/review/test_service.py`
- Test: `.worktrees/reviewer-user-specific-reviews/tests/review/test_publish_route.py`
- Build: `.worktrees/reviewer-user-specific-reviews/review-ui/package.json`

- [ ] **Step 1: Run focused backend tests**

Run:

```powershell
uv run pytest tests/review/test_service.py tests/review/test_publish_route.py
```

Expected:

```text
33 passed
```

Warnings are acceptable if tests pass.

- [ ] **Step 2: Build the production UI bundle**

Run:

```powershell
cd review-ui
npm run build
cd ..
```

Expected:

```text
✓ built
```

Record the generated `review-ui/dist/assets/index-*.js` and `index-*.css` filenames.

- [ ] **Step 3: Confirm the built bundle has no legacy note calls**

Run:

```powershell
rg "fetchNotes|postNote|rejectUnit|Standalone reviewer notes" review-ui/dist
```

Expected: no matches.

---

### Task 3: Verify And Align Neon Production Configuration

**Files:**
- Read: `.worktrees/reviewer-user-specific-reviews/src/ibrary/config.py`
- Read: `.worktrees/reviewer-user-specific-reviews/src/ibrary/review/db.py`
- Read: `.worktrees/reviewer-user-specific-reviews/infra/HOSTING.md`

- [ ] **Step 1: Export AWS credentials for the dev/prod portal account**

Run:

```powershell
. .\scripts\terraform-aws-env.ps1 -Profile ibrary-dev
```

Expected:

```text
681986854278
```

The exact helper output may include role/account details.

- [ ] **Step 2: Confirm the operator-local prod URL exists without printing it**

Run:

```powershell
if ($env:DATABASE_URL_REVIEW_PROD) { "DATABASE_URL_REVIEW_PROD=set" } else { "DATABASE_URL_REVIEW_PROD=missing" }
```

Expected:

```text
DATABASE_URL_REVIEW_PROD=set
```

If missing, stop and ask the user to export it in the terminal environment.

- [ ] **Step 3: Compare SSM `DATABASE_URL_REVIEW` to `DATABASE_URL_REVIEW_PROD` by host only**

Run:

```powershell
$ssm = aws ssm get-parameter --name "/ibrary/review/DATABASE_URL_REVIEW" --with-decryption --region eu-west-1 --profile ibrary-dev --query "Parameter.Value" --output text
$prod = $env:DATABASE_URL_REVIEW_PROD
$ssmUri = [System.Uri]$ssm
$prodUri = [System.Uri]$prod
"ssm_host=$($ssmUri.Host)"
"prod_host=$($prodUri.Host)"
"ssm_db=$($ssmUri.AbsolutePath.TrimStart('/'))"
"prod_db=$($prodUri.AbsolutePath.TrimStart('/'))"
```

Expected:

```text
ssm_host=<neon-host>
prod_host=<same-neon-host>
ssm_db=<db-name>
prod_db=<same-db-name>
```

Do not print usernames, passwords, or full URLs.

- [ ] **Step 4: If SSM differs, update only the expected runtime key**

Run only if Step 3 shows a mismatch:

```powershell
aws ssm put-parameter --name "/ibrary/review/DATABASE_URL_REVIEW" --type SecureString --value "$env:DATABASE_URL_REVIEW_PROD" --overwrite --region eu-west-1 --profile ibrary-dev
```

Expected:

```text
Version
```

Record that `/ibrary/review/DATABASE_URL_REVIEW` was updated from `DATABASE_URL_REVIEW_PROD`, with secrets redacted.

---

### Task 4: Build And Roll The EC2 API Image

**Files:**
- Read: `.worktrees/reviewer-user-specific-reviews/Dockerfile`
- Read: `.worktrees/reviewer-user-specific-reviews/Makefile`
- Execute: `.worktrees/reviewer-user-specific-reviews/scripts/portal_admin.py`

- [ ] **Step 1: Get the ECR repository URL**

Run:

```powershell
$ecr = terraform -chdir=infra/terraform/environments/dev output -raw portal_ecr_repository_url
"ecr=$ecr"
```

Expected:

```text
ecr=681986854278.dkr.ecr.eu-west-1.amazonaws.com/ibrary-review-api
```

- [ ] **Step 2: Build the API image from the worktree**

Run:

```powershell
docker build -t "$ecr`:latest" .
```

Expected:

```text
Successfully tagged 681986854278.dkr.ecr.eu-west-1.amazonaws.com/ibrary-review-api:latest
```

- [ ] **Step 3: Authenticate Docker to ECR**

Run:

```powershell
aws ecr get-login-password --region eu-west-1 --profile ibrary-dev | docker login --username AWS --password-stdin 681986854278.dkr.ecr.eu-west-1.amazonaws.com
```

Expected:

```text
Login Succeeded
```

- [ ] **Step 4: Push the image**

Run:

```powershell
docker push "$ecr`:latest"
```

Expected: output includes pushed layers and a final digest.

- [ ] **Step 5: Roll EC2 to the pushed image**

Run:

```powershell
uv run python scripts/portal_admin.py --instance-id i-072319bb6a312ad56 --region eu-west-1 roll --image "$ecr`:latest"
```

Expected:

```text
portal Up
healthy
```

- [ ] **Step 6: Verify EC2 status**

Run:

```powershell
uv run python scripts/portal_admin.py --instance-id i-072319bb6a312ad56 --region eu-west-1 status
```

Expected: `portal` container is running and healthy.

---

### Task 5: Deploy The Matching UI Bundle To S3 And CloudFront

**Files:**
- Build output: `.worktrees/reviewer-user-specific-reviews/review-ui/dist`
- Read: `.worktrees/reviewer-user-specific-reviews/infra/terraform/environments/dev/outputs.tf`

- [ ] **Step 1: Get S3 bucket and CloudFront distribution**

Run:

```powershell
$bucket = terraform -chdir=infra/terraform/environments/dev output -raw portal_ui_bucket
$dist = terraform -chdir=infra/terraform/environments/dev output -raw portal_cloudfront_distribution_id
"bucket=$bucket"
"dist=$dist"
```

Expected:

```text
bucket=ibrary-review-ui-dev-681986854278
dist=E2J7Q9XCZKFILO
```

- [ ] **Step 2: Sync the UI bundle**

Run:

```powershell
aws s3 sync review-ui/dist "s3://$bucket" --delete --region eu-west-1 --profile ibrary-dev
```

Expected: uploaded files include `index.html` and the current `assets/index-*.js`.

- [ ] **Step 3: Invalidate CloudFront**

Run:

```powershell
$invalidation = aws cloudfront create-invalidation --distribution-id $dist --paths "/*" --profile ibrary-dev --query "Invalidation.Id" --output text
"invalidation=$invalidation"
aws cloudfront wait invalidation-completed --distribution-id $dist --id $invalidation --profile ibrary-dev
"invalidation_status=completed"
```

Expected:

```text
invalidation_status=completed
```

---

### Task 6: Smoke Test CloudFront And Neon

**Files:**
- Read only: deployed CloudFront app and EC2 API

- [ ] **Step 1: Fetch CloudFront health**

Run:

```powershell
$url = "https://d52pmztlzpw34.cloudfront.net"
Invoke-RestMethod "$url/health"
```

Expected:

```text
status : ok
```

- [ ] **Step 2: Confirm CloudFront index references the new asset**

Run:

```powershell
$html = Invoke-WebRequest "$url/" -UseBasicParsing
$html.Content | Select-String "assets/index-.*\.js"
```

Expected: the asset name matches the file generated in Task 2.

- [ ] **Step 3: Confirm served JS has no legacy helper names**

Run:

```powershell
$asset = (($html.Content | Select-String -Pattern '/assets/index-[^"]+\.js').Matches[0].Value)
$js = Invoke-WebRequest "$url$asset" -UseBasicParsing
$js.Content | Select-String "fetchNotes|postNote|rejectUnit|Standalone reviewer notes"
```

Expected: no matches.

- [ ] **Step 4: Confirm the target unit API reads from Neon**

Run:

```powershell
Invoke-RestMethod "$url/review/units/bio_sss1_theme1_topic1_content0"
```

Expected: returns unit JSON rather than a connection error, 404, or localhost Postgres failure.

- [ ] **Step 5: Confirm container sees `DATABASE_URL_REVIEW` without exposing it**

Run:

```powershell
uv run python scripts/portal_admin.py --instance-id i-072319bb6a312ad56 --region eu-west-1 exec --command 'python - <<PY
import os
from urllib.parse import urlparse
url=os.environ.get("DATABASE_URL_REVIEW")
print("DATABASE_URL_REVIEW=set" if url else "DATABASE_URL_REVIEW=missing")
if url:
    parsed=urlparse(url)
    print("host="+parsed.hostname)
    print("db="+parsed.path.lstrip("/"))
PY'
```

Expected:

```text
DATABASE_URL_REVIEW=set
host=<neon-host>
db=<prod-db>
```

If `portal_admin.py` does not support `exec`, use the repo's established SSM command pattern to run the same Python snippet inside the container.

- [ ] **Step 6: Record verification outcome**

Write a short deployment note in the final response with:

```text
API image digest:
UI asset:
CloudFront invalidation:
Neon host/db:
Health result:
Unit API result:
Remaining risks:
```

Do not include database credentials.

---

## Self-Review Notes

- Spec coverage: Covers worktree source, API roll, S3 sync, CloudFront invalidation, Neon env mapping, and CloudFront smoke tests.
- Placeholder scan: No TBD/TODO placeholders remain.
- Type/command consistency: Uses `DATABASE_URL_REVIEW` for runtime and `DATABASE_URL_REVIEW_PROD` only as operator-local source. Uses CloudFront URL `https://d52pmztlzpw34.cloudfront.net`, bucket `ibrary-review-ui-dev-681986854278`, distribution `E2J7Q9XCZKFILO`, and instance `i-072319bb6a312ad56` from existing deployment context.
