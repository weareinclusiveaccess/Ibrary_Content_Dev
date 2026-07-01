# Reviewer Portal User-Specific Reviews — Design Spec

**Status:** Approved for implementation planning  
**Date:** 2026-05-23  
**Context:** Reviewer portal bugfix and workflow refinement

---

## 1. Goals

1. Make reviewer progress specific to each user, so one reviewer submitting a review does not hide the unit from other reviewers.
2. Persist each reviewer's rubric scores, note, and approve/reject outcome as one current review per unit.
3. Give admins a clear summary of all reviewer outcomes before opening a unit, and a complete review view on the unit page.
4. Replace the separate reviewer reject flow with a single review submission form.
5. Add role-aware guidance through tooltips and a How-to page.

---

## 2. Language

This design uses the terms in `CONTEXT.md`.

- A **Review** is one reviewer's current submission for one unit.
- A **Review Outcome** is `approve` or `reject`.
- **My Review State** is what a reviewer sees for their own relationship to a unit.
- A **Review Summary** is the admin aggregate of latest reviews per reviewer.
- **Admin Notes** are persisted separately from reviewer notes.

---

## 3. Current Problems

The current portal uses the unit's global `status` to drive reviewer queue tabs. When one reviewer submits a rubric, the backend marks the unit `verified`; other reviewers then stop seeing the unit in their available queue even though they have not reviewed it.

Reviewer rubric scores are persisted in `content_manual_quality_check`, but the reviewer page does not reload the current user's saved review into the form. When a user opens a reviewed unit again, the rubric defaults to the standard initial values.

The reviewer page also has separate `Submit review`, `Reject`, and `Add note` actions. That splits one reviewer decision across multiple workflows and creates notes that are not clearly attached to a review.

---

## 4. Design Decisions

| Decision | Choice |
|---|---|
| Review cardinality | One current review per reviewer per unit |
| Resubmission | Updates the reviewer's existing review |
| Review outcomes | `approve` or `reject` |
| Rejection note | Required, using the normal reviewer note field |
| Approval note | Optional |
| Admin readiness | First human review of either outcome makes the unit admin-ready |
| Admin publishing | Admin may publish even when some reviewers rejected |
| Published units for reviewers | Visible as read-only in `My reviews` if previously reviewed |
| Review history | Preserved; v1 summary counts latest review per reviewer |
| Standalone reviewer notes | Removed |
| Admin notes | Kept as persisted admin-only notes |
| Reviewer outcome control | Radio buttons |

---

## 5. Backend Design

### 5.1 Review Storage

Continue using `content_manual_quality_check` for human review data, but distinguish row kinds explicitly.

Review rows should have:

- `scores.kind = "review"`
- `scores.outcome = "approve" | "reject"`
- rubric scores:
  - `representation`
  - `engagement`
  - `action_expression`
- `notes` as the reviewer note
- `checked_by` as the reviewer identity

Admin notes should use a separate row kind, such as:

- `scores.kind = "admin_note"`
- `notes` as the admin note
- `checked_by` as the admin identity

Existing audit entries such as publish events can keep their own kind and must not count as reviews.

### 5.2 Uniqueness

The current review for a unit is unique by:

```text
curriculum_unit_id + checked_by + scores.kind = "review"
```

Because this project uses JSON for `scores`, the implementation can enforce this in service logic first. A database-level partial unique index may be added if the selected Postgres target supports the JSON predicate cleanly.

### 5.3 Submit Review API

The reviewer submit endpoint should accept:

```json
{
  "outcome": "approve",
  "representation": 8,
  "engagement": 7.5,
  "action_expression": 8,
  "notes": ""
}
```

Rules:

- `outcome` is required.
- `reject` requires a non-empty `notes` value.
- Resubmission updates the existing current review for `(unit, reviewer)`.
- First review of either outcome makes the unit admin-ready.
- `approve` sets global workflow status to `verified`.
- `reject` sets global workflow status to `rejected`.
- Published units reject review updates with a clear error.

### 5.4 List Units API

The unit list response should include current-user review metadata and admin summary metadata.

```ts
my_review: {
  state: "not_reviewed" | "approved" | "rejected"
  reviewed_at: string | null
  overall_score: number | null
  read_only: boolean
} | null

review_summary: {
  total: number
  approved: number
  rejected: number
}
```

Reviewer UI uses `my_review`, not global workflow status, for reviewer tabs.

Admin UI uses `review_summary` to show review coverage and outcome split in the queue table.

### 5.5 Unit Detail API

The unit detail view should provide:

- the current user's review, for reviewers
- all latest reviewer reviews, for admins
- admin notes, for admins
- global workflow status, for admins and as read-only published state for reviewers

Admins should see reviewer reviews as structured cards with reviewer identity, outcome, rubric scores, overall average, note, and timestamp.

### 5.6 Workflow Status

Reviewer outcomes update the existing global workflow status so the admin queue can keep using the current status model:

- latest submitted `approve` outcome sets status to `verified`
- latest submitted `reject` outcome sets status to `rejected`
- admin publish sets status to `published`
- admin send-back sets status to `draft`

Reviewers do not use `verified` or `rejected` as their visible state. They see **My Review State** plus a read-only `Published` badge when applicable.

---

## 6. Reviewer UI Design

### 6.1 Queue

Reviewer tabs use **My Review State**:

- `Available to review`: units where the user has not reviewed and the unit is not published.
- `My reviews`: units where the user has reviewed, including published units as read-only.

Reviewers should not see the global workflow status values `draft`, `verified`, or `rejected` as their primary status. Published units may show a clear `Published` read-only badge.

### 6.2 Review Form

The review page should show one form containing:

- rubric sliders
- approve/reject radio buttons
- reviewer note textarea
- one `Submit review` button

Validation:

- If `Reject` is selected, reviewer note is required.
- If the unit is published, the form is read-only and submit is disabled.

When the reviewer has already reviewed the unit, the form loads their saved scores, outcome, and note instead of defaulting to initial rubric values.

### 6.3 Removed Reviewer Actions

Remove the standalone reviewer `Add note` action.

Remove the separate reviewer `Reject` button and reject dialog. Rejection is submitted through the normal review form.

---

## 7. Admin UI Design

### 7.1 Queue Summary

The admin queue table should include a `Review Summary` column before the action button.

Examples:

- `1 review: 1 approved, 0 rejected`
- `3 reviews: 2 approved, 1 rejected`
- `2 reviews: 0 approved, 2 rejected`

The table should continue showing global workflow status so admins can distinguish verified, rejected, and published units.

### 7.2 Unit Detail

The admin unit detail sidebar should include:

1. `Review summary`
   - total review count
   - approved count
   - rejected count
2. `Reviewer reviews`
   - one latest review card per reviewer
   - outcome badge
   - rubric scores
   - reviewer note
   - timestamp
3. `Admin notes`
   - existing admin notes
   - `Add admin note` control

Admin notes are persisted separately from reviewer reviews and do not affect review counts.

### 7.3 Admin Decisions

Admins may publish an admin-ready unit even if one or more current reviewer reviews rejected it. The UI should make disagreement visible but not block publishing.

Sending a unit back to draft should keep reviews visible as review history. In v1, because there is no content revision or review round model, review summary still counts the latest review per reviewer.

---

## 8. Guidance Design

### 8.1 Tooltips

Add short tooltips near ambiguous controls:

- Reviewer `Approve`: "Use when the unit is acceptable for admin review."
- Reviewer `Reject`: "Use when the unit needs changes. A note is required."
- Reviewer note: "Required for rejections. Optional rationale for approvals."
- Published badge: "Published units are read-only. Contact an admin if your opinion changed."
- Admin review summary: "Counts the latest review from each reviewer."
- Admin publish button: "Admins may publish after reviewing all available outcomes."
- Admin note: "Admin-only operational note. Does not count as a reviewer review."

### 8.2 How-to Page

Add a role-aware How-to page linked from the portal header.

Reviewer guidance should explain:

- how `Available to review` and `My reviews` work
- how to score the rubric
- how to choose approve or reject
- why rejection notes are required
- why published units become read-only

Admin guidance should explain:

- review summaries and mixed outcomes
- how to read reviewer review cards
- admin notes
- send-back behavior
- publishing despite reviewer disagreement

---

## 9. Data Flow

### Reviewer Submit

```text
Reviewer opens unit
  -> API returns unit + my_review
  -> UI loads saved review or defaults
  -> Reviewer selects outcome, adjusts scores, writes note
  -> Submit review
  -> API upserts current review for this reviewer
  -> API marks unit admin-ready if this is the first human review
  -> Reviewer returns to queue
```

### Admin Review

```text
Admin opens queue
  -> API returns units with review_summary
  -> Admin opens unit
  -> API returns all latest reviewer reviews + admin notes
  -> Admin may add note, send back, or publish
```

---

## 10. Error Handling

- Reject submission without a note returns a validation error.
- Review update on a published unit returns a clear read-only error.
- Review submission for a missing unit returns `404`.
- Admin note submission for a missing unit returns `404`.
- The UI should preserve unsent form values when a submission fails.

---

## 11. Testing

Backend tests should cover:

- reviewer A review does not hide the unit from reviewer B
- approve review creates or updates one current review
- reject review requires a note
- resubmission updates the same reviewer review
- review summary counts latest reviews by unique reviewer and outcome
- admin notes do not affect review summary
- published units reject reviewer updates

Frontend tests or manual verification should cover:

- reviewer queue tabs use `my_review`
- saved rubric scores/outcome/note reload into the form
- reject note validation
- published reviewed unit is read-only in `My reviews`
- admin queue shows review summary split
- admin detail shows reviewer reviews and admin notes separately
- How-to page changes content by role

---

## 12. Out of Scope

- Explicit reviewer assignment or workload management.
- Content versioning or review rounds.
- Blocking publish when reviewers disagree.
- Historical submission timeline for every resubmission.
- Reworking the broader curation pipeline status model.
