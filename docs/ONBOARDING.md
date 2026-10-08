# Onboarding

This repository builds accessible biology lessons for Nigerian Senior Secondary School (SSS 1). It extracts an OpenStax textbook, aligns the text with a structured curriculum, drafts lessons with a language model, and keeps a human review step before anything is served to the product.

You do not need to run the whole pipeline on day one. Pick the path that matches your job, read the short list for that path, then set up only the tools that path needs.

## What you are looking at

Three programs share this repo. They are not one server.

| Program | What it does | Default URL | When you touch it |
|---|---|---|---|
| Content pipeline | Turns the textbook and curriculum into lesson JSON | No server. It is a script. | You are changing extraction, alignment, prompts, or judging. |
| Reviewer portal | Lets a person read a lesson, score it, and approve it | http://127.0.0.1:8090 | You are changing review, login, or publish. |
| Content read API | Serves lessons that are already in DynamoDB | http://127.0.0.1:8080 | You are changing what the product backend can fetch. |

The content API only reads. It does not create lessons. The portal and the pipeline are what create and approve them.

Open [content-creation-flow.html](content-creation-flow.html) in a browser and click each stage. That map is the picture version of this page. The work itself is the checklist in [tasks.html](tasks.html): set up locally, learn the flow, extract the reviews already stored in Neon, understand the current judge against those reviews, then propose how to calibrate the judge to the human scores. The proposal comes before any judge code change.

## Read this first, in this order

Everyone:

1. This page.
2. [content-creation-flow.html](content-creation-flow.html) — click **Extract** through **Serve**.
3. [README.md](../README.md) — what is implemented, and the commands that match it.
4. [SETUP.md](../SETUP.md) — install, Docker, environment variables, and the textbook download. Use the checklist at the top. Skip the Windows notes if you are on macOS or Linux.

Then stop, and read only the track for your work.

### Pipeline and lesson quality

5. [REVIEW_PIPELINE_V2.md](REVIEW_PIPELINE_V2.md) — how version 2 adds a relevance filter before curation. New work should use pipeline version 2.
6. [PIPELINE_ORCHESTRATOR.md](PIPELINE_ORCHESTRATOR.md) — what happens inside the **curate** step.
7. [SUBJECT_CONFIGURATION.md](SUBJECT_CONFIGURATION.md) — subject name, slug, and unit-id prefix. Biology is the only subject wired up today.
8. [LLM_TRACING.md](LLM_TRACING.md) — where prompt traces go when a model call looks wrong.

Read the design specs only when you are changing that part of the system:

- [superpowers/specs/2026-05-16-biology-pipeline-v2-design.md](superpowers/specs/2026-05-16-biology-pipeline-v2-design.md)
- [superpowers/specs/2026-05-16-student-self-study-curation-design.md](superpowers/specs/2026-05-16-student-self-study-curation-design.md)
- [superpowers/specs/2026-07-13-review-weakness-summarization-design.md](superpowers/specs/2026-07-13-review-weakness-summarization-design.md)

### Reviewer portal

5. [plans/2026-05-16-reviewer-portal.md](plans/2026-05-16-reviewer-portal.md)
6. [REVIEW_PORTAL_CLOUDFRONT_USER_GUIDE.md](REVIEW_PORTAL_CLOUDFRONT_USER_GUIDE.md) — what a reviewer sees in production.
7. [infra/README.md](../infra/README.md) and [infra/HOSTING.md](../infra/HOSTING.md) — AWS layout. Read these before you run Terraform.

### Content API (product backend)

5. [CONTENT_API.md](CONTENT_API.md)
6. [BACKEND_INTEGRATION.md](BACKEND_INTEGRATION.md)
7. [infra/terraform/iam/README.md](../infra/terraform/iam/README.md) — the read-only DynamoDB user. Do not reuse a personal AWS profile for the public API.

Everyone who will point a laptop at shared data should also read the next section, **Local machine vs Neon, AWS, and DynamoDB**, before copying a connection string.

## Rules that are easy to get wrong

- Curriculum items are topics, not weeks. Use `topic_number`. Do not invent a week or term mapping for the live curriculum.
- A subtopic is one content item: `curriculum[N].content[M]`.
- A unit id looks like `bio_sss1_theme1_topic1_content0`. The pieces are class, theme, topic, and content index.
- The field names are `class`, `theme`, and `theme_number`. The live curriculum model has no term.
- Pipeline steps are safe to run again. They upsert by id and skip work that is already done.
- Before any model call that needs textbook text, the code loads the full chunk from PostgreSQL. Do not send the model a similarity hit that only has an id.
- DynamoDB is for lessons a person has approved. The content API reads that table. Draft lessons stay in PostgreSQL and in JSON under `data/docs/extracted_source_content/biology/`.
- Prompt changes are tracked by file path plus a content hash. See `src/ibrary/curation/prompts.py` and `src/ibrary/prompt_improvement/review_weakness_prompts.py`.
- Do not commit `.env`, `.env.content-api`, AWS keys, or Terraform state. Copy the example files and fill them in locally.

`src/sourceContentProcessor/` is older extraction code. New pipeline work goes under `src/ibrary/`.

## Set up the machine

You need Python 3.10, 3.11, or 3.12 (not 3.13 or newer), [uv](https://docs.astral.sh/uv/), Git, and Docker. An OpenAI API key is required for embeddings and for every later model step.

```bash
git clone https://github.com/weareinclusiveaccess/Ibrary_Content_Dev.git
cd Ibrary_Content_Dev
git checkout main
git pull

# Your own branch. Do not commit on main.
git checkout -b yourname/short-description

uv sync --extra dev --extra pipeline
uv pip install -e .
cp .env.example .env
```

Work only on that branch. Do not commit on `main`. When a task is ready, open a pull request into `main` and ask someone in the group to approve it. Do not merge your own pull request. Merging to `main` is supposed to wait for that approval.

Copy `.env.example` only. Do not copy a teammate’s `.env`. That file holds their OpenAI key, and sometimes a LangSmith key. Those are personal credentials. Create your own inside the shared group, as below.

## What to put in `.env`

Most lines in the example can stay as they are. For the onboarding tasks you only fill or confirm the rows in this table.

| Variable | What you do |
|---|---|
| `OPENAI_API_KEY` | Create your own key in the group’s OpenAI organization. Required before any model or embedding step. |
| `OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL`, `OPENAI_CURATION_MODEL`, `OPENAI_RELEVANCE_MODEL` | Leave the example values. |
| `LANGSMITH_TRACING` | Leave `false` until you have your own LangSmith key. |
| `LANGSMITH_API_KEY` | Leave empty. Create your own later, in the group workspace. Do not paste someone else’s. |
| `LANGSMITH_PROJECT` | Leave `ibrary-pipeline` so traces land in the same project once you turn tracing on. |
| `DATABASE_URL` and the `POSTGRES_*` lines | Leave the Docker values. This is local Postgres, not Neon. |
| `DATABASE_URL_REVIEW` | Leave unset until the review phase. Then ask the group for the **development** direct URL. |
| `DYNAMODB_ENDPOINT_URL` | Leave `http://localhost:8000` for the whole assignment. |
| `PORTAL_PUBLISH_ENABLED` | Leave `false`. |
| `PIPELINE_VERSION` | Leave `2`. |
| `JUDGE_PASS_THRESHOLD` | Leave `7.0`. The judge task uses this. |
| `AWS_PROFILE`, `AWS_SDK_LOAD_CONFIG`, `AWS_DEFAULT_REGION` | Leave the example (`ibrary-dev`, `1`, `eu-west-1`). Do not set `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY`. |
| `COGNITO_USER_POOL_ID`, `COGNITO_APP_CLIENT_ID`, `COGNITO_REGION` | Leave blank until the review phase. The pool id and client id come from the group. Region stays `eu-west-1`. |
| `S3_BUCKET` | Not needed to finish setup or `validate`. When you run `extract`, ask the group for the bucket name and keep using the AWS profile. |

You do not need `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, Redis, `CONTENT_API_KEYS`, or a production review URL for these tasks.

### Create your own OpenAI key

Ask to be invited to the group’s OpenAI organization. Create the key on a project inside that organization, not on a separate personal org, and not by reusing a key from chat or from another `.env`.

1. Sign in at [platform.openai.com](https://platform.openai.com).
2. Switch to the organization the group names. If you do not see it, stop and ask for an invite.
3. Open the project the group uses for Ibrary, or ask which project to use.
4. Go to **API keys** and create a key. Copy it once into `OPENAI_API_KEY` in your local `.env`.
5. Billing stays on that organization. You are not opening a second account to pay for pipeline calls.

### Create your own LangSmith key later

Day-one tracing is the local JSONL file (`LLM_TRACE_ENABLED=true`, path `data/logs/llm_traces.jsonl`). That needs no LangSmith account. See [LLM_TRACING.md](LLM_TRACING.md).

When you want traces in the shared LangSmith UI:

1. Ask to be added to the group’s LangSmith workspace.
2. In that workspace, create **your** API key. LangSmith shows it once.
3. Set `LANGSMITH_API_KEY` to that key, set `LANGSMITH_TRACING=true`, and keep `LANGSMITH_PROJECT=ibrary-pipeline`.

### Cognito user, when you reach the review phase

The portal has no local password. An admin creates your user and adds you to the Cognito group `reviewer` (or `admin` if you will manage users). You set your own password from the invite. Do not share or reuse another person’s login.

The pool id and app client id are the same for the whole group. Ask for those two values and put them in `COGNITO_USER_POOL_ID` and `COGNITO_APP_CLIENT_ID`. They are not API secrets, but they are also not something to guess.

Start the local databases, create tables, and download the textbook (about 380 MB, not stored in git):

```bash
make up
uv run alembic upgrade head
uv run python scripts/create_dynamodb_tables.py
make download-textbook
```

`make up` starts only what runs on your laptop: PostgreSQL with pgvector, and DynamoDB Local. It does not start Neon, Cognito, or the production DynamoDB table. The textbook lands at `data/docs/extracted_source_content/biology/Biology2e-WEB.pdf`. The curriculum file next to it, `biology_curriculum_structured.json`, is already in git.

Check that tests pass before you change anything:

```bash
uv run pytest
```

## Local machine vs Neon, AWS, and DynamoDB

Day-one setup uses Docker. Shared reviewer data and the lessons the product serves live in other accounts. A wrong connection string writes drafts into the review database, or publishes into the production table.

| Store | Local (your laptop) | Remote (shared) |
|---|---|---|
| Pipeline Postgres | Docker, `DATABASE_URL=postgresql://ibrary:ibrary_dev@localhost:5432/ibrary` | Do not point this at Neon for normal pipeline work. |
| Review Postgres | Same Docker database, only if `DATABASE_URL_REVIEW` is unset | **Neon.** Set `DATABASE_URL_REVIEW`. |
| DynamoDB | DynamoDB Local, `DYNAMODB_ENDPOINT_URL=http://localhost:8000` | Table `CuratedContent` in AWS account `681986854278`, region `eu-west-1`. Unset `DYNAMODB_ENDPOINT_URL`. |
| Textbook images | No local S3 unless you set `S3_ENDPOINT_URL` | Bucket `ibrary-content` in `eu-west-1`. This is the normal target for `extract`. |
| Reviewer login | Portal still runs on port 8090 | **Cognito** user pool in `eu-west-1`. |

### Local Docker

```bash
make up
uv run alembic upgrade head
uv run python scripts/create_dynamodb_tables.py
```

- Postgres listens on `127.0.0.1:5432`, database `ibrary`, user `ibrary`, password `ibrary_dev`. Schema `ibrary`. This holds chunks, embeddings, alignment, and curated drafts.
- DynamoDB Local listens on port `8000`. The container is in-memory (`-inMemory` in `docker-compose.yml`). Stopping it drops every item. Create the table again after `make up`.
- Alembic uses `DATABASE_URL`. With the example file, that is the Docker database, not Neon.

### Neon (review database)

Neon is hosted Postgres for the reviewer portal. The project id in `.env.example` is the shared IbraryContentReview project. Ask a teammate for the development-branch URL. Do not invent one, and do not commit it.

```bash
# Direct host. The hostname must not contain -pooler.
# Pooler hosts reject the search_path option the app sets on connect.
DATABASE_URL_REVIEW=postgresql://USER:PASS@ep-....aws.neon.tech/neondb?sslmode=require
```

If `DATABASE_URL_REVIEW` is missing, the portal uses `DATABASE_URL`. That is the local Docker database. An empty review URL does not mean you are on Neon.

Use the **development** branch for portal work. Production is a different URL. Operators keep that production URL in `DATABASE_URL_REVIEW_PROD` on their machine. The EC2 portal does not read that name. It reads SSM parameter `/ibrary/review/DATABASE_URL_REVIEW` in `eu-west-1`. Those two values should be the same production Neon URL. Do not put the production URL in `.env` while you are experimenting.

Migrations and loaders that must change Neon need the direct host, not the pooled host. Run them only after you have read the host name and confirmed it is the development branch.

The portal database is Neon, not Amazon RDS. Terraform can create RDS (`enable_rds`), and [infra/README.md](../infra/README.md) still describes that module. Leave `enable_rds` false unless someone explicitly asks for RDS. See [infra/HOSTING.md](../infra/HOSTING.md).

### AWS account

Shared cloud resources are in account `681986854278`, region `eu-west-1`.

Local AWS access uses a named profile, not keys pasted into `.env`:

```bash
AWS_PROFILE=ibrary-dev
AWS_SDK_LOAD_CONFIG=1
AWS_DEFAULT_REGION=eu-west-1
```

The `ibrary-dev` profile assumes role `content-dev` and expects MFA. Setup is in [infra/terraform/iam/README.md](../infra/terraform/iam/README.md). `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `.env` override that profile. `.env.example` may show local dummy keys for DynamoDB Local. If those are set, real S3 uploads and real DynamoDB calls use the dummy keys and fail or hit the wrong place. For real S3, comment the keys out and keep the profile.

What that profile is for:

- Uploading textbook figures to `s3://ibrary-content/biology/textbook-images/`
- Reading those figures back for the portal (presigned URLs)
- Talking to production DynamoDB when the local endpoint is unset
- Running Terraform in `infra/terraform/environments/dev`

Copy `terraform.tfvars.example` to `terraform.tfvars` and fill it locally. Do not commit `terraform.tfvars`. Cognito (the reviewer login pool) is created there. After apply, copy `cognito_user_pool_id` and `cognito_app_client_id` into `.env`. Region `COGNITO_REGION=eu-west-1`.

The public content API in production uses a separate read-only IAM user, `ibrary-content-api`, not your developer profile. See [infra/terraform/iam/README.md](../infra/terraform/iam/README.md).

### DynamoDB, local and AWS

Same table name both places: `CuratedContent`. Same key shape: `SUBJECT#Biology#CLASS#SSS 1#THEME#1`.

| | Local | AWS |
|---|---|---|
| How you select it | `DYNAMODB_ENDPOINT_URL=http://localhost:8000` | Unset `DYNAMODB_ENDPOINT_URL` |
| Process | `make up` then `uv run python scripts/create_dynamodb_tables.py` | Table already exists in `eu-west-1`. Do not create a second one from a laptop pointed at AWS unless you were asked to. |
| Lifetime | Empty again after the container stops | Persistent. This is what the product backend reads. |
| Who should write | Your pipeline `publish` step, or the portal with `PORTAL_PUBLISH_ENABLED=true`, while the endpoint is local | Only after a lesson is approved, and only against the table you meant. |

`.env` is loaded first. `.env.content-api` does not override a variable that `.env` already set. If `.env` contains `DYNAMODB_ENDPOINT_URL=http://localhost:8000`, `make content-api` reads DynamoDB Local even when the content-api example file leaves that line commented. To read the AWS table, comment the endpoint out of `.env`, then restart the API.

Leave `PORTAL_PUBLISH_ENABLED=false` until you intend to write DynamoDB. With the endpoint still on localhost, a publish stays on your laptop. With the endpoint unset, the same button writes the AWS table.

## Run only the cheap path first

This reads the PDF, checks the curriculum, and embeds chunks. It does not draft lessons.

```bash
uv run python scripts/run_pipeline.py --pipeline-version 2
```

That runs, in order: `extract`, `validate`, `align`, `filter_relevance`.

| Step | What you should see afterward |
|---|---|
| `extract` | Chunks and figure records in PostgreSQL. Figures uploaded to S3 when a bucket is configured. `textbook_image_manifest.json` updated. |
| `validate` | Curriculum JSON accepted. Unit ids assigned. |
| `align` | Each unit linked to textbook chunks in PostgreSQL (`pgvector`). |
| `filter_relevance` | Chunks marked relevant or not. This calls a model. |

`filter_relevance` spends API credits. `extract` on the full PDF takes a long time. You can run one step:

```bash
uv run python scripts/run_pipeline.py --pipeline-version 2 --steps validate
```

## Run lesson drafting only when you mean to

Drafting, judging, and publishing call models and can write DynamoDB.

```bash
uv run python scripts/run_pipeline.py --full --pipeline-version 2
```

Full order with version 2:

`extract` → `validate` → `align` → `filter_relevance` → `curate` → `judge` → `publish`

Optional curriculum rewrite, inserted after `validate`:

```bash
uv run python scripts/run_pipeline.py --full --pipeline-version 2 --refine-curriculum
```

Useful limits while you are learning the prompts:

```bash
uv run python scripts/run_pipeline.py --steps curate --pipeline-version 2 --curate-unit bio_sss1_theme1_topic1_content0
uv run python scripts/run_pipeline.py --full --pipeline-version 2 --resume-from curate
uv run python scripts/run_pipeline.py --full --pipeline-version 2 --skip-judge
```

Inside `curate`, one unit goes through this sequence:

1. Text curator writes the lesson from the relevant excerpts.
2. Media linker and formula resolver run.
3. Module assembler builds the stored lesson.

The student-facing body is Markdown in `curated_content`. Figures are a separate `images` list. A "(Figure 1)" written in the prose is not the same number as an OpenStax caption such as `FIGURE 34.1`.

Outputs to inspect on the **local** pipeline database:

- `data/docs/extracted_source_content/biology/curated_content.json`
- PostgreSQL table `ibrary.curated_content` on `localhost:5432`
- Judge results beside that JSON when `judge` has run

`publish` writes DynamoDB. With the example `.env`, that is DynamoDB Local, not AWS.

## Reviewer portal

The portal process runs on your laptop. Its database is whichever URL `DATABASE_URL_REVIEW` names.

```bash
uv run python scripts/run_review_portal.py
```

Open http://127.0.0.1:8090.

- Unset `DATABASE_URL_REVIEW`: reviews are stored in local Docker Postgres.
- Set `DATABASE_URL_REVIEW` to the Neon **development** direct host: reviews are stored in that Neon branch.
- Cognito is optional for a first look and required for a real login. Set `COGNITO_USER_POOL_ID`, `COGNITO_APP_CLIENT_ID`, and `COGNITO_REGION=eu-west-1` from the Terraform outputs. The pool is in AWS, not in Docker.

Approval does not publish to DynamoDB unless `PORTAL_PUBLISH_ENABLED=true`. Leave that off until you intend to publish, and check `DYNAMODB_ENDPOINT_URL` first so you know which table receives the write.

The UI source is `review-ui/`. The API is `src/ibrary/review/`. Node 22 is required to build the UI (`review-ui/.nvmrc`).

## Content read API

The API process is local. The table it reads depends on `DYNAMODB_ENDPOINT_URL`, including a value inherited from `.env`.

```bash
cp .env.content-api.example .env.content-api
make content-api
```

Open http://127.0.0.1:8080/docs. `GET /health` does not need a key. Lesson routes need the `X-API-Key` header. The key comes from `CONTENT_API_KEYS`.

Partition keys look like `SUBJECT#Biology#CLASS#SSS 1#THEME#1`. Subject is part of the key so more than one subject can share the table later.

To read the AWS table, unset `DYNAMODB_ENDPOINT_URL` and use the `ibrary-dev` profile, or the read-only `ibrary-content-api` keys described in the IAM doc. To read only your laptop, keep the endpoint on `http://localhost:8000` and run `make up` first.

## After reviews exist

The reviews for this assignment are already in Neon. Do not submit a new one. Ask the group for the direct URL of that database, set `DATABASE_URL_REVIEW`, and only read.

Reviewer scores are `ibrary.content_manual_quality_check`. The `scores` JSON has `representation`, `engagement`, and `action_expression`, plus `notes` and `checked_by`. The LLM judge is a different table, `ibrary.content_udl_scores`, joined on `curriculum_unit_id`. Its `scores` JSON has `representation_score`, `engagement_score`, `action_expression_score`, `correctness_score`, `clarity_score`, `passed`, and `checkpoint_scores`. If `DATABASE_URL_REVIEW` is unset, a query uses local Docker and will not show these reviews.

```bash
psql "$DATABASE_URL_REVIEW" -c "
SELECT
  m.curriculum_unit_id,
  m.checked_by,
  m.notes,
  m.overall_score AS reviewer_overall,
  m.scores->>'representation' AS reviewer_representation,
  m.scores->>'engagement' AS reviewer_engagement,
  m.scores->>'action_expression' AS reviewer_action_expression,
  u.overall_score AS judge_overall,
  u.scores->>'representation_score' AS judge_representation,
  u.scores->>'engagement_score' AS judge_engagement,
  u.scores->>'action_expression_score' AS judge_action_expression,
  u.scores->>'correctness_score' AS judge_correctness,
  u.scores->>'clarity_score' AS judge_clarity,
  u.scores->>'passed' AS judge_passed
FROM ibrary.content_manual_quality_check m
LEFT JOIN ibrary.content_udl_scores u
  ON u.curriculum_unit_id = m.curriculum_unit_id
ORDER BY m.created_at DESC;
"
```

Do not run Alembic or a loader against that URL. Checkpoint notes stay inside `u.scores->'checkpoint_scores'` when you need them for a gap.

Review comments can also be summarized into prompt weaknesses. That code lives in `src/ibrary/prompt_improvement/review_weaknesses.py`. It is not a step inside `run_pipeline.py`, and it does not compare reviewer scores with the judge. It reads review evidence from the portal database (`DATABASE_URL_REVIEW`, Neon when that is set), asks a model for grounded weaknesses, and retries when the model cites a source id that was not supplied. The model name is `OPENAI_REVIEW_SUMMARY_MODEL`, falling back to `OPENAI_MODEL`.

## Map of the code

| Path | Role |
|---|---|
| `src/ibrary/config.py` | Every environment setting |
| `src/ibrary/models.py` | PostgreSQL tables |
| `src/ibrary/textbook/` | PDF extract and load |
| `src/ibrary/curriculum/` | Curriculum checks and unit ids |
| `src/ibrary/alignment/` | Embeddings and similarity search |
| `src/ibrary/relevance/` | Pipeline v2 gate |
| `src/ibrary/curation/` | Lesson prompts and JSON schema |
| `src/ibrary/pipeline/` | Curate orchestration |
| `src/ibrary/enrichment/` | Images and formulas |
| `src/ibrary/judging/` | UDL score |
| `src/ibrary/review/` | Portal API |
| `src/ibrary/serving/api.py` | Public read API |
| `src/ibrary/serving/dynamodb_writer.py` | Writes approved lessons |
| `src/ibrary/serving/keys.py` | DynamoDB key shape |
| `review-ui/` | Portal frontend |
| `alembic/versions/` | Database migrations |
| `scripts/run_pipeline.py` | Pipeline entry point |

## First week

Work through [tasks.html](tasks.html) in order. It is the assignment: local setup, the flow, extract the Neon reviews and set them beside the judge, then a written proposal for a judge calibrated to those reviews. Use [SETUP.md](../SETUP.md) when a command fails. Do not start `--full` as part of that assignment.

When something fails, look at [SETUP.md](../SETUP.md) under Common Issues before changing model code. Failed model calls are retried three times. If they still fail, the lesson is marked for review rather than published as if it succeeded.
