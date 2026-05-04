#!/bin/bash
# ===============================================
# 兵部 · 告警发送脚本
# 支持：钉钉/短信/电话 P0-P2分级
# ===============================================

set -euo pipefail

# ---------- 配置区（TODO: 运行时注入） ----------
DINGTALK_WEBHOOK="${DINGTALK_WEBHOOK:-}"
SMS_API="${SMS_API:-}"
PHONE_API="${PHONE_API:-}"
ALERT_LOG="/var/log/quant/alert.log"
# -----------------------------

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ALERT $1" >> "$ALERT_LOG"
}

send_dingtalk() {
    local level="$1"
    local msg="$2"
    if [[ -z "$DINGTALK_WEBHOOK" ]]; then
        log "钉钉未配置，跳过: $msg"
        return 1
    fi
    local emoji="🔴"
    case "$level" in
        WARNING) emoji="🟠" ;;
        CRITICAL) emoji="🔴" ;;
        INFO) emoji="ℹ️" ;;
    esac
    local payload=$(cat << PAYLOAD
{
    "msgtype": "text",
    "text": {
        "content": "${emoji} [${level}] 量化交易监控系统\n$msg\n时间: $(date '+%Y-%m-%d %H:%M:%S')"
    }
}
PAYLOAD
)
    curl -s -X POST "$DINGTALK_WEBHOOK" \
        -H "Content-Type: application/json" \
        -d "$payload" > /dev/null
    log "钉钉告警已发送: $level $msg"
}

send_sms() {
    local phone="$1"
    local msg="$2"
    if [[ -z "$SMS_API" ]]; then
        log "短信API未配置，跳过: $phone $msg"
        return 1
    fi
    # TODO: 对接短信API
    log "短信已发送: $phone $msg"
}

call_phone() {
    local phone="$1"
    local msg="$2"
    if [[ -z "$PHONE_API" ]]; then
        log "电话API未配置，跳过: $phone $msg"
        return 1
    fi
    # TODO: 对接电话API（P0告警）
    log "电话已拨打: $phone $msg"
}

# ---------- 主逻辑 ----------
case "$1" in
    P0)
        log "P0告警: $2"
        send_dingtalk "CRITICAL" "$2"
        call_phone "${3:-13800000000}" "$2"  # TODO: 配置紧急电话
        send_sms "${3:-13800000000}" "$2"
        ;;
    P1)
        log "P1告警: $2"
        send_dingtalk "CRITICAL" "$2"
        send_sms "${4:-13800000000}" "$2"
        ;;
    P2)
        log "P2告警: $2"
        send_dingtalk "WARNING" "$2"
        ;;
    *)
        echo "用法: $0 {P0|P1|P2} <消息> [电话] [电话2...]"
        ;;
esac
