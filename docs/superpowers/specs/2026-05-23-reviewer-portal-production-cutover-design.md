# Reviewer Portal Production Cutover - Design Spec

**Status:** Approved for implementation planning  
**Date:** 2026-05-23  
**Context:** Deploy the user-specific reviews worktree to EC2/S3/CloudFront with Neon production data

---

## 1. Goal

Deploy the reviewer portal from `.worktrees/reviewer-user-specific-reviews` as one coherent production release so the CloudFront app matches the EC2 API and uses the production Neon review database.

The immediate production failure is a split deployment: the CloudFront UI and EC2 API can be updated independently. The user-specific reviews API rejects legacy standalone reviewer notes, while an old UI bundle still calls those endpoints. The fix is an atomic cutover of the matching worktree API and UI, plus database configuration verification.

---

## 2. Scope

This cutover does four things:

1. Treat `.worktrees/reviewer-user-specific-reviews` as the release source.
2. Deploy the matching API image to EC2.
3. Deploy the matching `review-ui/dist` bundle to the S3 UI bucket and invalidate CloudFront.
4. Ensure the reviewer API reads the production Neon database through the app's expected `DATABASE_URL_REVIEW` environment variable, sourced from the operator's `DATABASE_URL_REVIEW_PROD`.

This does not redesign the reviewer workflow. That behavior is already covered by `docs/superpowers/specs/2026-05-23-reviewer-portal-user-specific-reviews-design.md`.

---

## 3. Current Architecture

Production has two deploy surfaces:

- CloudFront default behavior serves the React SPA from the S3 UI bucket.
- CloudFront `/review/*` and `/health` route to the EC2 reviewer API container.

The Docker image also contains a built UI, but CloudFront does not use that bundled UI for normal `/unit/*` navigation. A successful API roll alone is not enough; the S3 UI bundle must be synced and CloudFront invalidated in the same release.

The reviewer API uses `DATABASE_URL_REVIEW` from app configuration. Locally, the operator may store the production URL as `DATABASE_URL_REVIEW_PROD`, but EC2 reads SSM parameters from `/ibrary/review/*`. Therefore production must have `/ibrary/review/DATABASE_URL_REVIEW` set to the same Neon URL intended by `DATABASE_URL_REVIEW_PROD`.

---

## 4. Release Design

The release source is the worktree at `.worktrees/reviewer-user-specific-reviews`.

Before deployment, run focused verification from that worktree:

- backend review tests for service and publish routes
- frontend production build

For the API release, use the repo's existing ECR and EC2 roll path. The deployed image must be built from the worktree code, not the main workspace. After rolling, `portal-status` or an equivalent health check must show the container healthy.

For the UI release, sync the worktree's `review-ui/dist` to the Terraform `portal_ui_bucket` with `--delete`, then create a CloudFront invalidation for `/*`. Verification must fetch CloudFront `index.html` and confirm it references the newly built asset names.

For database configuration, verify SSM `/ibrary/review/DATABASE_URL_REVIEW` points to the Neon production host/database from `DATABASE_URL_REVIEW_PROD`, with credentials redacted. If the key is missing or points elsewhere, update that SSM key only, then restart or roll the portal container so it reloads runtime env.

---

## 5. Smoke Tests

Smoke testing must target CloudFront, not only localhost:

1. `/health` returns `{"status":"ok"}` through CloudFront.
2. The unit page for `bio_sss1_theme1_topic1_content0` loads from CloudFront.
3. The served JavaScript bundle no longer contains calls to legacy reviewer `fetchNotes`, `postNote`, or `rejectUnit`.
4. Reviewer unit API calls use the new user-specific flow:
   - reviewer submission goes through `/reviewer-scores` or `/reviewer-rubric`
   - admin notes use `/admin-notes`
   - standalone `/notes` is not called by the UI
5. The API can connect to Neon via `DATABASE_URL_REVIEW`.
6. The production Neon database contains the target unit needed for smoke testing.

If a write-path smoke test is run, it must use an existing safe test route or a minimal reversible review submission. Do not create irreversible production data for verification.

---

## 6. Failure Handling

If CloudFront still serves an old bundle after invalidation, verify the S3 sync target bucket and wait for invalidation completion before retrying browser tests.

If EC2 reports healthy but DB-backed endpoints fail, inspect the container runtime env for `DATABASE_URL_REVIEW` and confirm it is not falling back to localhost. Do not run migrations or data writes until the database target is confirmed to be production Neon.

If migrations are missing on Neon, run the repo's normal migration path with the review production URL intentionally mapped into the migration environment. Record the exact command and target host with credentials redacted.

If the target unit is absent from production Neon, treat that as a data deployment problem, not a UI bug. Load or publish the expected unit through the established pipeline path before declaring the portal fixed.

---

## 7. Acceptance Criteria

The cutover is complete when:

- EC2 is running the worktree API image and reports healthy.
- CloudFront serves the worktree UI bundle from S3.
- SSM `/ibrary/review/DATABASE_URL_REVIEW` points at production Neon.
- DB-backed reviewer endpoints connect successfully to Neon.
- The CloudFront unit page works without legacy standalone reviewer note calls.
- The verification notes include commands run, asset/image identifiers, database target with secrets redacted, and any remaining risk.
