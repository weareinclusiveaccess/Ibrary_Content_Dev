# IBrary Biology Content Creation System — Implementation Plan

**Goal:** Design and build a system that creates UDL-aligned educational biology content for IBrary, using OpenAI and textbook knowledge. Biology serves as the sample subject for the pipeline.

**References:**
- [RFC](https://docs.google.com/document/d/1x4dJZwBxID5bleYjSN58SKoCEi6C7gX0Pe1mHdpaGPs/edit?tab=t.0)
- [Architecture Diagram](https://yoyo-cafe-29949704.figma.site/)

---

## Executive Summary

The system converts the Nigerian SS1 Biology curriculum + OpenStax textbook content into structured, UDL-aligned learning modules. The pipeline has five main stages: **Extract & Normalize** → **Curriculum–Textbook Alignment** → **UDL Curation (LLM)** → **Review & Publish** → **Serving Store (DynamoDB)**.

---

## Current State (What Exists)

| Asset | Location | Status |
|-------|----------|--------|
| Nigerian curriculum (structured) | `data/docs/extracted_source_content/biology/biology_curriculum_structured.json` | ✅ Done |
| Extraction template | `data/docs/extracted_source_content/extraction_template.json` | ✅ Week/subtopic structure |

**Gaps:** Curriculum–textbook alignment automation, embedding/retrieval index, UDL curation service, review workflow, DynamoDB serving store, read API.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         INPUTS / AUTHORING                                        │
│  Curriculum PDF (NERDC)  │  OpenStax Textbook  │  Lecture Notes (.md/.rtf/.pdf)  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  Component 0: Extract + Normalize                                                 │
│  • Curriculum PDF → curriculum_normalized.json                                    │
│  • Textbook (PDF/web) → openstax_structured.json (chapter→section→chunk)         │
│  • Lecture notes → normalized_source.json (week segmentation)                     │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  Component 1: Schema Validation + ID Generation                                   │
│  • curriculum_validated.json, textbook_validated.json                             │
│  • curriculum_unit_id, textbook_chunk_id                                          │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  Component 2: Curriculum ↔ Textbook Alignment                                     │
│  • Vector index for textbook chunks                                               │
│  • curriculum_textbook_alignment.json (top-k chunks per unit + confidence)        │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  Component 3: UDL Curation (LLM)                                                  │
│  • OpenAI / Amazon Nova                                                           │
│  • Generate UDL-aligned modules from matched textbook chunks                      │
│  • Output: curated_content.json (draft)                                           │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  Component 4: Human Review Workflow                                               │
│  • draft → reviewed → approved → published                                        │
│  • Traceability: curriculum_unit_id, textbook_chunk_ids, model/prompt versions    │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  Component 5: Storage + Serving                                                   │
│  • S3: raw + processed + curated archive (versioned)                              │
│  • DynamoDB: published items only (Week + Subtopic)                               │
│  • API Gateway + Lambda: GetItem / Query                                           │
│  • Optional: OpenSearch / Algolia for search                                      │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase-by-Phase Plan

### Phase 1: Foundation (Weeks 1–2)

**Objective:** Lock inputs and complete curriculum + textbook normalization.

| Task | Deliverable | Notes |
|------|-------------|-------|
| 1.1 | Validate `biology_curriculum_structured.json` against RFC schema | `curriculum_validated.json` | Add `curriculum_unit_id` per topic |
| 1.2 | Normalize curriculum structure (theme → topic → subtopic) | Canonical IDs, extraction report | Handle unmapped/ambiguous rows |
| 1.3 | Convert existing OpenStax extracted JSON to chunked format | `openstax_structured.json` | Chapter → section → subsection chunks |
| 1.4 | Define `textbook_chunk_id` schema and manifest | `book_structure_manifest.json` | Chunk IDs + hierarchy |

**Acceptance:** 100% curriculum units have stable IDs; textbook chunks are retrievable by ID.

---

### Phase 2: Curriculum–Textbook Alignment (Weeks 3–4)

**Objective:** Map each curriculum unit to relevant textbook chunks.

| Task | Deliverable | Notes |
|------|-------------|-------|
| 2.1 | Embed textbook chunks (OpenAI embeddings or similar) | Vector index | Store embeddings + metadata |
| 2.2 | Build retrieval function (top-k by similarity) | Retrieval test script | Manual spot-check on sample units |
| 2.3 | Generate `curriculum_textbook_alignment.json` | Alignment file | curriculum_unit_id → [chunk_ids] + confidence |
| 2.4 | Flag low-confidence matches | `[Needs Review]` markers | ≥80% units with ≥1 usable match |

**Acceptance:** Alignment file exists; retrieval returns relevant chunks for sample curriculum units.

---

### Phase 3: UDL Curation Service (Weeks 5–6)

**Objective:** Generate UDL-aligned modules from curriculum + textbook context.

| Task | Deliverable | Notes |
|------|-------------|-------|
| 3.1 | Define UDL module output schema | `module_schema.json` | title, objectives, sections, glossary, takeaways, images |
| 3.2 | Implement curation prompt (rewrite-only, grounded in chunks) | Prompt template | Include curriculum objectives, textbook chunks, UDL rubric |
| 3.3 | Build curation service (subtopic-level batching) | `curation_service.py` | One LLM call per subtopic; optional two-pass for coherence |
| 3.4 | Add traceability fields | `curriculum_unit_id`, `textbook_chunk_refs[]`, `model_version`, `prompt_version` | |
| 3.5 | Pilot: generate drafts for 3–5 weeks | `curated_content.json` (draft) | Biology SS1, Term 1 |

**Acceptance:** Draft modules produced; grounded in OpenStax; UDL structure present.

---

### Phase 4: Review Workflow + Image Attachment (Weeks 7–8)

**Objective:** Human-in-the-loop review and image enrichment.

| Task | Deliverable | Notes |
|------|-------------|-------|
| 4.1 | Define status transitions | draft → reviewed → approved → published | Enforce in code |
| 4.2 | Build reviewer checklist (UDL rubric) | Checklist doc + validation | Clarity, structure, key terms, accessibility |
| 4.3 | Image attachment (caption + alt text) | `images_manifest.json` | Prefer textbook figures; flag for review if generated |
| 4.4 | Store curated outputs in S3 (versioned) | `curated_content_{version}.json` | Audit trail, rollback |

**Acceptance:** Status transitions enforced; reviewer checklist in place; images with captions/alt text.

---

### Phase 5: Serving Store + API (Weeks 9–10)

**Objective:** DynamoDB + read API for published content.

| Task | Deliverable | Notes |
|------|-------------|-------|
| 5.1 | Design DynamoDB table `CuratedContent` | PK/SK schema | PK: SUBJECT#Biology#CLASS#SSS1#TERM#1, SK: WEEK#01, WEEK#01#SUBTOPIC#slug |
| 5.2 | Implement write path (published only) | Lambda or script | Only `status=published` → DynamoDB |
| 5.3 | Implement read API | API Gateway + Lambda | GET /weeks, GET /weeks/{id}, GET /weeks/{id}/subtopics, GET /weeks/{id}/subtopics/{slug} |
| 5.4 | Optional: Search index | OpenSearch/Algolia | index_records.jsonl → search index |

**Acceptance:** DynamoDB populated; API returns published content; Query/GetItem patterns verified.

---

### Phase 6: QA + Rollout (Week 11)

**Objective:** End-to-end validation and production enablement.

| Task | Deliverable | Notes |
|------|-------------|-------|
| 6.1 | UDL rubric pass for pilot content | QA report | Spot-check clarity, structure, definitions |
| 6.2 | Factual spot-check for flagged items | Review log | Equations, tables, [Needs Review] |
| 6.3 | Staging validation | Staging env | Full flow: curriculum → DynamoDB → API |
| 6.4 | Production publishing enabled | Runbook | How to publish new content |

**Acceptance:** Pilot content passes QA; staging validated; runbook documented.

---

## DynamoDB Data Model (Summary)

| Item Type | PK | SK | Key Fields |
|-----------|----|----|------------|
| Week | SUBJECT#Biology#CLASS#SSS1#TERM#1 | WEEK#01 | introduction, learning_objectives, topic_glossary, search_title, keywords |
| Subtopic | SUBJECT#Biology#CLASS#SSS1#TERM#1 | WEEK#01#SUBTOPIC#scientific-process | curated_content, key_takeaways, glossary_terms, search_summary, searchable_text |

---

## Key Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| LLM hallucination in science content | Rewrite-only constraint; ground in textbook chunks; [Needs Review] for ambiguous source |
| Inconsistent input structure | Component 0 header normalization; extraction report for unmapped sections |
| DynamoDB item size limits | Store subtopic-level; truncate searchable_text if needed; consider S3 pointer for large bodies |
| Review throughput bottleneck | Prioritize by [Needs Review], equations, extraction conflicts |
| Cost (LLM) | Subtopic-level batching; deterministic retries; cache raw/processed artifacts |

---

## File Structure (Proposed)

```
Ibrary_Content_Dev/
├── src/
│   ├── sourceContentProcessor/     # Existing: extractors
│   ├── curriculum/                 # NEW: curriculum validation, normalization
│   ├── textbook/                   # NEW: chunking, embedding, retrieval
│   ├── alignment/                  # NEW: curriculum ↔ textbook mapping
│   ├── curation/                   # NEW: UDL LLM service
│   ├── review/                     # NEW: status workflow, checklist
│   ├── serving/                    # NEW: DynamoDB write, API
│   └── schemas/
├── data/
│   ├── docs/extracted_source_content/biology/
│   │   ├── biology_curriculum_structured.json
│   │   ├── curriculum_openstax_concepts_mapping.json
│   │   ├── essential-biology/       # Extracted chapters
│   │   ├── curriculum_validated.json
│   │   ├── openstax_structured.json
│   │   ├── curriculum_textbook_alignment.json
│   │   └── curated_content.json
│   └── ...
├── docs/
│   └── PLAN_BIOLOGY_CONTENT_SYSTEM.md  # This file
└── ...
```

---

## Milestone Checklist (RFC-Aligned)

| Milestone | Target | Status |
|-----------|--------|--------|
| M1: Inputs locked + mapping plan | Wk 1 | ✅ Done |
| M2: Curriculum extraction + normalization | Wk 2 | 🏋️ In Progress |
| M3: Curriculum JSON complete (all 3 subjects) | Wk 3 | 🧑‍🦽 In Progress |
| M4: OpenStax ingestion + structuring | Wk 4 | ⭕ Not Started |
| M5: Textbook embedding + retrieval index | Wk 5 | ⭕ Not Started |
| M6: Curriculum ↔ textbook alignment | Wk 6 | ⭕ Not Started |
| M7: UDL module generation (drafts) | Wk 7 | ⭕ Not Started |
| M8: Review + publish workflow | Wk 8 | ⭕ Not Started |
| M9: Serving store + API (MVP) | Wk 9 | ⭕ Not Started |
| M10: End-to-end QA + rollout | Wk 10 | ⭕ Not Started |

---

## Next Steps

1. **Immediate:** Complete M2–M3 (curriculum normalization, validation, stable IDs).
2. **Short-term:** Convert existing OpenStax extracted JSON to chunked `openstax_structured.json` (M4).
3. **Medium-term:** Implement embedding + retrieval (M5) and alignment generation (M6).
4. **Parallel:** Define UDL module schema and curation prompt; build curation service (M7).

---

*Last updated: March 2026*
