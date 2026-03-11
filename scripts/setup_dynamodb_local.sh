#!/bin/sh
set -eu

echo "Starting DynamoDB Local via Docker Compose..."
docker compose up -d dynamodb-local

echo "Waiting for DynamoDB Local to be ready..."
sleep 3

echo "Creating tables..."
python scripts/create_dynamodb_tables.py

echo "DynamoDB Local setup complete."
