#!/bin/bash
# ===============================================
# 兵部 · 监控指标采集脚本
# 适用：WORK_PLAN.md 1.1节所有监控对象
# ===============================================

set -euo pipefail

LOG_DIR="/var/log/quant/monitor"
METRICS_FILE="$LOG_DIR/metrics.json"
ALERT_SCRIPT="/Users/luxiangnan/.openclaw/workspace-bingbu/scripts/alert.sh"

mkdir -p "$LOG_DIR"

log_alert() {
    local level="$1"
    local msg="$2"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [${level}] $msg" >> "$LOG_DIR/alert.log"
    # TODO: 调用告警脚本
    # bash "$ALERT_SCRIPT" "$level" "$msg"
}

check_threshold() {
    local metric="$1"
    local value="$2"
    local warn="$3"
    local crit="$4"
    if (( $(echo "$value > $crit" | bc -l) )); then
        log_alert "CRITICAL" "$metric=$value (阈值>$crit)"
        return 2
    elif (( $(echo "$value > $warn" | bc -l) )); then
        log_alert "WARNING" "$metric=$value (阈值>$warn)"
        return 1
    fi
    return 0
}

# ---------- 行情接收服务 ----------
check_market_data() {
    # TODO: 接入实际行情API获取延迟和丢包率
    local delay_ms="${1:-50}"
    local loss_rate="${2:-0.01}"
    check_threshold "md_delay_ms" "$delay_ms" 300 500
    check_threshold "md_loss_rate" "$loss_rate" 0.5 1.0
    echo "md_delay_ms=$delay_ms md_loss_rate=$loss_rate"
}

# ---------- 交易执行服务 ----------
check_trade_exec() {
    # TODO: 接入交易通道API获取订单延迟和拒单率
    local order_delay_ms="${1:-80}"
    local reject_rate="${2:-0.1}"
    check_threshold "trade_order_delay_ms" "$order_delay_ms" 100 200
    check_threshold "trade_reject_rate" "$reject_rate" 0.3 0.5
    echo "trade_order_delay_ms=$order_delay_ms trade_reject_rate=$reject_rate"
}

# ---------- 策略引擎 ----------
check_strategy_engine() {
    local cpu=$(top -l 1 | grep "CPU usage" | awk '{print $3}' | tr -d '%')
    local mem=$(vm_stat | grep "Pages active" | awk '{print $3}' | tr -d '.')
    # TODO: 更精确的内存计算
    check_threshold "strategy_cpu" "$cpu" 80 90
    echo "strategy_cpu=$cpu strategy_mem_pages=$mem"
}

# ---------- 数据库 ----------
check_database() {
    # TODO: 连接数据库获取QPS/连接数/复制延迟
    local conn_pct="${1:-45}"
    local repl_delay="${2:-0.5}"
    check_threshold "db_conn_pct" "$conn_pct" 70 80
    check_threshold "db_repl_delay_s" "$repl_delay" 3 5
    echo "db_conn_pct=$conn_pct db_repl_delay_s=$repl_delay"
}

# ---------- Redis缓存 ----------
check_redis() {
    # TODO: redis-cli info 获取命中率/内存/连接数
    local hit_rate="${1:-98.5}"
    local mem_pct="${2:-60}"
    check_threshold "redis_hit_rate" "$hit_rate" 97 95
    check_threshold "redis_mem_pct" "$mem_pct" 70 75
    echo "redis_hit_rate=$hit_rate redis_mem_pct=$mem_pct"
}

# ---------- 消息队列 ----------
check_mq() {
    # TODO: rabbitmqctl / kafka Topics
    local queue_depth="${1:-500}"
    local consumer_lag="${2:-2}"
    check_threshold "mq_queue_depth" "$queue_depth" 5000 10000
    check_threshold "mq_consumer_lag_s" "$consumer_lag" 5 10
    echo "mq_queue_depth=$queue_depth mq_consumer_lag_s=$consumer_lag"
}

# ---------- 风控引擎 ----------
check_risk_engine() {
    # TODO: 风控API健康检查
    local resp_ms="${1:-30}"
    check_threshold "risk_resp_ms" "$resp_ms" 80 100
    echo "risk_resp_ms=$resp_ms"
}

# ---------- 服务器基础 ----------
check_server() {
    local cpu=$(top -l 1 | grep "CPU usage" | awk '{print $3}' | tr -d '%')
    local disk=$(df -h / | tail -1 | awk '{print $5}' | tr -d '%')
    check_threshold "server_cpu" "$cpu" 85 90
    check_threshold "server_disk_pct" "$disk" 80 85
    echo "server_cpu=$cpu server_disk_pct=$disk"
}

# ---------- 主循环 ----------
collect_all() {
    local ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    local metrics=$(cat << METRICS
{
    "ts": "$ts",
    "market_data": { $(check_market_data) },
    "trade_exec": { $(check_trade_exec) },
    "strategy": { $(check_strategy_engine) },
    "database": { $(check_database) },
    "redis": { $(check_redis) },
    "mq": { $(check_mq) },
    "risk": { $(check_risk_engine) },
    "server": { $(check_server) }
}
METRICS
)
    echo "$metrics" >> "$METRICS_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 指标采集完成"
}

# ---------- 采集频率控制 ----------
case "${1:-10s}" in
    5s) collect_all ;;
    10s) collect_all ;;
    30s) collect_all ;;
    1min) while true; do collect_all; sleep 60; done ;;
    *) echo "用法: $0 {5s|10s|30s|1min}" ;;
esac
