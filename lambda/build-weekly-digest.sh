#!/usr/bin/env bash
# Build Lambda deployment package for WEEKLY DIGEST ONLY
# Your existing function.zip stays untouched!
# Usage: bash lambda/build-weekly-digest.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$SCRIPT_DIR/package-weekly"
ZIP_FILE="$SCRIPT_DIR/weekly-digest.zip"

echo "Building weekly digest Lambda package..."
echo "→ Your existing function.zip will NOT be modified"

echo "Installing dependencies..."
pip install -r "$SCRIPT_DIR/requirements.txt" -t "$PACKAGE_DIR" --quiet

echo "Copying weekly digest source files..."
cp "$SCRIPT_DIR/collector.py" "$PACKAGE_DIR/"
cp "$SCRIPT_DIR/digest_sender.py" "$PACKAGE_DIR/"

echo "Creating weekly-digest.zip..."
cd "$PACKAGE_DIR"
zip -r "$ZIP_FILE" . --quiet

echo "Cleaning up package directory..."
rm -rf "$PACKAGE_DIR"

echo ""
echo "✅ Done: $ZIP_FILE"
echo "✅ Original function.zip preserved"
echo ""
echo "Files in package:"
echo "  - collector.py"
echo "  - digest_sender.py"
echo "  - dependencies (feedparser, requests, etc.)"
