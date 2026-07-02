# IAM for the content read API

## Read-only DynamoDB user (Render / external hosting)

The public content API needs **read-only** DynamoDB access. Create a dedicated IAM user (do not reuse your MFA developer profile):

1. IAM → Users → **Create user** → `ibrary-content-api`
2. Attach inline policy from `content-api-readonly-policy.json`
3. Create access key → set in Render env vars:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `CONTENT_API_KEYS` (generate a strong random key for your backend team)

Deploy via `render.yaml` (Render free tier → public HTTPS URL).

## Target account

| | Value |
|--|--------|
| **Account** | `681986854278` |
| **Region** | `eu-west-1` |
| **Table** | `CuratedContent` |
