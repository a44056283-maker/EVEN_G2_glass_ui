#!/bin/bash
# cloudflared 看门狗脚本
# 监控断线次数，超过阈值发飞书告警

LOG_FILE="/Users/luxiangnan/Library/Logs/com.cloudflare.cloudflared.err.log"
STATE_FILE="/tmp/cloudflared-watchdog.state"
ALERT_THRESHOLD=5          # 5次断线发告警
RESET_HOURS=1              # 1小时后重置计数
WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/$(cat ~/.openclaw/config.json | python3 -c 'import json,sys; c=json.load(sys.stdin); print(c.get("feishu",{}).get("webhook",""))' 2>/dev/null || echo '')"

# 获取上次告警时间
last_alert=$(cat "$STATE_FILE" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin) if sys.stdin.read().strip() else {}; print(d.get('last_alert',0))" 2>/dev/null || echo "0")
now=$(date +%s)

# 检查是否在冷却期内（1小时）
if [ "$now" -lt "$((last_alert + RESET_HOURS * 3600))" ]; then
    echo "[看门狗] 冷却期内，跳过检查"
    exit 0
fi

# 统计最近告警次数（最近RESET_HOURS小时内）
# 用 Python 避免 awk 逐行调用外部 date 命令（原来 6700+ 次调用巨慢）
window=$((RESET_HOURS * 3600))
cutoff_ts=$(date -j -v-${RESET_HOURS}H +%s 2>/dev/null || date -d "last hour" +%s 2>/dev/null)
cutoff_str=$(date -j -f %s $cutoff_ts +"%Y-%m-%dT%H:%M:%S" 2>/dev/null || date -d @$cutoff_ts -u +"%Y-%m-%dT%H:%M:%S" 2>/dev/null)

recent_count=$(python3 - << 'PYEOF' 2>/dev/null
import re
pattern = re.compile(r"Connection terminated|Unable to establish|Serve tunnel error")
cutoff = """$cutoff_str"""
count = 0
try:
    with open("$LOG_FILE", 'r', errors='ignore') as f:
        for line in f:
            if pattern.search(line):
                ts_str = line[:19]
                if ts_str >= cutoff:
                    count += 1
except:
    print("0")
    exit(0)
print(count)
PYEOF
)

if [ "${recent_count:-0}" -ge "$ALERT_THRESHOLD" ]; then
    msg="⚠️ Cloudflare Tunnel 看门狗告警
近${RESET_HOURS}小时内断线 ${recent_count} 次（阈值${ALERT_THRESHOLD}）
建议检查网络状况或考虑切回 http2"

    echo "[看门狗] 告警触发: recent_count=${recent_count}"

    # 发飞书通知
    if [ -n "$WEBHOOK_URL" ] && [[ "$WEBHOOK_URL" != *"None"* ]] && [[ "$WEBHOOK_URL" != *"猫"* ]]; then
        curl -s -X POST "$WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d "{\"msg_type\":\"text\",\"content\":{\"text\":\"$msg\"}}" 2>/dev/null
    fi

    # 更新状态
    echo "{\"last_alert\":$now,\"count\":$recent_count}" > "$STATE_FILE"
fi

echo "[看门狗] 检查完成. 近${RESET_HOURS}h断线次数: ${recent_count:-0}"
