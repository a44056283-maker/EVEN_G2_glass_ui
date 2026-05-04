#!/bin/bash
# ===============================================
# 兵部 · 备份脚本框架
# 适用：数据库/行情数据/交易日志/持仓快照
# ===============================================

set -euo pipefail

BACKUP_ROOT="/data/backup"
DATE=$(date '+%Y-%m-%d')
TIME=$(date '+%H')
OSS_BUCKET="oss://quant-backup"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] BACKUP $1"
}

# ---------- 全量备份（每日收盘后） ----------
backup_full() {
    local type="$1"
    local src="$2"
    local dest="$BACKUP_ROOT/daily/$DATE/${type}.tar.gz"

    mkdir -p "$BACKUP_ROOT/daily/$DATE"
    log "开始全量备份: $type"
    tar -czf "$dest" "$src" 2>/dev/null || true
    log "✅ 全量备份完成: $dest"
    
    # 校验
    md5sum "$dest" > "${dest}.md5"
    
    # 同步到对象存储
    # TODO: 配置ossutil后启用
    # ossutil cp "$dest" "$OSS_BUCKET/daily/$DATE/${type}.tar.gz"
}

# ---------- 增量备份（每15min/每小时） ----------
backup_incremental() {
    local type="$1"
    local src="$2"
    local hour="${TIME}h"
    local dest="$BACKUP_ROOT/incremental/$DATE/${hour}.${type}.inc.gz"

    mkdir -p "$BACKUP_ROOT/incremental/$DATE"
    log "开始增量备份: $type @ $hour"
    tar -czf "$dest" -g /dev/null "$src" 2>/dev/null || true
    log "✅ 增量备份完成: $dest"
}

# ---------- 数据库备份 ----------
backup_db() {
    local db_name="${1:-quant}"
    log "开始数据库备份: $db_name"
    # TODO: 配置数据库连接后启用
    # pg_dump -h localhost -U postgres "$db_name" | gzip > "$BACKUP_ROOT/daily/$DATE/db_${db_name}.sql.gz"
    log "✅ 数据库备份完成（占位）"
}

# ---------- 备份验证 ----------
verify_backup() {
    local backup_file="$1"
    if [[ -f "${backup_file}.md5" ]]; then
        local expected_md5=$(cat "${backup_file}.md5" | awk '{print $1}')
        local actual_md5=$(md5sum "$backup_file" | awk '{print $1}')
        if [[ "$expected_md5" == "$actual_md5" ]]; then
            log "✅ 备份校验通过: $backup_file"
            echo '{"file":"'"$backup_file"'","status":"ok","md5":"'"$actual_md5"'"}'
        else
            log "❌ 备份校验失败: $backup_file"
            echo '{"file":"'"$backup_file"'","status":"failed","md5":"'"$actual_md5"'"}'
        fi
    fi
}

# ---------- 主逻辑 ----------
case "${1:-full}" in
    full)
        backup_db
        backup_full "trade_log" "/var/log/trade"   # TODO: 确认路径
        backup_full "position"   "/data/positions"   # TODO: 确认路径
        ;;
    incremental)
        backup_incremental "trade_log" "/var/log/trade"
        ;;
    verify)
        verify_backup "$2"
        ;;
    *)
        echo "用法: $0 {full|incremental|verify <file>}"
        ;;
esac
