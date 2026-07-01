# IAM for Terraform (reviewer portal)

## Target account and role

| | Value |
|--|--------|
| **Account** | `681986854278` (IBrary content dev) |
| **Role** | `content-dev` → `arn:aws:iam::681986854278:role/content-dev` |

Terraform is configured in `environments/dev/versions.tf` to assume this role (see `assume_role_arn` in `terraform.tfvars`).

### Run Terraform with content-dev

**Option 1 — AWS profile (recommended if you use MFA)**

`~/.aws/config` should include something like:

```ini
[profile ibrary-dev]
role_arn       = arn:aws:iam::681986854278:role/content-dev
source_profile = your-base-profile
mfa_serial     = arn:aws:iam::YOUR_ID_ACCOUNT:mfa/YOUR_USER
region         = eu-west-1
```

Then:

```bash
export AWS_PROFILE=ibrary-dev
export AWS_SDK_LOAD_CONFIG=1
cd infra/terraform/environments/dev
# If profile already assumes content-dev, clear double-assume in tfvars:
# assume_role_arn = ""
terraform plan   # check aws_account_id in plan output
terraform apply
```

**Option 2 — Terraform assumes role directly**

In `terraform.tfvars`:

```hcl
assume_role_arn = "arn:aws:iam::681986854278:role/content-dev"
aws_account_id  = "681986854278"
```

Use base credentials that are allowed to `sts:AssumeRole` into `content-dev`, then `terraform apply`.

Verify after plan:

```text
aws_account_id = "681986854278"
aws_caller_arn = "arn:aws:sts::681986854278:assumed-role/content-dev/..."
```

The `content-dev` role (or an attached policy) must allow Cognito create — see `cognito-terraform-deploy-policy.json`.

**IAM policy for the API:** `content-dev` often cannot `iam:CreatePolicy`. In `terraform.tfvars` set `cognito_create_admin_iam_policy = false` (default). After apply, use output `cognito_admin_api_policy_json` or grant the same actions on pool `eu-west-1_*` to whoever runs the review API locally.

**Cognito domain prefix** is globally unique across all AWS accounts. If apply fails with *Domain already associated*, change `cognito_domain_prefix` in `terraform.tfvars` and run `terraform apply` again.

---

## Error: `programuser` cannot `cognito-idp:CreateUserPool`

Terraform needs permission to create Cognito resources. Your IAM user must have the policy in `cognito-terraform-deploy-policy.json` attached.

### Option A — AWS Console (account admin)

1. IAM → Users → **programuser** → Add permissions → Create inline policy → JSON.
2. Paste contents of `cognito-terraform-deploy-policy.json`.
3. Name: `IBraryCognitoTerraformDeploy`.
4. Save, then re-run:

   ```bash
   cd infra/terraform/environments/dev
   terraform apply
   ```

### Option B — AWS CLI (as admin)

```bash
aws iam put-user-policy \
  --user-name programuser \
  --policy-name IBraryCognitoTerraformDeploy \
  --policy-document file://infra/terraform/iam/cognito-terraform-deploy-policy.json
```

### Option C — Use a different AWS profile

If you have an admin profile locally:

```bash
export AWS_PROFILE=your-admin-profile
terraform apply
```

### If you cannot get Cognito permissions

Skip Terraform for now and keep **mock login** + **Neon** for hosting the API/UI. Add Cognito when an account admin grants access.
