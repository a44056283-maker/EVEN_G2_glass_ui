#!/usr/bin/env bash
set -euo pipefail

TASK_NAME="${1:-manual-review}"
SAFE_TASK_NAME="$(echo "$TASK_NAME" | tr ' /:' '___')"
ROOT="$(pwd)"
STAMP="$(date +%Y%m%d_%H%M)"
BUNDLE_NAME="${STAMP}_${SAFE_TASK_NAME}"
BUNDLE_DIR="$ROOT/docs/gpt-advisor/bundles/$BUNDLE_NAME"
ZIP_PATH="$ROOT/docs/gpt-advisor/bundles/${BUNDLE_NAME}.zip"

source "$ROOT/scripts/gpt-advisor/cloud_config.sh"

mkdir -p "$BUNDLE_DIR"

{
  echo "# Claude Final Report"
  echo ""
  echo "Task: $TASK_NAME"
  echo "Generated: $(date)"
  echo "Project: $ROOT"
  echo ""
  echo "## Summary"
  echo ""
  echo "请 Claude 在此处填写本轮最终总结。"
} > "$BUNDLE_DIR/01_CLAUDE_FINAL_REPORT.md"

{
  echo "# Modified Files"
  echo ""
  git status --short 2>/dev/null || echo "No git"
  echo ""
  echo "## Git Diff Name Only"
  git diff --name-only 2>/dev/null || echo "No git"
} > "$BUNDLE_DIR/02_MODIFIED_FILES.md"

{
  echo "# Test Results"
  echo ""
  echo "Please run: npm run typecheck && npm run build && npm run pack:g2"
} > "$BUNDLE_DIR/03_TEST_RESULTS.md"

{
  echo "# EHPK SHA256"
  echo ""
  find "$ROOT/apps/evenhub-plugin" -maxdepth 3 -name "*.ehpk" -print0 2>/dev/null | xargs -0 shasum -a 256 2>/dev/null || echo "No EHPK found"
} > "$BUNDLE_DIR/04_EHPK_SHA256.txt"

cp "$ROOT/docs/gpt-advisor/ISSUE_REGISTER.md" "$BUNDLE_DIR/05_OPEN_ISSUES.md" 2>/dev/null || {
  echo "# Open Issues" > "$BUNDLE_DIR/05_OPEN_ISSUES.md"
}

cp "$ROOT/docs/gpt-advisor/NEXT_ACTIONS.md" "$BUNDLE_DIR/06_NEXT_ACTIONS.md" 2>/dev/null || {
  echo "# Next Actions" > "$BUNDLE_DIR/06_NEXT_ACTIONS.md"
}

{
  echo "# Cloud Sync Info"
  echo ""
  echo "Generated: $(date)"
  echo "Project root: $ROOT"
  echo "Bundle dir: $BUNDLE_DIR"
  echo "Local zip: $ZIP_PATH"
  echo "iCloud outbox: $ICLOUD_OUTBOX"
  echo "iCloud latest: $ICLOUD_LATEST/latest_review_bundle.zip"
} > "$BUNDLE_DIR/07_CLOUD_SYNC_INFO.md"

LATEST_REPORT="$(ls -t "$ROOT"/docs/gpt-advisor/test-reports/*.md 2>/dev/null | head -n 1 || true)"
if [ -n "$LATEST_REPORT" ]; then
  cp "$LATEST_REPORT" "$BUNDLE_DIR/latest_test_report.md"
fi

git diff -- . ':!**/.env' ':!**/.env.*' ':!**/node_modules/**' ':!**/dist/**' > "$BUNDLE_DIR/optional_patch_diff.diff" 2>/dev/null || true

rm -f "$ZIP_PATH"
(cd "$BUNDLE_DIR" && zip -r "$ZIP_PATH" . >/dev/null 2>&1)

SHA="$(shasum -a 256 "$ZIP_PATH" | awk '{print $1}')"

cp "$ZIP_PATH" "$ICLOUD_OUTBOX/"
cp "$ZIP_PATH" "$ICLOUD_LATEST/latest_review_bundle.zip"

{
  echo "# Latest Outbox Bundle"
  echo ""
  echo "Task: $TASK_NAME"
  echo "Generated: $(date)"
  echo "Local bundle: $ZIP_PATH"
  echo "iCloud outbox bundle: $ICLOUD_OUTBOX/$(basename "$ZIP_PATH")"
  echo "iCloud latest: $ICLOUD_LATEST/latest_review_bundle.zip"
  echo "SHA256: $SHA"
} > "$ROOT/docs/gpt-advisor/cloud-sync/LATEST_OUTBOX_BUNDLE.md"

cp "$ROOT/docs/gpt-advisor/cloud-sync/LATEST_OUTBOX_BUNDLE.md" "$ICLOUD_LATEST/LATEST_OUTBOX_BUNDLE.md"

echo "Bundle created:"
echo "$ZIP_PATH"
echo ""
echo "Copied to iCloud outbox:"
echo "$ICLOUD_OUTBOX/$(basename "$ZIP_PATH")"
echo ""
echo "Latest copy:"
echo "$ICLOUD_LATEST/latest_review_bundle.zip"
echo ""
echo "SHA256: $SHA"
