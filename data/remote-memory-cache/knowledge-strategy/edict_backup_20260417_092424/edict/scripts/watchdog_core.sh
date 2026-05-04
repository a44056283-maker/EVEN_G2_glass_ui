#!/bin/bash
# ===============================================
# 兵部 · 看门狗核心进程守护脚本
# 适用：行情服务/交易通道/策略引擎/风控服务/Redis
# ===============================================

set -euo pipefail

# ---------- 配置区 ----------
MAX_RESTARTS=5
WINDOW_SEC=300      # 5分钟内
RESTART_INTERVAL=30 # 重启间隔(秒)
WATCHDOG_LOG="/var/log/watchdog.log"
PID_DIR="/var/run/watchdog"
# -----------------------------

mkdir -p "$PID_DIR" "$WATCHDOG_LOG"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WATCHDOG $1" | tee -a "$WATCHDOG_LOG"
}

check_and_restart() {
    local svc_name="$1"
    local pid_file="$PID_DIR/${svc_name}.pid"
    local start_cmd="$2"       # 启动命令
    local max_restarts="${3:-$MAX_RESTARTS}"
    local window="${4:-$WINDOW_SEC}"
    local interval="${5:-$RESTART_INTERVAL}"

    local count_file="$PID_DIR/${svc_name}.count"
    local last_reset_file="$PID_DIR/${svc_name}.reset"

    # 窗口过期，重置计数
    if [[ -f "$last_reset_file" ]]; then
        local last_reset=$(cat "$last_reset_file")
        local now=$(date +%s)
        if (( now - last_reset > window )); then
            echo 0 > "$count_file"
            echo $now > "$last_reset_file"
        fi
    else
        echo 0 > "$count_file"
        echo $(date +%s) > "$last_reset_file"
    fi

    local restart_count=$(cat "$count_file" 2>/dev/null || echo 0)

    # 检查进程是否存活
    if [[ -f "$pid_file" ]] && kill -0 $(cat "$pid_file") 2>/dev/null; then
        log "$svc_name: 进程存活 (PID=$(cat $pid_file))"
        echo 0 > "$count_file"
        return 0
    fi

    # 进程不存活，尝试重启
    (( restart_count++ ))
    echo $restart_count > "$count_file"

    if (( restart_count > max_restarts )); then
        log "🚨 $svc_name: 重启次数超限 ($restart_count/$max_restarts)，标记为Dead，触发P0告警"
        # TODO: 触发钉钉/短信P0告警
        return 1
    fi

    log "⚠️  $svc_name: 进程退出，第${restart_count}次重启，${interval}s后执行"
    sleep $interval

    eval "$start_cmd" &
    local new_pid=$!
    echo $new_pid > "$pid_file"
    sleep 2

    if kill -0 $new_pid 2>/dev/null; then
        log "✅ $svc_name: 重启成功 (PID=$new_pid)"
        echo 0 > "$count_file"
    else
        log "❌ $svc_name: 重启失败，继续累计"
    fi
}

# ---------- 示例服务配置 ----------
# check_and_restart "md_server"    "python3 /opt/quant/md_server.py"    5 300 30
# check_and_restart "trade_gateway" "python3 /opt/quant/trade_gateway.py" 3 180 60
# check_and_restart "risk_server"  "python3 /opt/quant/risk_server.py"   999 60 10  # 风控不允许失败
# check_and_restart "redis_server" "redis-server /etc/redis/redis.conf"  5 300 30
