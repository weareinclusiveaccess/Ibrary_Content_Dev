# Content read API — setup and backend integration

Standalone branch: serves published biology lessons from DynamoDB (`CuratedContent` in AWS account `681986854278`, region `eu-west-1`). No dependency on the reviewer portal or pipeline UI.

## Quick start (local)

```bash
cp .env.content-api.example .env
# Edit .env — set CONTENT_API_KEYS and AWS credentials (see below)

uv sync --extra content-api --extra dev
uv pip install -e .

make content-api
# or: uv run --extra content-api python scripts/run_content_api.py
```

Health check (no API key):

```bash
curl http://127.0.0.1:8080/health
```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `CONTENT_API_KEYS` | yes | Comma-separated keys for `X-API-Key` header |
| `AWS_DEFAULT_REGION` | yes | `eu-west-1` |
| `AWS_ACCESS_KEY_ID` | Render/prod | IAM user `ibrary-content-api` access key |
| `AWS_SECRET_ACCESS_KEY` | Render/prod | IAM user secret |
| `AWS_PROFILE` | local dev | e.g. `ibrary-dev` (omit access keys when using profile) |
| `AWS_SDK_LOAD_CONFIG` | local dev | `1` when using named profile |
| `DYNAMODB_ENDPOINT_URL` | optional | Set only for DynamoDB Local; **unset for prod AWS** |
| `PIPELINE_SUBJECT` | optional | Default query subject (`Biology`) |
| `CONTENT_API_HOST` | optional | Bind host (default `127.0.0.1`; use `0.0.0.0` in containers) |
| `CONTENT_API_PORT` | optional | Default `8080` |
| `CONTENT_API_CORS_ORIGINS` | optional | Default `*` |

Copy template: [`.env.content-api.example`](../.env.content-api.example)

## AWS IAM (hosted deploy)

Create a dedicated read-only IAM user — do **not** use your MFA developer role on Render.

1. IAM → Users → `ibrary-content-api`
2. Attach inline policy: [`infra/terraform/iam/content-api-readonly-policy.json`](../infra/terraform/iam/content-api-readonly-policy.json)
3. Create access key → set in Render secrets

See also [`infra/terraform/iam/README.md`](../infra/terraform/iam/README.md).

## Deploy free public HTTPS (Render)

1. Push this branch to GitHub
2. [Render](https://render.com) → **New** → **Blueprint** → connect repo (`render.yaml`)
3. Set secrets in Render dashboard:
   - `CONTENT_API_KEYS`
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
4. Deploy → use URL like `https://ibrary-content-api.onrender.com`

Free tier sleeps after ~15 min idle; first request after sleep may take ~30s.

```bash
docker build -f Dockerfile.content-api -t ibrary-content-api:dev .
```

## Backend integration

**Auth:** every content request requires header `X-API-Key: <key>`.

**Base URL:** your Render URL or `http://localhost:8080` locally.

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness (no auth) |
| `GET` | `/topics?class_name=SSS%201&theme_number=1&subject=Biology` | List topics in a theme |
| `GET` | `/topics/{n}?class_name=...&theme_number=...` | Topic metadata |
| `GET` | `/topics/{n}/subtopics?...` | All lessons under a topic |
| `GET` | `/topics/{n}/subtopics/{i}?...` | Full lesson (typical app path) |

### Example

```bash
curl -H "X-API-Key: YOUR_KEY" \
  "https://ibrary-content-api.onrender.com/topics/1/subtopics/0?class_name=SSS%201&theme_number=1&subject=Biology"
```

### DynamoDB key layout

```
PK = SUBJECT#Biology#CLASS#SSS 1#THEME#1
SK (topic)    = TOPIC#01
SK (subtopic) = TOPIC#01#CONTENT#0
```

Unit ID `bio_sss1_theme1_topic1_content0` maps to `theme_number=1`, `topic_number=1`, `content_index=0`.

### Response fields (subtopic)

| Field | Notes |
|-------|-------|
| `curated_content_md` | Main lesson body (Markdown) |
| `key_takeaways`, `glossary_terms`, `student_activities`, etc. | JSON **strings** — parse with `JSON.parse` |
| `curriculum_unit_id` | e.g. `bio_sss1_theme1_topic1_content0` |

### Typical BE flow

1. User selects class / theme / topic
2. `GET /topics/{topic}/subtopics` → list content items
3. `GET /topics/{topic}/subtopics/{index}` → render `curated_content_md`

Always **query by PK** — never scan the table.
