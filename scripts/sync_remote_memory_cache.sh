#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-192.168.13.48}"
REMOTE_USER="${REMOTE_USER:-luxiangnan}"
TARGET_DIR="${TARGET_DIR:-$(cd "$(dirname "$0")/.." && pwd)/data/remote-memory-cache}"

mkdir -p "$TARGET_DIR"/{codex-memories,daily-evolution,tianlu-memory,knowledge-strategy}

EXCLUDES=(
  "--exclude=.env"
  "--exclude=*.env"
  "--exclude=*key*"
  "--exclude=*Key*"
  "--exclude=*KEY*"
  "--exclude=*token*"
  "--exclude=*Token*"
  "--exclude=*TOKEN*"
  "--exclude=*secret*"
  "--exclude=*Secret*"
  "--exclude=*SECRET*"
  "--exclude=*credential*"
  "--exclude=*Credential*"
  "--exclude=*CREDENTIAL*"
  "--exclude=*.pem"
  "--exclude=*.p12"
  "--exclude=*.mobileprovision"
  "--exclude=node_modules"
  "--exclude=.git"
  "--exclude=.DS_Store"
)

sync_one() {
  local remote_path="$1"
  local local_path="$2"
  local escaped_remote_path
  escaped_remote_path=$(printf '%q' "$remote_path")
  rsync -az --delete "${EXCLUDES[@]}" \
    -e "ssh -o BatchMode=yes -o ConnectTimeout=8" \
    "${REMOTE_USER}@${REMOTE_HOST}:${escaped_remote_path}/" \
    "${TARGET_DIR}/${local_path}/"
}

sync_one "/Users/${REMOTE_USER}/.codex/memories" "codex-memories"
sync_one "/Users/${REMOTE_USER}/Desktop/每日进化日志" "daily-evolution"
sync_one "/Users/${REMOTE_USER}/Desktop/🧠 天禄记忆库" "tianlu-memory"
sync_one "/Users/${REMOTE_USER}/Desktop/Knowledge_Strategy_Base" "knowledge-strategy"

date '+%Y-%m-%d %H:%M:%S %Z' > "$TARGET_DIR/.last_sync"

echo "Memory cache synced to: $TARGET_DIR"
