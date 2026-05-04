#!/usr/bin/env bash
set -euo pipefail

ROOT="$(pwd)"
source "$ROOT/scripts/gpt-advisor/cloud_config.sh"

mkdir -p "$ROOT/docs/gpt-advisor/reviews/from-gpt"

LATEST_REVIEW="$(ls -t "$ICLOUD_INBOX"/GPT_REVIEW_*.md 2>/dev/null | head -n 1 || true)"

if [ -z "$LATEST_REVIEW" ]; then
  echo "No GPT_REVIEW_*.md found in $ICLOUD_INBOX"
  exit 0
fi

DEST="$ROOT/docs/gpt-advisor/reviews/from-gpt/$(basename "$LATEST_REVIEW")"
cp "$LATEST_REVIEW" "$DEST"

echo "Copied GPT review:"
echo "$DEST"
