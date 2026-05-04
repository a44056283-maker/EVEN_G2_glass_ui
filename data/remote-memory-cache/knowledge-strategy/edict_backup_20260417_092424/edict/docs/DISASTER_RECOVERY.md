# 灾难恢复文档 (DISASTER_RECOVERY.md)

> 工部（技术运维部）- 基础设施灾备手册  
> 版本: v1.0 | 更新: 2025-01-15

---

## 📋 目录

1. [RTO/RPO目标](#rtto-rpo-目标)
2. [服务分级与恢复顺序](#服务分级与恢复顺序)
3. [自动恢复机制](#自动恢复机制)
4. [手动干预检查清单](#手动干预检查清单)
5. [故障场景与应对](#故障场景与应对)
6. [通知流程](#通知流程)

---

## 🎯 RTO/RPO 目标

| 服务 | RTO (恢复时间) | RPO (数据丢失窗口) | 优先级 |
|------|---------------|-------------------|--------|
| 三省六部系统 (7891) | 5分钟 | <1分钟 | P0 |
| 控制台 (9099) | 5分钟 | <1分钟 | P0 |
| Freqtrade Bot (9090-9093) | 10分钟 | <5分钟 | P1 |
| Cloudflared 隧道 | 15分钟 | N/A | P1 |
| S/R 扫描服务 | 30分钟 | N/A | P2 |

---

## 🔢 服务分级与恢复顺序

### 启动顺序 (Ordered Boot Sequence)

```
P0 (核心控制)
  1. cloudflared 隧道 → 确保外网可达
  2. 控制台 9099 → 提供统一管理界面
  3. 三省六部 7891 → 决策系统

P1 (交易引擎)
  4. freqtrade-9090 (Gate-17656685222)
  5. freqtrade-9091 (Gate-85363904550)
  6. freqtrade-9092 (Gate-15637798222)
  7. freqtrade-9093 (OKX-15637798222)

P2 (辅助服务)
  8. S/R 扫描服务
```

### 关闭顺序 (Graceful Shutdown)

```
P2 → P1 → P0
```

---

## 🤖 自动恢复机制

### port_scan.py 看门狗

看门狗实现**三层监控**：

```
┌─────────────────────────────────────────────────────────┐
│  L1: 进程存活检查 (CRITICAL)                            │
│      - 使用 pgrep 检查进程是否存在                      │
│      - 进程死 → 立即重启 + 飞书CRITICAL告警             │
├─────────────────────────────────────────────────────────┤
│  L2: 端口响应检查 (WARNING)                              │
│      - curl 测试 HTTP 200                               │
│      - 超时5秒 → 重启 + 飞书WARNING告警                 │
├─────────────────────────────────────────────────────────┤
│  L3: API业务指标检查 (INFO)                             │
│      - 测量响应时间                                      │
│      - >2s 警告, >5s 严重 → 记录日志                    │
└─────────────────────────────────────────────────────────┘
```

### 自动恢复流程图

```
                    ┌──────────────┐
                    │  检测到故障  │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        ┌─────────┐  ┌──────────┐  ┌─────────┐
        │ 进程死  │  │ 端口不通 │  │响应慢   │
        │ CRITICAL│  │ WARNING  │  │ INFO    │
        └───┬─────┘  └────┬─────┘  └────┬────┘
            │             │             │
            ▼             ▼             ▼
     ┌────────────┐  ┌──────────┐  ┌──────────┐
     │立即重启    │  │尝试重启   │  │记录日志  │
     │+ CRITICAL │  │+ WARNING │  │+ 详细记录 │
     │飞书告警   │  │飞书告警  │  │          │
     └─────┬─────┘  └────┬─────┘  └────┬────┘
           │              │             │
           ▼              ▼             ▼
     ┌──────────┐  ┌──────────┐  ┌──────────┐
     │ 验证成功 │  │ 验证成功 │  │          │
     │ + INFO   │  │ + INFO   │  │          │
     │ 恢复通知 │  │ 恢复通知 │  │          │
     └────┬─────┘  └────┬─────┘  └────┬─────┘
          │              │             │
          ▼              ▼             ▼
     ┌─────────────────────────────────────────┐
     │           恢复失败? → 人工介入          │
     └─────────────────────────────────────────┘
```

---

## 📝 手动干预检查清单

### 🔴 紧急故障 (CRITICAL)

**现象**: 多个服务同时不可用 / 进程全部死亡

```
□ 1. 检查网络连接
   - ping openclaw.tianlu2026.org
   - curl https://console.tianlu2026.org

□ 2. 检查 cloudflared 状态
   - pgrep -f cloudflared
   - tail -20 ~/.cloudflared/*.log

□ 3. 重启 cloudflared 隧道
   - cd ~/.cloudflared
   - ./cloudflared --config config-tianlu.yml tunnel run aa05ab31-21df-4431-81bf-4ae6a98792fb

□ 4. 检查端口占用
   - lsof -i :7891
   - lsof -i :9099

□ 5. 检查日志
   - tail -50 ~/edict/data/logs/edict.log
   - tail -50 ~/edict/data/logs/console.log
```

### 🟡 交易机器人故障 (WARNING)

**现象**: 单个或多个 Bot 无响应

```
□ 1. 检查 Bot 进程
   - pgrep -f "freqtrade.*9090"
   - pgrep -f "freqtrade.*9091"
   - pgrep -f "freqtrade.*9092"
   - pgrep -f "freqtrade.*9093"

□ 2. 检查 Bot 日志
   - tail -100 /tmp/ft_9090.log
   - tail -100 /tmp/ft_9091.log
   - tail -100 /tmp/ft_9092.log
   - tail -100 /tmp/ft_9093.log

□ 3. 手动重启单个 Bot
   - cd ~/freqtrade
   - source .venv/bin/activate
   - freqtrade trade -c config_shared.json -c config_gate_overlay.json -s FOttStrategy

□ 4. 验证 Bot 在线
   - curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:9090/api/v1/ping

□ 5. 检查持仓状态（防止爆仓）
   - 访问 http://localhost:9099
   - 确认所有持仓正常
```

### 🔵 性能问题 (INFO)

**现象**: API 响应慢 / 内存使用率高

```
□ 1. 检查系统资源
   - top -o %MEM
   - df -h
   - free -m

□ 2. 检查端口健康
   - curl http://127.0.0.1:9099/health

□ 3. 内存释放（如需要）
   - sync && echo 3 > /proc/sys/vm/drop_caches  (Linux)
   - macOS: 重启相关进程

□ 4. 重启控制台
   - pkill -f "console_server.py"
   - cd ~/freqtrade_console
   - nohup python3 console_server.py &
```

---

## 🚨 故障场景与应对

### 场景1: cloudflared 隧道断开

**检测**:
```bash
# 自动检测：port_scan.py 每分钟检查
curl -s -o /dev/null -w '%{http_code}' https://console.tianlu2026.org
```

**影响**: 所有外网域名不可访问

**恢复**:
```bash
# 1. 检查进程
pgrep -f cloudflared

# 2. 如进程不存在，重启
cd ~/.cloudflared
nohup cloudflared --config config-tianlu.yml tunnel run aa05ab31-21df-4431-81bf-4ae6a98792fb &

# 3. 验证
sleep 5
curl -s -o /dev/null -w '%{http_code}' https://console.tianlu2026.org
```

---

### 场景2: Freqtrade Bot 崩溃

**检测**:
```bash
# 自动检测：port_scan.py L1层
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:9090/api/v1/ping
```

**影响**: 该 Bot 对应的交易对停止交易

**恢复**:
```bash
# 1. 检查是否真的死了
curl -s http://127.0.0.1:9090/api/v1/ping

# 2. 检查日志
tail -100 /tmp/ft_9090.log

# 3. 确认无持仓（防止平仓时机不当）
curl -s http://127.0.0.1:9090/api/v1/status

# 4. 重启 Bot
cd ~/freqtrade
source .venv/bin/activate
nohup freqtrade trade -c config_shared.json -c config_gate_overlay.json -s FOttStrategy > /tmp/ft_9090.log 2>&1 &

# 5. 验证
sleep 10
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:9090/api/v1/ping
```

---

### 场景3: 控制台 (9099) 无响应

**检测**:
```bash
curl http://127.0.0.1:9099/health
```

**影响**: 无法通过 Web UI 管理所有 Bot

**恢复**:
```bash
# 1. 检查进程
pgrep -f "console_server.py"

# 2. 重启控制台
pkill -f "console_server.py"
cd ~/freqtrade_console
nohup python3 console_server.py > ~/edict/data/logs/console.log 2>&1 &

# 3. 验证
sleep 3
curl http://127.0.0.1:9099/health
```

---

### 场景4: 系统内存耗尽

**检测**:
```bash
# 自动检测：console_server.py L2层
curl http://127.0.0.1:9099/health | jq '.layers.L2_memory'
```

**影响**: 所有服务响应极慢或崩溃

**恢复**:
```bash
# 1. 检查内存使用
top -o %MEM

# 2. 找出内存大户
ps aux --sort=-%mem | head -10

# 3. 重启高内存进程
# 优先重启非关键服务

# 4. 如仍不足，重启所有服务
# 按 P2 → P1 → P0 顺序
```

---

## 📞 通知流程

### 告警分级

| 级别 | 触发条件 | 通知方式 | 响应时效 |
|------|---------|---------|---------|
| 🚨 CRITICAL | 进程死亡 / 端口超时 | 飞书+电话 | 5分钟内 |
| ⚠️ WARNING | 端口不通 / 响应慢 | 飞书 | 30分钟内 |
| ℹ️ INFO | 恢复通知 / 性能记录 | 飞书 | 工作时间 |

### 通知接收人

```
CRITICAL: 太子 (oc_5016041d5ee6ed2a8cc4e98372569cec) + 电话
WARNING:  太子 (oc_5016041d5ee6ed2a8cc4e98372569cec)
INFO:     仅日志记录
```

---

## 🔧 维护命令速查

```bash
# 查看所有服务状态
python3 ~/edict/scripts/port_scan.py

# 重启 cloudflared
pkill -f cloudflared && sleep 2 && cd ~/.cloudflared && nohup cloudflared --config config-tianlu.yml tunnel run aa05ab31-21df-4431-81bf-4ae6a98792fb &

# 重启控制台
pkill -f console_server.py && cd ~/freqtrade_console && nohup python3 console_server.py &

# 重启单个 Bot (以9090为例)
pkill -f "ft_9090.log" && sleep 2 && cd ~/freqtrade && source .venv/bin/activate && nohup freqtrade trade -c config_shared.json -c config_gate_overlay.json -s FOttStrategy > /tmp/ft_9090.log 2>&1 &

# 查看端口健康
curl -s http://127.0.0.1:9099/health | python3 -m json.tool

# 查看 Bot 状态
curl -s -u freqtrade:freqtrade http://127.0.0.1:9090/api/v1/ping
```

---

_文档版本: v1.0 | 最后更新: 2025-01-15 | 维护者: 工部（技术运维部）_
