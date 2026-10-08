#!/bin/sh
set -eu

TARGET_DIR="data/docs/extracted_source_content/biology"
TARGET_FILE="$TARGET_DIR/Biology2e-WEB.pdf"
DOWNLOAD_URL="https://assets.openstax.org/oscms-prodcms/media/documents/Biology2e-WEB.pdf"

if [ -f "$TARGET_FILE" ] && [ -s "$TARGET_FILE" ]; then
    echo "Textbook already exists at $TARGET_FILE ($(du -h "$TARGET_FILE" | cut -f1) ). Skipping download."
    exit 0
fi

mkdir -p "$TARGET_DIR"

echo "Downloading OpenStax Biology 2e (~380 MB) ..."
echo "Source: $DOWNLOAD_URL"
echo "Target: $TARGET_FILE"

if command -v curl > /dev/null 2>&1; then
    curl -L --progress-bar -o "$TARGET_FILE" "$DOWNLOAD_URL"
elif command -v wget > /dev/null 2>&1; then
    wget --show-progress -O "$TARGET_FILE" "$DOWNLOAD_URL"
else
    echo "ERROR: Neither curl nor wget found. Please install one and retry." >&2
    exit 1
fi

if [ ! -s "$TARGET_FILE" ]; then
    echo "ERROR: Download failed — file is empty or missing." >&2
    rm -f "$TARGET_FILE"
    exit 1
fi

echo "Download complete: $TARGET_FILE ($(du -h "$TARGET_FILE" | cut -f1))"
