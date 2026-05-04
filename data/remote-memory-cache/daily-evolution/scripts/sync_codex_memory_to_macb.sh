#!/usr/bin/env bash
set -euo pipefail

# Sync Codex/TianLu memory from this Mac to computer B.
# Usage:
#   bash sync_codex_memory_to_macb.sh
#   MACB_HOST=192.168.13.104 MACB_USER=luxiangnan bash sync_codex_memory_to_macb.sh

MACB_HOST="${MACB_HOST:-192.168.13.104}"
MACB_USER="${MACB_USER:-luxiangnan}"
REMOTE="${MACB_USER}@${MACB_HOST}"

TS="$(date '+%Y%m%d_%H%M%S')"
LOG_DIR="$HOME/Desktop/每日进化日志/sync_logs"
LOG_FILE="$LOG_DIR/codex_memory_sync_${TS}.log"

mkdir -p "$LOG_DIR"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

run_remote() {
  ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$REMOTE" "$@"
}

rsync_common=(
  -az
  --human-readable
  --itemize-changes
  --delete
  --exclude ".DS_Store"
  --exclude "*.pem"
  --exclude "*.key"
  --exclude "*.env"
  --exclude ".env*"
  --exclude "*token*"
  --exclude "*Token*"
  --exclude "*credential*"
  --exclude "*Credential*"
  --exclude "*secret*"
  --exclude "*Secret*"
  --exclude "*webhook*"
  --exclude "*Webhook*"
)

sync_dir() {
  local src="$1"
  local dst="$2"
  local label="$3"

  if [ ! -e "$src" ]; then
    log "SKIP $label: source not found: $src"
    return 0
  fi

  log "SYNC $label"
  run_remote "mkdir -p '$dst'"
  rsync "${rsync_common[@]}" "$src/" "$REMOTE:$dst/" | tee -a "$LOG_FILE"
}

log "Start Codex memory sync to $REMOTE"

run_remote "mkdir -p \
  '$HOME/.codex/memories' \
  '$HOME/Desktop/每日进化日志' \
  '$HOME/Desktop/🧠 天禄记忆库' \
  '$HOME/Desktop/Knowledge_Strategy_Base' \
  '$HOME/.codex'"

sync_dir "$HOME/.codex/memories" "$HOME/.codex/memories" "Codex local memories"
sync_dir "$HOME/Desktop/每日进化日志" "$HOME/Desktop/每日进化日志" "Daily evolution logs"
sync_dir "$HOME/Desktop/🧠 天禄记忆库" "$HOME/Desktop/🧠 天禄记忆库" "TianLu memory library"

if [ -d "/Volumes/TianLu_Archive/Knowledge_Strategy_Base" ]; then
  sync_dir "/Volumes/TianLu_Archive/Knowledge_Strategy_Base" "$HOME/Desktop/Knowledge_Strategy_Base" "Strategy knowledge base"
elif [ -d "$HOME/Desktop/Knowledge_Strategy_Base" ]; then
  sync_dir "$HOME/Desktop/Knowledge_Strategy_Base" "$HOME/Desktop/Knowledge_Strategy_Base" "Strategy knowledge base"
else
  log "SKIP Strategy knowledge base: source not found"
fi

BOOTSTRAP_FILE="$(mktemp)"
cat > "$BOOTSTRAP_FILE" <<'EOF'
# Computer B Codex Memory Bootstrap

When working for luxiangnan, first read these local memory locations when the task depends on trading-system history, TianLu evolution work, or prior Codex decisions:

- ~/.codex/memories
- ~/Desktop/每日进化日志
- ~/Desktop/🧠 天禄记忆库
- ~/Desktop/Knowledge_Strategy_Base

Core trading-system rules:

- V6.5 complete rules are the hard controller.
- FOttStrategy is only an exchange API shell, not a strategy source.
- Trading robots only execute; they do not own autonomous entry, exit, take-profit, or stop-loss decisions.
- Tianyan AI is an auditor and administrator for V6.5 entry signals.
- Chushan AI is an auditor and administrator for V6.5 exit, correction, take-profit, and stop-loss signals.
- AI must not override V6.5 with soft reasoning.
- New rules must enter L5 shadow testing before touching live bots.

Security rule:

Do not copy or expose exchange API keys, .env files, Cloudflare tokens, Feishu webhooks, OpenClaw gateway tokens, or remote passwords.
EOF

scp -q -o StrictHostKeyChecking=no "$BOOTSTRAP_FILE" "$REMOTE:$HOME/.codex/COMPUTER_B_MEMORY_BOOTSTRAP.md"
rm -f "$BOOTSTRAP_FILE"

run_remote "cat > '$HOME/Desktop/🧠 天禄记忆库/AGENTS.md' <<'EOF'
# AGENTS.md - TianLu Memory Library on Computer B

Before answering TianLu trading-system or evolution-system questions, inspect:

- ~/.codex/memories
- ~/Desktop/每日进化日志
- ~/Desktop/🧠 天禄记忆库
- ~/Desktop/Knowledge_Strategy_Base

Hard rule: V6.5 is the controller. AI is auditor/admin only. Robots execute only.
EOF"

log "Remote bootstrap written:"
log "  $REMOTE:$HOME/.codex/COMPUTER_B_MEMORY_BOOTSTRAP.md"
log "  $REMOTE:$HOME/Desktop/🧠 天禄记忆库/AGENTS.md"

log "Done. Log saved to $LOG_FILE"
