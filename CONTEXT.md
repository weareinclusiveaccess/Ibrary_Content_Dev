# IBrary Review Context

This context defines the language for human review of curated learning units before publication.

## Language

**Review**:
A human reviewer submission for one learning unit, made by one reviewer. A reviewer has at most one current review per unit, and resubmitting updates that review.
_Avoid_: Standalone note, audit entry, LLM judge result

**Review Outcome**:
The reviewer's decision for a review: approve or reject. Reviewers choose the outcome explicitly when submitting a review.
_Avoid_: Status, action button

**Approval**:
A review outcome saying the unit is acceptable for admin consideration.
_Avoid_: Verified, published

**Rejection**:
A review outcome saying the unit is not acceptable yet. A rejection must include a reviewer note explaining why.
_Avoid_: Reject special note

**Reviewer Note**:
The human explanation attached to a review. It is required for rejections and optional for approvals.
_Avoid_: Separate rejection reason

**Admin Note**:
A persisted admin comment about a unit, used for operational decisions or follow-up outside a reviewer submission.
_Avoid_: Reviewer note

**Admin-Ready Unit**:
A unit that has at least one human review of either outcome and can be evaluated by an admin for publication or follow-up.
_Avoid_: Fully reviewed, published

**Admin Decision**:
The final admin action on an admin-ready unit, such as publishing it or sending it back for revision. Reviewer disagreement informs the decision but does not block publishing.
_Avoid_: Reviewer approval as final approval

**Published Unit**:
A unit that has been published by an admin. Reviewers can see that it is published and can view prior reviews, but cannot change their review for it in the portal.
_Avoid_: Editable reviewed unit

**My Review State**:
A reviewer's own relationship to a unit: not reviewed, approved, or rejected. It is separate from the unit's global workflow status.
_Avoid_: Local status, reviewer status

**Review Summary**:
The admin-facing aggregate of the latest review per reviewer for a unit, including total unique reviewers and counts by review outcome.
_Avoid_: Review count when outcome split matters

**Review History**:
Past human reviews that remain visible after admin follow-up or revision. Review history should not be silently deleted.
_Avoid_: Clearing reviews

## Example Dialogue

Reviewer: "I reviewed this unit and rejected it because the activities are not accessible enough."

Admin: "I can see your rejection outcome, your rubric scores, and your reviewer note on the unit's review summary."

Reviewer: "Another reviewer may still review the same unit."

Admin: "Yes. The unit is admin-ready after the first review, and I can compare all reviewer outcomes on the same page."
