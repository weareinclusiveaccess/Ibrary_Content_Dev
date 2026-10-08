#!/usr/bin/env python3
"""Create DynamoDB tables for local development."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ibrary.serving.dynamodb_writer import create_table

if __name__ == "__main__":
    create_table()
    print("DynamoDB tables ready.")
