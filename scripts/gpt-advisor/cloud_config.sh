#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$(pwd)}"
ICLOUD_ROOT="${HOME}/Library/Mobile Documents/com~apple~CloudDocs/Tianlu-G2-Claude-Reports"
ICLOUD_OUTBOX="${ICLOUD_ROOT}/outbox"
ICLOUD_INBOX="${ICLOUD_ROOT}/inbox-from-gpt"
ICLOUD_ARCHIVE="${ICLOUD_ROOT}/archive"
ICLOUD_LATEST="${ICLOUD_ROOT}/latest"
ICLOUD_LOGS="${ICLOUD_ROOT}/logs"

mkdir -p "$ICLOUD_OUTBOX" "$ICLOUD_INBOX" "$ICLOUD_ARCHIVE" "$ICLOUD_LATEST" "$ICLOUD_LOGS"
mkdir -p "$PROJECT_ROOT/docs/gpt-advisor/bundles"
mkdir -p "$PROJECT_ROOT/docs/gpt-advisor/reviews/from-gpt"
mkdir -p "$PROJECT_ROOT/docs/gpt-advisor/reviews/applied"
mkdir -p "$PROJECT_ROOT/docs/gpt-advisor/cloud-sync"
