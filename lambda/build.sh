#!/usr/bin/env bash
# Build Lambda deployment package
# Usage: bash lambda/build.sh (run from repo root)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$SCRIPT_DIR/package"
ZIP_FILE="$SCRIPT_DIR/function.zip"

echo "Installing dependencies..."
pip install -r "$SCRIPT_DIR/requirements.txt" -t "$PACKAGE_DIR" --quiet

echo "Copying Lambda source files..."
cp "$SCRIPT_DIR"/*.py "$PACKAGE_DIR/"

echo "Creating function.zip..."
cd "$PACKAGE_DIR"
zip -r "$ZIP_FILE" . --quiet

echo "Cleaning up package directory..."
rm -rf "$PACKAGE_DIR"

echo "Done: $ZIP_FILE"
