#!/usr/bin/env bash
set -uo pipefail

DEST_BASE="${DEST_BASE:-/Volumes/TianLu_Storage}"
TS="$(date +%Y%m%d_%H%M%S)"
ROOT="${DEST_BASE}/V65_Trading_System_Full_Backup_${TS}"
LOG="${ROOT}/backup_run.log"

mkdir -p \
  "${ROOT}/00_SERVICE_SNAPSHOTS" \
  "${ROOT}/07_logs" \
  "${ROOT}/08_proxy_and_tunnel" \
  "${ROOT}/09_launchd_cron" \
  "${ROOT}/10_restore_notes"

exec > >(tee -a "${LOG}") 2>&1

echo "# V6.5 Trading System Full Backup"
echo "start=$(date '+%F %T')"
echo "root=${ROOT}"

run_capture() {
  local name="$1"
  shift
  echo "[snapshot] ${name}"
  /usr/bin/perl -e 'alarm shift @ARGV; exec @ARGV' 25 "$@" > "${ROOT}/00_SERVICE_SNAPSHOTS/${name}" 2>&1 || true
}

copy_dir() {
  local src="$1"
  local dest="$2"
  local label="$3"
  echo
  echo "==== ${label} ===="
  if [ -e "${src}" ]; then
    mkdir -p "${dest}"
    rsync -aE --human-readable --stats "${src}/" "${dest}/"
    local rc=$?
    if [ "${rc}" -eq 0 ]; then
      echo "[ok] ${label}"
    else
      echo "[warn] ${label} rsync exit=${rc}; backup continues"
    fi
  else
    echo "[skip] ${label} source missing: ${src}"
  fi
}

copy_file() {
  local src="$1"
  local destdir="$2"
  local label="$3"
  echo
  echo "==== ${label} ===="
  mkdir -p "${destdir}"
  if [ -e "${src}" ]; then
    rsync -aE --human-readable --stats "${src}" "${destdir}/"
    local rc=$?
    if [ "${rc}" -eq 0 ]; then
      echo "[ok] ${label}"
    else
      echo "[warn] ${label} rsync exit=${rc}; backup continues"
    fi
  else
    echo "[skip] ${label} source missing: ${src}"
  fi
}

run_capture process_trading_services.txt pgrep -fl "freqtrade|console_server.py|edict/dashboard/server.py|openclaw|cloudflared|mihomo|watchdog|dns_watchdog|proxy_watchdog"
run_capture listening_ports.txt lsof -nP -iTCP -sTCP:LISTEN
run_capture disk_usage.txt df -h
run_capture launchctl_user.txt launchctl list
run_capture crontab.txt crontab -l
run_capture openclaw_gateway_status.txt openclaw gateway status
run_capture openclaw_status.txt openclaw status
run_capture openclaw_cron_list.json openclaw cron list --json
run_capture openclaw_models_tianlu.txt openclaw models list --agent tianlu
run_capture scutil_proxy.txt scutil --proxy
run_capture network_locations.txt networksetup -listallnetworkservices
run_capture cloudflared_version.txt cloudflared --version

copy_dir "/Users/luxiangnan/freqtrade" "${ROOT}/01_MacA_freqtrade_9090_9097" "Mac A freqtrade 9090-9097完整目录"
copy_dir "/Users/luxiangnan/freqtrade_console" "${ROOT}/02_console_9099_tianyan_chushan" "9099控制台+天眼AI+出山AI完整目录"
copy_dir "/Users/luxiangnan/edict" "${ROOT}/03_sanshengliubu_7891" "7891三省六部系统完整目录"
copy_dir "/Users/luxiangnan/.openclaw" "${ROOT}/04_openclaw_feishu_agents_cron" "OpenClaw+飞书机器人+Cron+动态干预完整目录"
copy_dir "/Users/luxiangnan/.codex" "${ROOT}/04b_codex_model_provider_config" "Codex模型供应商配置"

copy_dir "/Users/luxiangnan/.cloudflared" "${ROOT}/08_proxy_and_tunnel/cloudflared" "Cloudflared隧道配置"
copy_dir "/Users/luxiangnan/OpenClaw-Scripts" "${ROOT}/08_proxy_and_tunnel/OpenClaw-Scripts" "OpenClaw脚本/实时备份"
copy_dir "/Users/luxiangnan/Library/Application Support/mihomo-standalone" "${ROOT}/08_proxy_and_tunnel/mihomo-standalone" "mihomo-standalone代理配置"
copy_dir "/Users/luxiangnan/Library/Application Support/mihomo-party" "${ROOT}/08_proxy_and_tunnel/mihomo-party" "Clash Party/mihomo代理配置"
copy_file "/Users/luxiangnan/start_mihomo.sh" "${ROOT}/08_proxy_and_tunnel" "start_mihomo.sh"
copy_file "/Users/luxiangnan/proxy_watchdog.sh" "${ROOT}/08_proxy_and_tunnel" "proxy_watchdog.sh"
copy_file "/Users/luxiangnan/proxy_watchdog.log" "${ROOT}/08_proxy_and_tunnel" "proxy_watchdog.log"
copy_file "/Users/luxiangnan/dns_watchdog.py" "${ROOT}/08_proxy_and_tunnel" "dns_watchdog.py"
copy_file "/Users/luxiangnan/.cloudflared/config-tianlu.yml" "${ROOT}/08_proxy_and_tunnel" "config-tianlu.yml"
copy_file "/Users/luxiangnan/.mcp.json" "${ROOT}/04_openclaw_feishu_agents_cron" "MCP配置"

copy_dir "/Users/luxiangnan/Library/LaunchAgents" "${ROOT}/09_launchd_cron/User_LaunchAgents" "用户LaunchAgents"
copy_dir "/tmp/openclaw" "${ROOT}/07_logs/tmp_openclaw" "OpenClaw临时日志"
for f in /tmp/console_server.log /tmp/bot_agent_*.log /tmp/freqtrade*.log /tmp/openclaw*.log; do
  [ -e "${f}" ] && rsync -aE "${f}" "${ROOT}/07_logs/" || true
done
copy_dir "/Users/luxiangnan/edict/data/logs" "${ROOT}/07_logs/edict_data_logs" "edict日志"
copy_file "/Users/luxiangnan/Library/Logs/com.cloudflare.cloudflared.watchdog.log" "${ROOT}/07_logs" "cloudflared watchdog日志"

echo
echo "==== Mac B 8081-8084远程备份 ===="
MACB_HOST="192.168.13.104"
MACB_USER="luxiangnan"
MACB_PASS="$(python3 - <<'PY'
import re, pathlib
p = pathlib.Path('/Users/luxiangnan/freqtrade_console/backup_v65_full.py')
m = re.search(r'MAC_B_PASS\\s*=\\s*"([^"]+)"', p.read_text())
print(m.group(1) if m else '')
PY
)"
if [ -n "${MACB_PASS}" ] && /opt/homebrew/bin/sshpass -p "${MACB_PASS}" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=12 "${MACB_USER}@${MACB_HOST}" "echo ok" > /tmp/macb_ssh_check.out 2>&1; then
  echo "[ok] Mac B SSH reachable"
  /opt/homebrew/bin/sshpass -p "${MACB_PASS}" ssh -o StrictHostKeyChecking=no "${MACB_USER}@${MACB_HOST}" \
    "ps aux | egrep 'freqtrade|8081|8082|8083|8084|console_server|mihomo|cloudflared' | egrep -v egrep; lsof -nP -iTCP -sTCP:LISTEN" \
    > "${ROOT}/00_SERVICE_SNAPSHOTS/macb_services_ports.txt" 2>&1 || true
  mkdir -p "${ROOT}/06_MacB_freqtrade_8081_8084"
  rsync -aE --human-readable --stats \
    -e "/opt/homebrew/bin/sshpass -p ${MACB_PASS} ssh -o StrictHostKeyChecking=no" \
    "${MACB_USER}@${MACB_HOST}:/Users/luxiangnan/freqtrade/" \
    "${ROOT}/06_MacB_freqtrade_8081_8084/"
  rc=$?
  if [ "${rc}" -eq 0 ]; then
    echo "[ok] Mac B freqtrade 8081-8084完整目录"
  else
    echo "[warn] Mac B rsync exit=${rc}; see backup log"
  fi
else
  echo "[warn] Mac B SSH unreachable; see /tmp/macb_ssh_check.out" | tee "${ROOT}/06_MacB_BACKUP_WARNING.txt"
  cat /tmp/macb_ssh_check.out >> "${ROOT}/06_MacB_BACKUP_WARNING.txt" 2>/dev/null || true
fi

cat > "${ROOT}/10_restore_notes/RESTORE_README.md" <<EOF
# V6.5 Trading System Restore Notes

Backup root: ${ROOT}
Created: $(date '+%F %T')

Main contents:
- 01_MacA_freqtrade_9090_9097: Mac A trading robots 9090-9097
- 02_console_9099_tianyan_chushan: 9099 console, Tianyan AI, Chushan AI
- 03_sanshengliubu_7891: Edict dashboard / SanShengLiuBu 7891
- 04_openclaw_feishu_agents_cron: OpenClaw config, Feishu integration, agents, cron jobs, intervention workflow
- 04b_codex_model_provider_config: Codex provider config used by OpenClaw/Cron
- 06_MacB_freqtrade_8081_8084: Mac B trading robots 8081-8084, if SSH was reachable
- 08_proxy_and_tunnel: cloudflared, mihomo/Clash, watchdog and proxy settings
- 09_launchd_cron: LaunchAgents and cron snapshots

Restore is rsync based. Stop target services first, then rsync each folder back to its original path and restart services.
This backup contains live credentials and API keys. Keep the external drive private.
EOF

find "${ROOT}" -maxdepth 3 -type d | sort > "${ROOT}/BACKUP_TREE_DIRS.txt"
find "${ROOT}" -maxdepth 3 -type f | sort > "${ROOT}/BACKUP_TREE_FILES.txt"
du -sh "${ROOT}" | tee "${ROOT}/BACKUP_SIZE.txt"

echo
echo "==== 创建整体归档包 ===="
ARCHIVE="${DEST_BASE}/V65_Trading_System_Full_Backup_${TS}.tar.gz"
tar -czf "${ARCHIVE}" -C "${DEST_BASE}" "$(basename "${ROOT}")"
tar_rc=$?
if [ "${tar_rc}" -eq 0 ]; then
  ls -lh "${ARCHIVE}" | tee "${ROOT}/ARCHIVE_INFO.txt"
  echo "[ok] archive created"
else
  echo "[warn] archive tar exit=${tar_rc}"
fi

echo "end=$(date '+%F %T')"
echo "BACKUP_ROOT=${ROOT}"
echo "BACKUP_ARCHIVE=${ARCHIVE}"
