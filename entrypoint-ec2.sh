#!/bin/sh
# Container entrypoint for the IBrary reviewer portal.
#
# Runs inside the container. Secrets are injected by the EC2 host via
# `docker run --env-file ...` (see modules/ec2_portal/main.tf user data),
# so this script only does lightweight pre-flight checks and execs the
# real command.

set -e

if [ -n "${IBRARY_BUILD_SHA}" ]; then
  echo "[entrypoint] starting IBrary review portal build=${IBRARY_BUILD_SHA}"
fi

# Fail-fast on required Cognito config. DATABASE_URL has a (dev-only) default
# in src/ibrary/config.py, so checking it here would be misleading — let
# SQLAlchemy surface the real error on first request instead.
missing=""
for key in COGNITO_USER_POOL_ID COGNITO_APP_CLIENT_ID; do
  eval val=\$$key
  if [ -z "$val" ]; then
    missing="$missing $key"
  fi
done

if [ -n "$missing" ]; then
  echo "[entrypoint] FATAL: missing required env vars:$missing" >&2
  echo "[entrypoint] Set them via SSM Parameter Store under /ibrary/review/* (prod) or .env (dev)." >&2
  exit 78  # EX_CONFIG
fi

# Allow ad-hoc shell access via `docker exec` while still execing the configured CMD.
exec "$@"
