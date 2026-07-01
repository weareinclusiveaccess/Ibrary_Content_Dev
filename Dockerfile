# syntax=docker/dockerfile:1.7
#
# Reviewer portal image: builds the React SPA, then bundles it with the FastAPI
# backend into a small runtime image. The EC2 user data fetches secrets from
# SSM Parameter Store and runs this image with `docker run --env-file ...`.
#
# Build locally:
#   docker build -t ibrary-review-api:dev .
#   docker run --rm -p 8090:8090 --env-file .env ibrary-review-api:dev
#
# Push to ECR (after `terraform apply` creates the repo):
#   REPO=$(cd infra/terraform/environments/dev && terraform output -raw portal_ecr_repository_url)
#   aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin "${REPO%%/*}"
#   SHA=$(git rev-parse --short HEAD)
#   docker build -t "$REPO:$SHA" -t "$REPO:latest" .
#   docker push "$REPO:$SHA"
#   docker push "$REPO:latest"

# ---------- Stage 1: build the React UI ----------------------------------
# Use debian-slim (glibc) rather than alpine (musl) — rolldown / esbuild
# native bindings are better supported on glibc, and npm has bugs with
# optional deps that bite hard on musl (see npm/cli#4828).
FROM node:22-slim AS ui-builder
WORKDIR /app/review-ui

# Install deps. We can't use `npm ci` with the committed package-lock.json
# because the lockfile was generated on Windows and npm has a long-standing
# bug (npm/cli#4828) where platform-specific optional deps (e.g. rolldown's
# native bindings) are not correctly cross-platform resolved from a foreign
# lockfile — the Linux binding URLs simply aren't there. We deliberately
# drop the lockfile here so npm resolves a fresh tree for the container's
# platform. Reproducibility is anchored by the node image SHA + package.json
# semver constraints; commit-time lockfile only governs local dev.
COPY review-ui/package.json review-ui/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm,sharing=locked \
    rm -f package-lock.json \
    && npm install --no-audit --no-fund --include=optional

# Copy UI sources and build the dist
COPY review-ui/ ./
RUN npm run build

# ---------- Stage 2: Python runtime --------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS runtime

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# OS deps required by psycopg2 + PyJWT[crypto] (cryptography wheels are prebuilt;
# libssl is still useful at runtime). Keep this lean.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies from lockfile. Doing this before copying source
# means subsequent code edits don't bust this layer. The cache mount keeps
# uv's HTTP cache across rebuilds — even if pyproject.toml/uv.lock change,
# the multi-GB CUDA/torch wheels don't have to be redownloaded from PyPI.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv sync --frozen --no-dev --no-install-project

# Copy ONLY the Python modules the reviewer portal needs at runtime. The full
# pipeline (textbook extraction, curation generation, alignment/embedding,
# evaluation, prompts, orchestrator, …) is deliberately NOT shipped to the
# production image. That keeps the deployment surface minimal:
#   - smaller image, less attack surface
#   - prod credentials can never accidentally be used by pipeline code that
#     isn't there
#   - any drift from "the portal also runs the pipeline" requires an explicit
#     COPY here, not a silent inclusion
#
# Minimum portal closure (derived from import-graph audit):
#   ibrary.{__init__, config, db, models}     ← core runtime
#   ibrary.review.*                            ← reviewer portal app
#   ibrary.serving.*                           ← DynamoDB writer (publish action)
#   ibrary.curation.{__init__, schemas,        ← imported by serving.dynamodb_writer
#                    curated_postgres}
#
# If a future portal route imports e.g. ibrary.alignment, add it explicitly here
# AND audit whether the corresponding heavy deps belong in the `pipeline` extra
# or in core (see pyproject.toml).
RUN mkdir -p src/ibrary/review src/ibrary/serving src/ibrary/curation
COPY src/ibrary/__init__.py                  src/ibrary/__init__.py
COPY src/ibrary/config.py                    src/ibrary/config.py
COPY src/ibrary/db.py                        src/ibrary/db.py
COPY src/ibrary/models.py                    src/ibrary/models.py
COPY src/ibrary/review/                      src/ibrary/review/
COPY src/ibrary/serving/                     src/ibrary/serving/
COPY src/ibrary/curation/__init__.py         src/ibrary/curation/__init__.py
COPY src/ibrary/curation/schemas.py          src/ibrary/curation/schemas.py
COPY src/ibrary/curation/curated_postgres.py src/ibrary/curation/curated_postgres.py

# Alembic kept in the image so operators can run one-off migrations via
# `docker exec portal alembic upgrade head`. env.py only touches ibrary.config
# and ibrary.models, both of which we copy above — no pipeline imports.
COPY alembic.ini ./
COPY alembic/    alembic/

COPY README.md ./
COPY --from=ui-builder /app/review-ui/dist review-ui/dist

# Install the project itself (after source is present). Reuses the cached
# wheels from the previous uv sync — only the project's own editable wheel
# is built here.
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv sync --frozen --no-dev

# Entrypoint script handles any pre-flight tasks (e.g. waiting for DB, logging build info)
COPY entrypoint-ec2.sh /usr/local/bin/entrypoint-ec2.sh
RUN chmod +x /usr/local/bin/entrypoint-ec2.sh

# Non-root user for the runtime (matches AL2023 expectations + best practice)
RUN useradd --create-home --shell /bin/bash --uid 1001 ibrary \
    && chown -R ibrary:ibrary /app
USER ibrary

EXPOSE 8090

# Healthcheck — CloudFront will probe via the public path, but a docker-level
# healthcheck helps for local docker run and EC2 systemd restart-on-unhealthy.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8090/health || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint-ec2.sh"]
CMD ["uvicorn", "ibrary.review.api:app", \
     "--host", "0.0.0.0", "--port", "8090", \
     "--proxy-headers", "--forwarded-allow-ips=*"]
