#!/usr/bin/env python3
"""Run the human review portal (FastAPI + static UI)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import uvicorn

from ibrary.config import REVIEW_API_HOST, REVIEW_API_PORT


def main() -> None:
    uvicorn.run(
        "ibrary.review.api:app",
        host=REVIEW_API_HOST,
        port=REVIEW_API_PORT,
        reload=True,
    )


if __name__ == "__main__":
    main()
