#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT_DIR/.logs/local-whisper-asr.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "local-whisper-asr is not running"
  exit 0
fi

PID="$(cat "$PID_FILE" || true)"
if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  echo "local-whisper-asr stopped: pid=$PID"
fi
rm -f "$PID_FILE"
