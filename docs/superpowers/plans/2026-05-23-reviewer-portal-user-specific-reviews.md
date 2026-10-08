# Reviewer Portal User-Specific Reviews Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix reviewer-specific review state, persist reviewer rubric edits, show admin review summaries, separate admin notes, and add role-aware reviewer/admin guidance.

**Architecture:** Keep `content_manual_quality_check` as the storage table, but classify rows by `scores.kind`. Backend service helpers expose current review, review summary, reviewer review cards, and admin notes; the React UI consumes those explicit fields instead of inferring reviewer progress from global unit status.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, React 19, TypeScript, Vite, Tailwind CSS utility classes.

---

## File Structure

- Modify `src/ibrary/review/schemas.py`: add review outcome/request/response models, `my_review`, `review_summary`, and admin note models.
- Modify `src/ibrary/review/service.py`: add review row classification helpers, upsert current review, compute summaries, list admin notes, and block reviewer updates for published units.
- Modify `src/ibrary/review/api.py`: update reviewer-score endpoint, expose admin notes, and include user-aware list/detail data.
- Modify `tests/review/test_service.py`: add service-level tests for review upsert, summary counts, admin notes, and published read-only behavior using mocked sessions.
- Modify `tests/review/test_publish_route.py`: replace old reject-route expectations with submit-review route expectations and admin note route expectations.
- Modify `review-ui/src/lib/api.ts`: add API types and request bodies for review outcomes, summaries, current review, and admin notes.
- Modify `review-ui/src/lib/types.ts`: add UI types for `ReviewOutcome`, `MyReview`, `ReviewSummary`, and `AdminNote`.
- Modify `review-ui/src/lib/mappers.ts`: map backend review metadata into UI shapes.
- Modify `review-ui/src/components/review-queue.tsx`: filter reviewer queues by `myReview`, show published read-only state, and add admin `Review Summary` column.
- Modify `review-ui/src/components/reviewer-rubric-panel.tsx`: add approve/reject radio controls, note validation affordance, read-only mode, and tooltips.
- Modify `review-ui/src/components/unit-review.tsx`: load saved reviews, remove standalone reviewer note/reject actions, handle read-only published units, and support admin notes.
- Modify `review-ui/src/components/admin-judge-sidebar.tsx`: show review summary, reviewer outcome cards, and admin notes separately.
- Create `review-ui/src/components/how-to.tsx`: role-aware How-to page.
- Modify `review-ui/src/routes.tsx`: add `/how-to`.
- Add `review-ui/src/components/ui/tooltip.tsx`: small local tooltip component using native hover/focus behavior.

---

### Task 1: Backend Schema Contract

**Files:**
- Modify: `src/ibrary/review/schemas.py`
- Test: `tests/review/test_service.py`

- [ ] **Step 1: Add failing schema expectations**

Add these imports and tests to `tests/review/test_service.py`:

```python
from pydantic import ValidationError

from ibrary.review.schemas import ReviewerRubricRequest
```

```python
def test_reviewer_rubric_request_requires_valid_outcome():
    body = ReviewerRubricRequest(
        outcome="approve",
        representation=8,
        engagement=7,
        action_expression=7.5,
        notes="",
    )
    assert body.outcome == "approve"

    with pytest.raises(ValidationError):
        ReviewerRubricRequest(
            outcome="maybe",
            representation=8,
            engagement=7,
            action_expression=7.5,
        )
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `uv run pytest tests/review/test_service.py::test_reviewer_rubric_request_requires_valid_outcome -v`

Expected: fail because `ReviewerRubricRequest` does not have an `outcome` field yet.

- [ ] **Step 3: Extend review schemas**

In `src/ibrary/review/schemas.py`, add these models above `UnitListItem`:

```python
from typing import Literal

ReviewOutcome = Literal["approve", "reject"]
MyReviewState = Literal["not_reviewed", "approved", "rejected"]


class MyReviewOut(BaseModel):
    state: MyReviewState = "not_reviewed"
    reviewed_at: str | None = None
    overall_score: float | None = None
    read_only: bool = False


class ReviewSummaryOut(BaseModel):
    total: int = 0
    approved: int = 0
    rejected: int = 0


class AdminNoteOut(BaseModel):
    author: str | None = None
    date: str | None = None
    text: str
```

Update `UnitListItem`:

```python
class UnitListItem(BaseModel):
    curriculum_unit_id: str
    title: str | None = None
    subtopic: str | None = None
    class_name: str | None = None
    theme_number: int | None = None
    topic_number: int | None = None
    status: str
    theme: str | None = None
    overall_score: float | None = None
    passed: bool | None = None
    updated_at: str | None = None
    my_review: MyReviewOut = Field(default_factory=MyReviewOut)
    review_summary: ReviewSummaryOut = Field(default_factory=ReviewSummaryOut)
```

Update `UnitDetailResponse`:

```python
class UnitDetailResponse(BaseModel):
    curriculum_unit_id: str
    title: str | None = None
    subtopic: str | None = None
    class_name: str | None = None
    theme: str | None = None
    theme_number: int | None = None
    topic_number: int | None = None
    status: str
    learning_objectives: list[str] = Field(default_factory=list)
    curated_content_md: str = ""
    key_takeaways: list[str] = Field(default_factory=list)
    student_activities: list[str] = Field(default_factory=list)
    teacher_activities: list[str] = Field(default_factory=list)
    accessibility_checklist: list[str] = Field(default_factory=list)
    images: list[ImageAsset] = Field(default_factory=list)
    prompt_version: str | None = None
    model_version: str | None = None
    updated_at: str | None = None
    my_review: MyReviewOut = Field(default_factory=MyReviewOut)
    review_summary: ReviewSummaryOut = Field(default_factory=ReviewSummaryOut)
```

Replace `ReviewerRubricRequest`:

```python
class ReviewerRubricRequest(BaseModel):
    """Human UDL principle scores and approve/reject outcome from a reviewer."""

    outcome: ReviewOutcome
    representation: float = Field(ge=0, le=10)
    engagement: float = Field(ge=0, le=10)
    action_expression: float = Field(ge=0, le=10)
    notes: str = ""
    checked_by: str | None = None
    mark_verified: bool = True
```

Update `ReviewerScoreOut`:

```python
class ReviewerScoreOut(BaseModel):
    id: int
    reviewer: str | None = None
    date: str | None = None
    outcome: ReviewOutcome = "approve"
    representation: float
    engagement: float
    action_expression: float
    overall_score: float | None = None
    notes: str = ""
```

Add an admin note request body near `NotesRequest`:

```python
class AdminNoteRequest(BaseModel):
    notes: str = Field(min_length=1)
```

- [ ] **Step 4: Run the schema test again**

Run: `uv run pytest tests/review/test_service.py::test_reviewer_rubric_request_requires_valid_outcome -v`

Expected: pass.

- [ ] **Step 5: Checkpoint commit**

Only commit if the user has requested commits for this implementation session.

```bash
git add src/ibrary/review/schemas.py tests/review/test_service.py
git commit -m "Add reviewer outcome schema contract"
```

---

### Task 2: Backend Review Classification Helpers

**Files:**
- Modify: `src/ibrary/review/service.py`
- Test: `tests/review/test_service.py`

- [ ] **Step 1: Add failing helper tests**

Add these tests to `tests/review/test_service.py`:

```python
def test_row_to_reviewer_score_reads_review_outcome():
    from types import SimpleNamespace

    from ibrary.review.service import _row_to_reviewer_score

    row = SimpleNamespace(
        id=1,
        checked_by="reviewer@example.com",
        created_at=None,
        overall_score=7.5,
        notes="Needs stronger accessibility support",
        scores={
            "kind": "review",
            "outcome": "reject",
            "representation": 7,
            "engagement": 8,
            "action_expression": 7.5,
        },
    )

    score = _row_to_reviewer_score(row)

    assert score is not None
    assert score.outcome == "reject"
    assert score.reviewer == "reviewer@example.com"
    assert score.notes == "Needs stronger accessibility support"


def test_row_to_reviewer_score_treats_legacy_rubric_as_approve():
    from types import SimpleNamespace

    from ibrary.review.service import _row_to_reviewer_score

    row = SimpleNamespace(
        id=2,
        checked_by="legacy@example.com",
        created_at=None,
        overall_score=8,
        notes="Looks good",
        scores={
            "kind": "rubric",
            "representation": 8,
            "engagement": 8,
            "action_expression": 8,
        },
    )

    score = _row_to_reviewer_score(row)

    assert score is not None
    assert score.outcome == "approve"
```

- [ ] **Step 2: Run helper tests and verify failure**

Run: `uv run pytest tests/review/test_service.py::test_row_to_reviewer_score_reads_review_outcome tests/review/test_service.py::test_row_to_reviewer_score_treats_legacy_rubric_as_approve -v`

Expected: fail because `ReviewerScoreOut` mapping does not include `outcome`.

- [ ] **Step 3: Add constants and helper functions**

In `src/ibrary/review/service.py`, update imports:

```python
from ibrary.review.schemas import (
    AdminNoteOut,
    CheckpointScoreOut,
    ImageAsset,
    JudgeReportResponse,
    MyReviewOut,
    ReviewSummaryOut,
    ReviewerNoteOut,
    ReviewerScoreOut,
    UnitDetailResponse,
    UnitListItem,
    UnitListResponse,
)
```

Add constants below `RUBRIC_SCORE_KEYS`:

```python
REVIEW_KIND = "review"
LEGACY_RUBRIC_KIND = "rubric"
ADMIN_NOTE_KIND = "admin_note"
AUDIT_KINDS = frozenset({"publish", "rejection"})
REVIEW_OUTCOMES = frozenset({"approve", "reject"})
```

Add these helpers after `_rubric_scores`:

```python
def _score_kind(raw: dict | None) -> str | None:
    if not isinstance(raw, dict):
        return None
    kind = raw.get("kind")
    return kind if isinstance(kind, str) else None


def _is_review_scores(raw: dict | None) -> bool:
    if not isinstance(raw, dict):
        return False
    kind = _score_kind(raw)
    return kind in {REVIEW_KIND, LEGACY_RUBRIC_KIND} or any(k in raw for k in RUBRIC_SCORE_KEYS)


def _review_outcome(raw: dict | None) -> str:
    if not isinstance(raw, dict):
        return "approve"
    outcome = raw.get("outcome")
    return outcome if outcome in REVIEW_OUTCOMES else "approve"


def _is_admin_note_scores(raw: dict | None) -> bool:
    return _score_kind(raw) == ADMIN_NOTE_KIND
```

Replace `_rubric_scores`:

```python
def _rubric_scores(raw: dict | None) -> dict[str, float] | None:
    if not _is_review_scores(raw):
        return None
    return {
        "representation": float(raw.get("representation") or 0),
        "engagement": float(raw.get("engagement") or 0),
        "action_expression": float(raw.get("action_expression") or 0),
    }
```

Replace `_row_to_reviewer_score`:

```python
def _row_to_reviewer_score(row: ContentManualQualityCheck) -> ReviewerScoreOut | None:
    scores = row.scores if isinstance(row.scores, dict) else None
    rubric = _rubric_scores(scores)
    if not rubric:
        return None
    overall = row.overall_score
    if overall is None:
        overall = round(
            (rubric["representation"] + rubric["engagement"] + rubric["action_expression"]) / 3,
            2,
        )
    return ReviewerScoreOut(
        id=row.id,
        reviewer=row.checked_by,
        date=_iso_dt(row.created_at),
        outcome=_review_outcome(scores),
        representation=rubric["representation"],
        engagement=rubric["engagement"],
        action_expression=rubric["action_expression"],
        overall_score=overall,
        notes=row.notes or "",
    )
```

- [ ] **Step 4: Run helper tests again**

Run: `uv run pytest tests/review/test_service.py::test_row_to_reviewer_score_reads_review_outcome tests/review/test_service.py::test_row_to_reviewer_score_treats_legacy_rubric_as_approve -v`

Expected: pass.

- [ ] **Step 5: Checkpoint commit**

Only commit if the user has requested commits for this implementation session.

```bash
git add src/ibrary/review/service.py tests/review/test_service.py
git commit -m "Classify human review rows by outcome"
```

---

### Task 3: Backend Review Upsert and Summary

**Files:**
- Modify: `src/ibrary/review/service.py`
- Test: `tests/review/test_service.py`

- [ ] **Step 1: Add service tests for upsert rules**

Add these tests with small in-memory fakes to `tests/review/test_service.py`:

```python
class _FakeQuery:
    def __init__(self, result):
        self.result = result

    def filter(self, *args, **kwargs):
        return self

    def one_or_none(self):
        return self.result

    def scalar(self):
        return self.result


class _FakeSession:
    def __init__(self, curated=None, existing_review=None):
        self.curated = curated
        self.existing_review = existing_review
        self.added = []
        self.committed = False
        self.closed = False
        self._query_count = 0

    def query(self, model):
        self._query_count += 1
        if self._query_count == 1:
            return _FakeQuery(self.curated)
        return _FakeQuery(self.existing_review)

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def test_submit_review_creates_review_and_sets_verified(monkeypatch):
    from types import SimpleNamespace

    from ibrary.review import service

    curated = SimpleNamespace(curriculum_unit_id="unit-1", status="draft", updated_at=None)
    session = _FakeSession(curated=curated, existing_review=None)
    monkeypatch.setattr(service, "get_review_session", lambda: session)

    ok = service.submit_reviewer_rubric(
        "unit-1",
        outcome="approve",
        representation=8,
        engagement=7,
        action_expression=7.5,
        notes="Good enough",
        checked_by="reviewer@example.com",
    )

    assert ok is True
    assert curated.status == "verified"
    assert session.committed is True
    assert len(session.added) == 1
    assert session.added[0].scores["kind"] == "review"
    assert session.added[0].scores["outcome"] == "approve"


def test_submit_review_updates_existing_review(monkeypatch):
    from types import SimpleNamespace

    from ibrary.review import service

    curated = SimpleNamespace(curriculum_unit_id="unit-1", status="draft", updated_at=None)
    existing = SimpleNamespace(
        notes="Old note",
        overall_score=5,
        checked_by="reviewer@example.com",
        scores={
            "kind": "review",
            "outcome": "reject",
            "representation": 5,
            "engagement": 5,
            "action_expression": 5,
        },
        updated_at=None,
    )
    session = _FakeSession(curated=curated, existing_review=existing)
    monkeypatch.setattr(service, "get_review_session", lambda: session)

    ok = service.submit_reviewer_rubric(
        "unit-1",
        outcome="approve",
        representation=9,
        engagement=8,
        action_expression=7,
        notes="Updated note",
        checked_by="reviewer@example.com",
    )

    assert ok is True
    assert len(session.added) == 0
    assert existing.notes == "Updated note"
    assert existing.scores["outcome"] == "approve"
    assert existing.overall_score == 8
    assert curated.status == "verified"


def test_submit_review_reject_requires_note(monkeypatch):
    from types import SimpleNamespace

    from ibrary.review import service

    curated = SimpleNamespace(curriculum_unit_id="unit-1", status="draft", updated_at=None)
    session = _FakeSession(curated=curated, existing_review=None)
    monkeypatch.setattr(service, "get_review_session", lambda: session)

    with pytest.raises(ValueError, match="Reviewer note is required for rejected reviews"):
        service.submit_reviewer_rubric(
            "unit-1",
            outcome="reject",
            representation=4,
            engagement=4,
            action_expression=4,
            notes=" ",
            checked_by="reviewer@example.com",
        )


def test_submit_review_blocks_published_unit(monkeypatch):
    from types import SimpleNamespace

    from ibrary.review import service

    curated = SimpleNamespace(curriculum_unit_id="unit-1", status="published", updated_at=None)
    session = _FakeSession(curated=curated, existing_review=None)
    monkeypatch.setattr(service, "get_review_session", lambda: session)

    with pytest.raises(ValueError, match="Published units are read-only"):
        service.submit_reviewer_rubric(
            "unit-1",
            outcome="approve",
            representation=8,
            engagement=8,
            action_expression=8,
            notes="",
            checked_by="reviewer@example.com",
        )
```

- [ ] **Step 2: Run upsert tests and verify failure**

Run: `uv run pytest tests/review/test_service.py::test_submit_review_creates_review_and_sets_verified tests/review/test_service.py::test_submit_review_updates_existing_review tests/review/test_service.py::test_submit_review_reject_requires_note tests/review/test_service.py::test_submit_review_blocks_published_unit -v`

Expected: fail because `submit_reviewer_rubric` does not accept `outcome` or upsert.

- [ ] **Step 3: Replace `submit_reviewer_rubric` implementation**

In `src/ibrary/review/service.py`, replace `submit_reviewer_rubric` with:

```python
def submit_reviewer_rubric(
    curriculum_unit_id: str,
    *,
    outcome: str,
    representation: float,
    engagement: float,
    action_expression: float,
    notes: str = "",
    checked_by: str | None = None,
    mark_verified: bool = True,
) -> bool:
    if outcome not in REVIEW_OUTCOMES:
        raise ValueError("outcome must be approve or reject")
    clean_notes = notes.strip()
    if outcome == "reject" and not clean_notes:
        raise ValueError("Reviewer note is required for rejected reviews")
    if not checked_by:
        raise ValueError("checked_by is required")

    session = get_review_session()
    try:
        row = (
            session.query(CuratedContent)
            .filter(CuratedContent.curriculum_unit_id == curriculum_unit_id)
            .one_or_none()
        )
        if not row:
            return False
        if row.status == "published":
            raise ValueError("Published units are read-only for reviewer updates")

        existing = (
            session.query(ContentManualQualityCheck)
            .filter(ContentManualQualityCheck.curriculum_unit_id == curriculum_unit_id)
            .filter(ContentManualQualityCheck.checked_by == checked_by)
            .one_or_none()
        )
        if existing and not _is_review_scores(existing.scores if isinstance(existing.scores, dict) else None):
            existing = None

        overall = round((representation + engagement + action_expression) / 3, 2)
        scores = {
            "kind": REVIEW_KIND,
            "outcome": outcome,
            "representation": representation,
            "engagement": engagement,
            "action_expression": action_expression,
        }

        if existing:
            existing.notes = clean_notes or None
            existing.overall_score = overall
            existing.scores = scores
            existing.updated_at = dt.datetime.utcnow()
        else:
            session.add(
                ContentManualQualityCheck(
                    curriculum_unit_id=curriculum_unit_id,
                    notes=clean_notes or None,
                    overall_score=overall,
                    checked_by=checked_by,
                    scores=scores,
                )
            )

        if mark_verified:
            row.status = "verified" if outcome == "approve" else "rejected"
            row.updated_at = dt.datetime.utcnow()
        session.commit()
        return True
    finally:
        session.close()
```

- [ ] **Step 4: Add summary helper functions**

Add these functions below `list_reviewer_scores`:

```python
def _review_summary_from_scores(scores: list[ReviewerScoreOut]) -> ReviewSummaryOut:
    approved = sum(1 for score in scores if score.outcome == "approve")
    rejected = sum(1 for score in scores if score.outcome == "reject")
    return ReviewSummaryOut(total=approved + rejected, approved=approved, rejected=rejected)


def _my_review_from_scores(
    scores: list[ReviewerScoreOut],
    *,
    reviewer_email: str | None,
    unit_status: str,
) -> MyReviewOut:
    if not reviewer_email:
        return MyReviewOut(read_only=unit_status == "published")
    for score in scores:
        if score.reviewer == reviewer_email:
            return MyReviewOut(
                state="approved" if score.outcome == "approve" else "rejected",
                reviewed_at=score.date,
                overall_score=score.overall_score,
                read_only=unit_status == "published",
            )
    return MyReviewOut(state="not_reviewed", read_only=unit_status == "published")
```

- [ ] **Step 5: Run upsert tests again**

Run: `uv run pytest tests/review/test_service.py::test_submit_review_creates_review_and_sets_verified tests/review/test_service.py::test_submit_review_updates_existing_review tests/review/test_service.py::test_submit_review_reject_requires_note tests/review/test_service.py::test_submit_review_blocks_published_unit -v`

Expected: pass.

- [ ] **Step 6: Checkpoint commit**

Only commit if the user has requested commits for this implementation session.

```bash
git add src/ibrary/review/service.py tests/review/test_service.py
git commit -m "Upsert user-specific reviewer submissions"
```

---

### Task 4: Backend List and Detail Metadata

**Files:**
- Modify: `src/ibrary/review/service.py`
- Modify: `src/ibrary/review/api.py`
- Test: `tests/review/test_publish_route.py`

- [ ] **Step 1: Add route test for list user metadata**

Add this test to `tests/review/test_publish_route.py`:

```python
def test_list_units_passes_current_user_email(admin_client):
    with patch.object(
        review_api.service,
        "list_units",
        return_value={
            "items": [],
            "total": 0,
            "offset": 0,
            "limit": 50,
        },
    ) as mock_list:
        resp = admin_client.get("/review/units")

    assert resp.status_code == 200
    _, kwargs = mock_list.call_args
    assert kwargs["current_user_email"] == "admin@example.com"
```

- [ ] **Step 2: Run route test and verify failure**

Run: `uv run pytest tests/review/test_publish_route.py::test_list_units_passes_current_user_email -v`

Expected: fail because route does not pass `current_user_email`.

- [ ] **Step 3: Update service signatures**

In `src/ibrary/review/service.py`, change `list_units` signature:

```python
def list_units(
    *,
    offset: int = 0,
    limit: int = 50,
    status: str | None = None,
    theme_number: int | None = None,
    topic_number: int | None = None,
    q: str | None = None,
    current_user_email: str | None = None,
) -> UnitListResponse:
```

Inside the `for curated, judge in rows:` loop, fetch reviewer scores and add metadata:

```python
            reviewer_scores = list_reviewer_scores(curated.curriculum_unit_id)
            review_summary = _review_summary_from_scores(reviewer_scores)
            my_review = _my_review_from_scores(
                reviewer_scores,
                reviewer_email=current_user_email,
                unit_status=curated.status or "draft",
            )
```

Add the fields to `UnitListItem`:

```python
                    my_review=my_review,
                    review_summary=review_summary,
```

Change `get_unit` signature:

```python
def get_unit(curriculum_unit_id: str, current_user_email: str | None = None) -> UnitDetailResponse | None:
```

Before returning `UnitDetailResponse`, compute:

```python
        reviewer_scores = list_reviewer_scores(curriculum_unit_id)
        review_summary = _review_summary_from_scores(reviewer_scores)
        my_review = _my_review_from_scores(
            reviewer_scores,
            reviewer_email=current_user_email,
            unit_status=row.status or "draft",
        )
```

Add to `UnitDetailResponse`:

```python
            my_review=my_review,
            review_summary=review_summary,
```

- [ ] **Step 4: Update API route calls**

In `src/ibrary/review/api.py`, update `list_units` route parameter name from `_user` to `user` and pass the email:

```python
    user: CognitoClaims = Depends(current_user),
):
    return service.list_units(
        offset=offset,
        limit=limit,
        status=status,
        theme_number=theme_number,
        topic_number=topic_number,
        q=q,
        current_user_email=user.email,
    )
```

Update `get_unit` route:

```python
def get_unit(curriculum_unit_id: str, user: CognitoClaims = Depends(current_user)):
    unit = service.get_unit(curriculum_unit_id, current_user_email=user.email)
```

Update `post_reviewer_rubric` to pass outcome and handle validation errors:

```python
    try:
        ok = service.submit_reviewer_rubric(
            curriculum_unit_id,
            outcome=body.outcome,
            representation=body.representation,
            engagement=body.engagement,
            action_expression=body.action_expression,
            notes=body.notes,
            checked_by=body.checked_by or user.email,
            mark_verified=body.mark_verified,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

- [ ] **Step 5: Run route test again**

Run: `uv run pytest tests/review/test_publish_route.py::test_list_units_passes_current_user_email -v`

Expected: pass.

- [ ] **Step 6: Run full review backend tests**

Run: `uv run pytest tests/review -v`

Expected: pass. If legacy `/reject` route tests fail because the route remains unchanged, keep the route for backward compatibility and adjust only tests that conflict with the new reviewer UI contract.

- [ ] **Step 7: Checkpoint commit**

Only commit if the user has requested commits for this implementation session.

```bash
git add src/ibrary/review/service.py src/ibrary/review/api.py tests/review/test_publish_route.py
git commit -m "Return user-specific review metadata"
```

---

### Task 5: Backend Admin Notes

**Files:**
- Modify: `src/ibrary/review/service.py`
- Modify: `src/ibrary/review/api.py`
- Test: `tests/review/test_publish_route.py`

- [ ] **Step 1: Add route tests for admin notes**

Add this test to `tests/review/test_publish_route.py`:

```python
def test_admin_notes_route_persists_admin_note(admin_client):
    with patch.object(review_api.service, "add_admin_note", return_value=True) as mock_add:
        resp = admin_client.post(
            "/review/units/bio_sss1_theme1_topic1_content0/admin-notes",
            json={"notes": "Wait for biology lead before publishing."},
        )

    assert resp.status_code == 200
    assert resp.json() == {"saved": True}
    mock_add.assert_called_once_with(
        "bio_sss1_theme1_topic1_content0",
        notes="Wait for biology lead before publishing.",
        checked_by="admin@example.com",
    )
```

- [ ] **Step 2: Run admin note route test and verify failure**

Run: `uv run pytest tests/review/test_publish_route.py::test_admin_notes_route_persists_admin_note -v`

Expected: fail because route and service function do not exist.

- [ ] **Step 3: Add service functions**

Add to `src/ibrary/review/service.py` after `add_manual_note`:

```python
def list_admin_notes(curriculum_unit_id: str) -> list[AdminNoteOut]:
    session = get_review_session()
    try:
        rows = (
            session.query(ContentManualQualityCheck)
            .filter(ContentManualQualityCheck.curriculum_unit_id == curriculum_unit_id)
            .order_by(ContentManualQualityCheck.created_at.desc())
            .all()
        )
        out: list[AdminNoteOut] = []
        for row in rows:
            scores = row.scores if isinstance(row.scores, dict) else None
            if not _is_admin_note_scores(scores):
                continue
            if not row.notes or not row.notes.strip():
                continue
            out.append(
                AdminNoteOut(
                    author=row.checked_by,
                    date=_iso_dt(row.created_at),
                    text=row.notes,
                )
            )
        return out
    finally:
        session.close()


def add_admin_note(
    curriculum_unit_id: str,
    *,
    notes: str,
    checked_by: str | None = None,
) -> bool:
    clean_notes = notes.strip()
    if not clean_notes:
        raise ValueError("Admin note is required")

    session = get_review_session()
    try:
        exists = (
            session.query(CuratedContent.curriculum_unit_id)
            .filter(CuratedContent.curriculum_unit_id == curriculum_unit_id)
            .scalar()
        )
        if not exists:
            return False
        session.add(
            ContentManualQualityCheck(
                curriculum_unit_id=curriculum_unit_id,
                notes=clean_notes,
                checked_by=checked_by,
                scores={"kind": ADMIN_NOTE_KIND},
            )
        )
        session.commit()
        return True
    finally:
        session.close()
```

- [ ] **Step 4: Add API routes**

In `src/ibrary/review/api.py`, import `AdminNoteRequest` and `AdminNoteOut` from schemas.

Add routes near existing note routes:

```python
@app.get(
    "/review/units/{curriculum_unit_id}/admin-notes",
    response_model=list[AdminNoteOut],
)
def get_admin_notes(
    curriculum_unit_id: str,
    _admin: CognitoClaims = Depends(require_admin),
):
    return service.list_admin_notes(curriculum_unit_id)


@app.post("/review/units/{curriculum_unit_id}/admin-notes")
def post_admin_note(
    curriculum_unit_id: str,
    body: AdminNoteRequest,
    admin: CognitoClaims = Depends(require_admin),
):
    try:
        ok = service.add_admin_note(
            curriculum_unit_id,
            notes=body.notes,
            checked_by=admin.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="Unit not found")
    return {"saved": True}
```

- [ ] **Step 5: Run admin note test again**

Run: `uv run pytest tests/review/test_publish_route.py::test_admin_notes_route_persists_admin_note -v`

Expected: pass.

- [ ] **Step 6: Checkpoint commit**

Only commit if the user has requested commits for this implementation session.

```bash
git add src/ibrary/review/service.py src/ibrary/review/api.py tests/review/test_publish_route.py
git commit -m "Add persisted admin notes"
```

---

### Task 6: Frontend API Types and Mappers

**Files:**
- Modify: `review-ui/src/lib/api.ts`
- Modify: `review-ui/src/lib/types.ts`
- Modify: `review-ui/src/lib/mappers.ts`

- [ ] **Step 1: Update UI type definitions**

In `review-ui/src/lib/types.ts`, add:

```ts
export type ReviewOutcome = "approve" | "reject";
export type MyReviewState = "not_reviewed" | "approved" | "rejected";

export interface MyReview {
  state: MyReviewState;
  reviewedAt: string;
  overallScore: number | null;
  readOnly: boolean;
}

export interface ReviewSummary {
  total: number;
  approved: number;
  rejected: number;
}

export interface AdminNote {
  author: string;
  date: string;
  text: string;
}
```

Update `UnitRow`:

```ts
export interface UnitRow {
  id: string;
  title: string;
  theme: string;
  topic: string;
  status: Status;
  judgeScore: number;
  passFail: PassFail;
  updated: string;
  myReview: MyReview;
  reviewSummary: ReviewSummary;
}
```

Update `UnitDetail`:

```ts
export interface UnitDetail {
  id: string;
  title: string;
  theme: string;
  topic: string;
  className: string;
  status: Status;
  learningObjectives: string[];
  lessonBody: string;
  figures: Figure[];
  lastUpdated: string;
  modelVersion: string;
  promptVersion: string;
  myReview: MyReview;
  reviewSummary: ReviewSummary;
}
```

Update `ReviewerScoreUi`:

```ts
export interface ReviewerScoreUi {
  id: number;
  reviewer: string;
  date: string;
  outcome: ReviewOutcome;
  representation: number;
  engagement: number;
  actionExpression: number;
  overallScore: number;
  notes: string;
}
```

Update `RubricDraft`:

```ts
export interface RubricDraft {
  outcome: ReviewOutcome;
  representation: number;
  engagement: number;
  actionExpression: number;
  notes: string;
}
```

- [ ] **Step 2: Update API types**

In `review-ui/src/lib/api.ts`, add:

```ts
export interface ApiMyReview {
  state: "not_reviewed" | "approved" | "rejected";
  reviewed_at: string | null;
  overall_score: number | null;
  read_only: boolean;
}

export interface ApiReviewSummary {
  total: number;
  approved: number;
  rejected: number;
}

export interface ApiAdminNote {
  author: string | null;
  date: string | null;
  text: string;
}
```

Add fields to `ApiUnitListItem` and `ApiUnitDetail`:

```ts
  my_review: ApiMyReview;
  review_summary: ApiReviewSummary;
```

Update `ApiReviewerScore`:

```ts
export interface ApiReviewerScore {
  id: number;
  reviewer: string | null;
  date: string | null;
  outcome: "approve" | "reject";
  representation: number;
  engagement: number;
  action_expression: number;
  overall_score: number | null;
  notes: string;
}
```

Update `ApiReviewerRubricBody`:

```ts
export interface ApiReviewerRubricBody {
  outcome: "approve" | "reject";
  representation: number;
  engagement: number;
  action_expression: number;
  notes?: string;
  checked_by?: string;
  mark_verified?: boolean;
}
```

Add admin note API functions:

```ts
export async function fetchAdminNotes(unitId: string): Promise<ApiAdminNote[]> {
  return apiFetch(`/review/units/${encodeURIComponent(unitId)}/admin-notes`);
}

export async function postAdminNote(unitId: string, notes: string): Promise<void> {
  await apiFetch(`/review/units/${encodeURIComponent(unitId)}/admin-notes`, {
    method: "POST",
    body: JSON.stringify({ notes }),
  });
}
```

- [ ] **Step 3: Update mappers**

In `review-ui/src/lib/mappers.ts`, import `ApiAdminNote`, `ApiMyReview`, and `ApiReviewSummary`.

Add helpers:

```ts
function mapMyReview(review: ApiMyReview | null | undefined) {
  return {
    state: review?.state ?? "not_reviewed",
    reviewedAt: review?.reviewed_at ? formatDate(review.reviewed_at) : "—",
    overallScore: review?.overall_score ?? null,
    readOnly: review?.read_only ?? false,
  };
}

function mapReviewSummary(summary: ApiReviewSummary | null | undefined) {
  return {
    total: summary?.total ?? 0,
    approved: summary?.approved ?? 0,
    rejected: summary?.rejected ?? 0,
  };
}
```

Update `mapUnitRow`:

```ts
    myReview: mapMyReview(item.my_review),
    reviewSummary: mapReviewSummary(item.review_summary),
```

Update `mapUnitDetail`:

```ts
    myReview: mapMyReview(item.my_review),
    reviewSummary: mapReviewSummary(item.review_summary),
```

Update `mapReviewerScore`:

```ts
    outcome: row.outcome,
```

Add:

```ts
export function mapAdminNote(note: ApiAdminNote): AdminNote {
  return {
    author: note.author ?? "Admin",
    date: note.date ? formatDate(note.date) : "—",
    text: note.text,
  };
}
```

- [ ] **Step 4: Run frontend typecheck**

Run: `cd review-ui && npm run build`

Expected: fail at this point because consuming components still need updates. Keep the errors for Task 7 and Task 8.

- [ ] **Step 5: Checkpoint commit**

Only commit if the user has requested commits for this implementation session.

```bash
git add review-ui/src/lib/api.ts review-ui/src/lib/types.ts review-ui/src/lib/mappers.ts
git commit -m "Add frontend review metadata types"
```

---

### Task 7: Reviewer Queue and Review Form UI

**Files:**
- Modify: `review-ui/src/components/review-queue.tsx`
- Modify: `review-ui/src/components/reviewer-rubric-panel.tsx`
- Modify: `review-ui/src/components/unit-review.tsx`
- Create: `review-ui/src/components/ui/tooltip.tsx`

- [ ] **Step 1: Add tooltip component**

Create `review-ui/src/components/ui/tooltip.tsx`:

```tsx
import type { ReactNode } from "react";

export function Tooltip({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <span className="group relative inline-flex items-center">
      {children}
      <span className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 hidden w-64 -translate-x-1/2 rounded-md border bg-white px-3 py-2 text-xs text-neutral-700 shadow-lg group-hover:block group-focus-within:block">
        {label}
      </span>
    </span>
  );
}
```

- [ ] **Step 2: Update reviewer queue tab matching**

In `review-ui/src/components/review-queue.tsx`, replace `matchesTab` with:

```ts
function matchesTab(unit: UnitRow, tab: QueueTab, role: "reviewer" | "admin"): boolean {
  if (role === "reviewer") {
    if (tab === "available") {
      return unit.myReview.state === "not_reviewed" && !unit.myReview.readOnly;
    }
    return unit.myReview.state !== "not_reviewed";
  }
  if (tab === "available") {
    return unit.status === "verified" || unit.status === "rejected";
  }
  return unit.status === "published";
}
```

Add an admin column header before `Updated`:

```tsx
{user.role === "admin" && <th className="p-3 font-medium">Review Summary</th>}
```

Add the admin cell before `Updated`:

```tsx
{user.role === "admin" && (
  <td className="p-3">
    <ReviewSummaryCell summary={unit.reviewSummary} />
  </td>
)}
```

Add a reviewer state cell in place of global status for reviewers:

```tsx
<td className="p-3">
  {user.role === "admin" ? (
    <StatusBadge status={unit.status} />
  ) : (
    <MyReviewBadge unit={unit} />
  )}
</td>
```

Add helper components at the bottom:

```tsx
function MyReviewBadge({ unit }: { unit: UnitRow }) {
  if (unit.myReview.readOnly) {
    return <Badge className="bg-purple-50 text-purple-700">Published · read-only</Badge>;
  }
  if (unit.myReview.state === "approved") {
    return <Badge className="bg-green-50 text-green-700">Approved by you</Badge>;
  }
  if (unit.myReview.state === "rejected") {
    return <Badge className="bg-red-50 text-red-700">Rejected by you</Badge>;
  }
  return <Badge className="bg-neutral-100 text-neutral-700">Not reviewed</Badge>;
}

function ReviewSummaryCell({ summary }: { summary: UnitRow["reviewSummary"] }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-neutral-700">{summary.total} review{summary.total === 1 ? "" : "s"}</span>
      <Badge className="bg-green-50 text-green-700">{summary.approved} approved</Badge>
      <Badge className="bg-red-50 text-red-700">{summary.rejected} rejected</Badge>
    </div>
  );
}
```

- [ ] **Step 3: Update reviewer rubric panel**

In `review-ui/src/components/reviewer-rubric-panel.tsx`, import `Tooltip`:

```ts
import { Tooltip } from "./ui/tooltip";
```

Add an outcome section before the score average:

```tsx
<div className="mb-6 rounded-md border bg-neutral-50 p-4">
  <div className="mb-3 text-sm font-medium">Review outcome</div>
  <div className="flex gap-4">
    <Tooltip label="Use when the unit is acceptable for admin review.">
      <label className="flex cursor-pointer items-center gap-2 text-sm">
        <input
          type="radio"
          name="review-outcome"
          value="approve"
          checked={draft.outcome === "approve"}
          disabled={readOnly}
          onChange={() => onChange({ ...draft, outcome: "approve" })}
        />
        Approve
      </label>
    </Tooltip>
    <Tooltip label="Use when the unit needs changes. A note is required.">
      <label className="flex cursor-pointer items-center gap-2 text-sm">
        <input
          type="radio"
          name="review-outcome"
          value="reject"
          checked={draft.outcome === "reject"}
          disabled={readOnly}
          onChange={() => onChange({ ...draft, outcome: "reject" })}
        />
        Reject
      </label>
    </Tooltip>
  </div>
</div>
```

Update note heading:

```tsx
<h3 className="mb-2 text-sm font-medium">
  Review note {draft.outcome === "reject" ? "(required)" : "(optional)"}
</h3>
<p className="mb-3 text-xs text-neutral-500">
  {draft.outcome === "reject"
    ? "Explain what needs to change before this unit can be accepted."
    : "Add approval rationale or follow-up comments if useful."}
</p>
```

- [ ] **Step 4: Update `UnitReview` default draft and loading**

In `review-ui/src/components/unit-review.tsx`, update `DEFAULT_RUBRIC`:

```ts
const DEFAULT_RUBRIC: RubricDraft = {
  outcome: "approve",
  representation: 7,
  engagement: 7,
  actionExpression: 7,
  notes: "",
};
```

After `setUnit(mapUnitDetail(detail));`, derive saved review for reviewer users:

```ts
const mappedDetail = mapUnitDetail(detail);
setUnit(mappedDetail);
if (user.role !== "admin" && mappedDetail.myReview.state !== "not_reviewed") {
  const scoresRaw = await fetchReviewerScores(unitId);
  const mine = scoresRaw.map(mapReviewerScore).find((score) => score.reviewer === user.email);
  if (mine) {
    setRubricDraft({
      outcome: mine.outcome,
      representation: mine.representation,
      engagement: mine.engagement,
      actionExpression: mine.actionExpression,
      notes: mine.notes,
    });
  }
}
```

Remove `fetchNotes`, `postNote`, `rejectUnit`, `MessageSquarePlus`, `XCircle`, `noteOpen`, `noteText`, `rejectOpen`, `rejectNoteText`, `handleReject`, and `handleSaveNote` from the reviewer action path.

In `handleReviewerApprove`, validate rejection note and submit outcome:

```ts
if (rubricDraft.outcome === "reject" && !rubricDraft.notes.trim()) {
  toast.error("A reviewer note is required when rejecting a unit");
  return;
}
await postReviewerRubric(unit.id, {
  outcome: rubricDraft.outcome,
  representation: rubricDraft.representation,
  engagement: rubricDraft.engagement,
  action_expression: rubricDraft.actionExpression,
  notes: rubricDraft.notes,
  checked_by: user.email,
  mark_verified: true,
});
```

Change toast copy:

```ts
description:
  rubricDraft.outcome === "approve"
    ? "Your approval, rubric scores, and note were saved"
    : "Your rejection, rubric scores, and required note were saved",
```

Pass read-only mode to panel:

```tsx
<ReviewerRubricPanel
  draft={rubricDraft}
  onChange={setRubricDraft}
  readOnly={unit.myReview.readOnly}
/>
```

Disable submit for read-only:

```tsx
<Button size="sm" onClick={() => setApproveOpen(true)} disabled={acting || unit.myReview.readOnly}>
  Submit review
</Button>
```

Update dialog description:

```tsx
description="Your outcome, UDL rubric scores, and reviewer note will be saved for admins."
```

- [ ] **Step 5: Run frontend build**

Run: `cd review-ui && npm run build`

Expected: pass after resolving import errors and removed state references.

- [ ] **Step 6: Checkpoint commit**

Only commit if the user has requested commits for this implementation session.

```bash
git add review-ui/src/components/review-queue.tsx review-ui/src/components/reviewer-rubric-panel.tsx review-ui/src/components/unit-review.tsx review-ui/src/components/ui/tooltip.tsx
git commit -m "Use reviewer-specific review state in UI"
```

---

### Task 8: Admin Review Sidebar and Admin Notes UI

**Files:**
- Modify: `review-ui/src/components/admin-judge-sidebar.tsx`
- Modify: `review-ui/src/components/unit-review.tsx`

- [ ] **Step 1: Add admin note state and API calls**

In `review-ui/src/components/unit-review.tsx`, import:

```ts
  fetchAdminNotes,
  postAdminNote,
```

Import mapper and type:

```ts
  mapAdminNote,
```

```ts
  AdminNote,
```

Add state:

```ts
const [adminNotes, setAdminNotes] = useState<AdminNote[]>([]);
const [adminNoteText, setAdminNoteText] = useState("");
```

In admin load `Promise.all`, include admin notes:

```ts
const [judgeRaw, notesRaw, scoresRaw, adminNotesRaw] = await Promise.all([
  fetchJudge(unitId),
  fetchNotes(unitId),
  fetchReviewerScores(unitId),
  fetchAdminNotes(unitId),
]);
setAdminNotes(adminNotesRaw.map(mapAdminNote));
```

Add handler:

```ts
const handleSaveAdminNote = async () => {
  if (!adminNoteText.trim() || !unit) return;
  setActing(true);
  try {
    await postAdminNote(unit.id, adminNoteText.trim());
    setAdminNoteText("");
    toast.success("Admin note saved");
    const adminNotesRaw = await fetchAdminNotes(unit.id);
    setAdminNotes(adminNotesRaw.map(mapAdminNote));
  } catch (e) {
    toast.error(e instanceof Error ? e.message : "Could not save admin note");
  } finally {
    setActing(false);
  }
};
```

Pass to admin sidebar:

```tsx
<AdminJudgeSidebar
  judge={judge}
  unit={unit}
  reviewerScores={reviewerScores}
  notes={notes}
  adminNotes={adminNotes}
  adminNoteText={adminNoteText}
  onAdminNoteTextChange={setAdminNoteText}
  onSaveAdminNote={handleSaveAdminNote}
  savingAdminNote={acting}
/>
```

- [ ] **Step 2: Update admin sidebar props**

In `review-ui/src/components/admin-judge-sidebar.tsx`, update imports:

```ts
  AdminNote,
  UnitDetail,
```

Import `Textarea`:

```ts
import { Textarea } from "./ui/textarea";
```

Update function props:

```ts
export function AdminJudgeSidebar({
  judge,
  unit,
  reviewerScores,
  notes,
  adminNotes,
  adminNoteText,
  onAdminNoteTextChange,
  onSaveAdminNote,
  savingAdminNote,
}: {
  judge: JudgeReportUi;
  unit: UnitDetail;
  reviewerScores: ReviewerScoreUi[];
  notes: ReviewerNote[];
  adminNotes: AdminNote[];
  adminNoteText: string;
  onAdminNoteTextChange: (value: string) => void;
  onSaveAdminNote: () => void;
  savingAdminNote: boolean;
}) {
```

Add a review summary card before reviewer list:

```tsx
<div className="rounded-lg border bg-white p-6">
  <h3 className="mb-4 text-sm font-medium">Review summary</h3>
  <div className="grid grid-cols-3 gap-3 text-center">
    <div>
      <div className="text-2xl font-semibold">{unit.reviewSummary.total}</div>
      <div className="text-xs text-neutral-500">Total</div>
    </div>
    <div>
      <div className="text-2xl font-semibold text-green-700">{unit.reviewSummary.approved}</div>
      <div className="text-xs text-neutral-500">Approved</div>
    </div>
    <div>
      <div className="text-2xl font-semibold text-red-700">{unit.reviewSummary.rejected}</div>
      <div className="text-xs text-neutral-500">Rejected</div>
    </div>
  </div>
</div>
```

Update `ReviewerScoreCard` to show outcome:

```tsx
<Badge className={score.outcome === "approve" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}>
  {score.outcome === "approve" ? "Approved" : "Rejected"}
</Badge>
```

Add admin notes section after reviewer reviews:

```tsx
<div className="rounded-lg border bg-white p-6">
  <h3 className="mb-4 text-sm font-medium">Admin notes</h3>
  {adminNotes.length === 0 ? (
    <p className="mb-4 text-sm text-neutral-500">No admin notes yet</p>
  ) : (
    <div className="mb-4 space-y-4">
      {adminNotes.map((note, i) => (
        <div key={i} className="border-l-2 pl-3">
          <div className="mb-1 flex items-center gap-2">
            <span className="text-xs font-medium">{note.author}</span>
            <span className="text-xs text-neutral-500">{note.date}</span>
          </div>
          <p className="text-sm text-neutral-700">{note.text}</p>
        </div>
      ))}
    </div>
  )}
  <Textarea
    placeholder="Write an admin note..."
    value={adminNoteText}
    onChange={(e) => onAdminNoteTextChange(e.target.value)}
    rows={4}
  />
  <Button
    className="mt-3"
    size="sm"
    onClick={onSaveAdminNote}
    disabled={savingAdminNote || !adminNoteText.trim()}
  >
    Add admin note
  </Button>
</div>
```

- [ ] **Step 3: Run frontend build**

Run: `cd review-ui && npm run build`

Expected: pass.

- [ ] **Step 4: Checkpoint commit**

Only commit if the user has requested commits for this implementation session.

```bash
git add review-ui/src/components/admin-judge-sidebar.tsx review-ui/src/components/unit-review.tsx
git commit -m "Show admin review summaries and notes"
```

---

### Task 9: Role-Aware How-to Page

**Files:**
- Create: `review-ui/src/components/how-to.tsx`
- Modify: `review-ui/src/routes.tsx`
- Modify: `review-ui/src/components/review-queue.tsx`
- Modify: `review-ui/src/components/unit-review.tsx`

- [ ] **Step 1: Create How-to component**

Create `review-ui/src/components/how-to.tsx`:

```tsx
import { useNavigate } from "react-router";
import { useAuth } from "@/contexts/AuthContext";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";

export function HowTo() {
  const navigate = useNavigate();
  const { user } = useAuth();

  if (!user) {
    navigate("/");
    return null;
  }

  return (
    <div className="min-h-screen bg-neutral-50">
      <header className="border-b bg-white px-6 py-4">
        <div className="mx-auto flex max-w-4xl items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold">How to use the review portal</h1>
            <p className="text-sm text-neutral-600">{user.email}</p>
          </div>
          <Button variant="outline" onClick={() => navigate("/queue")}>
            Back to queue
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-4xl space-y-6 px-6 py-8">
        {user.role === "admin" ? <AdminHowTo /> : <ReviewerHowTo />}
      </main>
    </div>
  );
}

function ReviewerHowTo() {
  return (
    <>
      <section className="rounded-lg border bg-white p-6">
        <Badge className="mb-3 bg-blue-50 text-blue-700">Reviewer</Badge>
        <h2 className="mb-3 text-xl font-semibold">Reviewing a unit</h2>
        <p className="text-sm text-neutral-700">
          Use Available to review for units you have not reviewed. Use My reviews for units
          where you already submitted an approval or rejection.
        </p>
      </section>
      <section className="rounded-lg border bg-white p-6">
        <h3 className="mb-2 font-medium">Approve or reject</h3>
        <p className="text-sm text-neutral-700">
          Choose Approve when the unit is acceptable for admin review. Choose Reject when the
          unit needs changes. Rejections require a reviewer note explaining what should change.
        </p>
      </section>
      <section className="rounded-lg border bg-white p-6">
        <h3 className="mb-2 font-medium">Published units</h3>
        <p className="text-sm text-neutral-700">
          Published units are read-only. If your opinion changes after publication, contact an
          admin outside the portal.
        </p>
      </section>
    </>
  );
}

function AdminHowTo() {
  return (
    <>
      <section className="rounded-lg border bg-white p-6">
        <Badge className="mb-3 bg-purple-50 text-purple-700">Admin</Badge>
        <h2 className="mb-3 text-xl font-semibold">Reading review summaries</h2>
        <p className="text-sm text-neutral-700">
          The Review Summary column counts the latest review from each reviewer and splits the
          outcomes into approved and rejected.
        </p>
      </section>
      <section className="rounded-lg border bg-white p-6">
        <h3 className="mb-2 font-medium">Mixed outcomes</h3>
        <p className="text-sm text-neutral-700">
          Reviewer disagreement does not block publishing. Read the review cards and notes, then
          decide whether to publish or send the unit back to draft.
        </p>
      </section>
      <section className="rounded-lg border bg-white p-6">
        <h3 className="mb-2 font-medium">Admin notes</h3>
        <p className="text-sm text-neutral-700">
          Admin notes are persisted operational comments. They do not count as reviewer reviews
          and do not change review summaries.
        </p>
      </section>
    </>
  );
}
```

- [ ] **Step 2: Add route**

In `review-ui/src/routes.tsx`, import and register:

```ts
import { HowTo } from "./components/how-to";
```

```tsx
{ path: "/how-to", Component: HowTo },
```

- [ ] **Step 3: Link How-to from headers**

In `review-ui/src/components/review-queue.tsx`, add a header button:

```tsx
<Button variant="outline" size="sm" asChild>
  <Link to="/how-to">How to</Link>
</Button>
```

In `review-ui/src/components/unit-review.tsx`, import `Link` from `react-router` and add near the header actions:

```tsx
<Button variant="outline" size="sm" asChild>
  <Link to="/how-to">How to</Link>
</Button>
```

- [ ] **Step 4: Run frontend build**

Run: `cd review-ui && npm run build`

Expected: pass.

- [ ] **Step 5: Checkpoint commit**

Only commit if the user has requested commits for this implementation session.

```bash
git add review-ui/src/components/how-to.tsx review-ui/src/routes.tsx review-ui/src/components/review-queue.tsx review-ui/src/components/unit-review.tsx
git commit -m "Add role-aware review portal guidance"
```

---

### Task 10: Final Verification and Cleanup

**Files:**
- Modify as needed based on test/build failures.

- [ ] **Step 1: Run backend review tests**

Run: `uv run pytest tests/review -v`

Expected: all review tests pass.

- [ ] **Step 2: Run frontend build**

Run: `cd review-ui && npm run build`

Expected: TypeScript build and Vite build pass.

- [ ] **Step 3: Run frontend lint**

Run: `cd review-ui && npm run lint`

Expected: lint passes or reports only pre-existing warnings unrelated to changed files.

- [ ] **Step 4: Manual reviewer verification**

Start the portal in the project’s usual local or deployed environment and verify:

```text
Reviewer A submits approve on a unit.
Reviewer A sees the unit in My reviews.
Reviewer B still sees the same unit in Available to review.
Reviewer A reopens the unit and sees saved scores, outcome, and note.
Reviewer A cannot edit a published unit.
```

- [ ] **Step 5: Manual admin verification**

Verify:

```text
Admin queue shows Review Summary with approved/rejected split.
Admin opens a unit and sees all latest reviewer review cards.
Admin adds an admin note and sees it persist after refresh.
Admin can publish a unit with mixed approve/reject outcomes.
```

- [ ] **Step 6: Check changed-file lints**

Use Cursor diagnostics or `ReadLints` on changed files. Fix diagnostics introduced by this work.

- [ ] **Step 7: Final checkpoint commit**

Only commit if the user has requested commits for this implementation session.

```bash
git add src/ibrary/review review-ui/src tests/review
git commit -m "Fix user-specific reviewer workflow"
```
