#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="$ROOT_DIR/services/local-whisper-asr"
VENV_DIR="$ROOT_DIR/.venv-local-whisper-asr"
LOG_DIR="$ROOT_DIR/.logs"
PID_FILE="$LOG_DIR/local-whisper-asr.pid"
LOG_FILE="$LOG_DIR/local-whisper-asr.log"

mkdir -p "$LOG_DIR"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$SERVICE_DIR/requirements.txt"

if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(cat "$PID_FILE" || true)"
  if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "local-whisper-asr already running: pid=$OLD_PID"
    exit 0
  fi
fi

LOCAL_WHISPER_HOST="${LOCAL_WHISPER_HOST:-127.0.0.1}"
LOCAL_WHISPER_PORT="${LOCAL_WHISPER_PORT:-8791}"
LOCAL_WHISPER_MODEL="${LOCAL_WHISPER_MODEL:-base}"
LOCAL_WHISPER_DEVICE="${LOCAL_WHISPER_DEVICE:-cpu}"
LOCAL_WHISPER_COMPUTE_TYPE="${LOCAL_WHISPER_COMPUTE_TYPE:-int8}"

nohup env \
  PYTHONUNBUFFERED=1 \
  LOCAL_WHISPER_HOST="$LOCAL_WHISPER_HOST" \
  LOCAL_WHISPER_PORT="$LOCAL_WHISPER_PORT" \
  LOCAL_WHISPER_MODEL="$LOCAL_WHISPER_MODEL" \
  LOCAL_WHISPER_DEVICE="$LOCAL_WHISPER_DEVICE" \
  LOCAL_WHISPER_COMPUTE_TYPE="$LOCAL_WHISPER_COMPUTE_TYPE" \
  "$VENV_DIR/bin/python" "$SERVICE_DIR/server.py" \
  >"$LOG_FILE" 2>&1 &

PID="$!"
echo "$PID" > "$PID_FILE"
echo "local-whisper-asr started: pid=$PID url=http://$LOCAL_WHISPER_HOST:$LOCAL_WHISPER_PORT log=$LOG_FILE"
