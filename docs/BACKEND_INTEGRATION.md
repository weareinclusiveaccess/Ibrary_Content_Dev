# Backend integration guide — IBrary Content API

Share this document with your backend team.

## Live URLs

| Resource | URL |
|----------|-----|
| **Base URL** | `https://ibrary-content-api-latest.onrender.com` |
| **Swagger UI** | [https://ibrary-content-api-latest.onrender.com/docs](https://ibrary-content-api-latest.onrender.com/docs) |
| **ReDoc** | [https://ibrary-content-api-latest.onrender.com/redoc](https://ibrary-content-api-latest.onrender.com/redoc) |
| **OpenAPI JSON** | [https://ibrary-content-api-latest.onrender.com/openapi.json](https://ibrary-content-api-latest.onrender.com/openapi.json) |
| **Health** | [https://ibrary-content-api-latest.onrender.com/health](https://ibrary-content-api-latest.onrender.com/health) |

Open **Swagger UI**, click **Authorize**, enter your `X-API-Key`, then try endpoints interactively.

---

## Authentication

Every `/topics*` request must include:

```http
X-API-Key: <key-from-ibrary-team>
```

`/health` does not require a key.

---

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | No | Liveness check |
| `GET` | `/topics` | Yes | List topics in a theme |
| `GET` | `/topics/{topic_number}` | Yes | Single topic metadata |
| `GET` | `/topics/{topic_number}/subtopics` | Yes | All lessons in a topic (full DynamoDB items) |
| `GET` | `/topics/{topic_number}/subtopics/summary` | Yes | **Catalog only:** `subtopic`, `PK`, `SK` |
| `GET` | `/topics/{topic_number}/subtopics/{content_index}` | Yes | **Full lesson** (main app endpoint) |

### Query parameters (all content routes)

| Parameter | Default | Example | Description |
|-----------|---------|---------|-------------|
| `class_name` | `SSS 1` | `SSS 1` | Nigerian curriculum class |
| `theme_number` | `1` | `1` | Theme 1–4 |
| `subject` | `Biology` | `Biology` | Subject name |

---

## Curriculum unit ID mapping

Postgres / review portal unit IDs map to API params:

```
bio_sss1_theme1_topic1_content0
         │      │      │        └── content_index = 0
         │      │      └── topic_number = 1
         │      └── theme_number = 1
         └── class SSS 1, subject Biology
```

API call:

```http
GET /topics/1/subtopics/0?class_name=SSS%201&theme_number=1&subject=Biology
X-API-Key: YOUR_KEY
```

---

## Response shape (lesson / subtopic)

```json
{
  "entity_type": "SUBTOPIC",
  "curriculum_unit_id": "bio_sss1_theme1_topic1_content0",
  "subtopic": "Recognizing Living Things",
  "curated_content_md": "# Recognizing Living Things\n\n...",
  "key_takeaways": "[\"Living things grow\", \"Living things reproduce\"]",
  "glossary_terms": "[{\"term\":\"Cell\",\"definition\":\"...\"}]",
  "student_activities": "[\"Observe specimens...\"]",
  "teacher_activities": "[\"Prepare microscope slides...\"]",
  "accessibility_checklist": "{...}",
  "textbook_chunk_refs": "[...]",
  "model_version": "gpt-5.1",
  "prompt_version": "..."
}
```

### Fields to parse as JSON

These are stored as **strings** in DynamoDB:

- `learning_objectives` (topic only)
- `key_takeaways`
- `glossary_terms`
- `student_activities`
- `teacher_activities`
- `accessibility_checklist`
- `textbook_chunk_refs`

### Main content field

- **`curated_content_md`** — Markdown; render to HTML in your frontend or via a Markdown library on the server.

---

## Code examples

### JavaScript (fetch)

```javascript
const BASE = "https://ibrary-content-api-latest.onrender.com";
const API_KEY = process.env.IBRARY_CONTENT_API_KEY;

async function getLesson(themeNumber, topicNumber, contentIndex) {
  const params = new URLSearchParams({
    class_name: "SSS 1",
    theme_number: String(themeNumber),
    subject: "Biology",
  });
  const url = `${BASE}/topics/${topicNumber}/subtopics/${contentIndex}?${params}`;
  const res = await fetch(url, {
    headers: { "X-API-Key": API_KEY },
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  const lesson = await res.json();
  lesson.key_takeaways = JSON.parse(lesson.key_takeaways);
  lesson.glossary_terms = JSON.parse(lesson.glossary_terms);
  return lesson;
}
```

### Python (httpx)

```python
import httpx
import json

BASE = "https://ibrary-content-api-latest.onrender.com"
API_KEY = "your-key"

def get_lesson(theme_number: int, topic_number: int, content_index: int) -> dict:
    r = httpx.get(
        f"{BASE}/topics/{topic_number}/subtopics/{content_index}",
        params={"class_name": "SSS 1", "theme_number": theme_number, "subject": "Biology"},
        headers={"X-API-Key": API_KEY},
        timeout=60.0,
    )
    r.raise_for_status()
    lesson = r.json()
    lesson["key_takeaways"] = json.loads(lesson["key_takeaways"])
    return lesson
```

### cURL

```bash
curl -H "X-API-Key: YOUR_KEY" \
  "https://ibrary-content-api-latest.onrender.com/topics/1/subtopics/0?class_name=SSS%201&theme_number=1&subject=Biology"
```

---

## Recommended app flow

```mermaid
flowchart LR
  A[User picks Theme + Topic] --> B[GET /topics/{n}/subtopics/summary]
  B --> C[Show lesson titles]
  C --> D[User picks lesson]
  D --> E[GET /topics/{n}/subtopics/{index}]
  E --> F[Parse JSON string fields]
  F --> G[Render curated_content_md]
```

1. Browse themes/topics via `GET /topics?theme_number=N`
2. Load lesson catalog via `GET /topics/{topic}/subtopics/summary` (title + PK/SK only)
3. Fetch one lesson via `GET /topics/{topic}/subtopics/{index}` (from `SK`: `TOPIC#01#CONTENT#0` → index `0`)
4. Parse JSON string fields; render Markdown

---

## HTTP status codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `403` | Missing or invalid `X-API-Key` |
| `404` | Topic or subtopic not found in DynamoDB |
| `503` | DynamoDB / AWS error (retry or contact IBrary) |

---

## Operational notes

- **Cold start:** Free Render tier sleeps after ~15 min idle; first request may take ~30s.
- **Caching:** Safe to cache lesson responses by `curriculum_unit_id` (content is published, rarely changes).
- **Rate limits:** No hard limit today; use reasonable caching on your side.

---

## OpenAPI / client generation

Download the spec:

```bash
curl -o ibrary-content-openapi.json \
  https://ibrary-content-api-latest.onrender.com/openapi.json
```

Generate a typed client (example):

```bash
npx openapi-typescript ibrary-content-openapi.json -o src/ibrary-content-api.ts
```
