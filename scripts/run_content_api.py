#!/usr/bin/env python3
"""Run the DynamoDB content read API."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import uvicorn

from ibrary.config import CONTENT_API_HOST, CONTENT_API_PORT


def main() -> None:
    reload = os.getenv("ENVIRONMENT", "development").lower() in ("development", "dev", "local")
    uvicorn.run(
        "ibrary.serving.api:app",
        host=CONTENT_API_HOST,
        port=CONTENT_API_PORT,
        reload=reload,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
