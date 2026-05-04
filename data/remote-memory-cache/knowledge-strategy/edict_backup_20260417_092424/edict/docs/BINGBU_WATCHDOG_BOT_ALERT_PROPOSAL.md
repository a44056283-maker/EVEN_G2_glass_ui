# 看门狗 Bot 离线飞书通知增强提案

> 版本: v1.0
> 日期: 2026-03-30
> 执行: 太子（天禄）
> 目标: 工部

---

## 一、问题描述

**现状：**
- `bingbu_watchdog.py` 每 30 秒检查一次 9090/9091/9092/9093 Bot 存活状态
- 检查结果写入日志，但 **Bot 离线时不发飞书通知**
- 导致 9091 机器人掉线后 2 小时无人知晓，直到父亲主动查看才发现

**根因：**
- `check_all_bots()` 只返回状态字符串 `🟢9090:在线 | 🔴9091:离线`
- 有 `send_feishu_alert()` 基础设施（隧道中断/代理中断会发通知）
- **Bot 离线判断分支存在，但未调用飞书通知**

---

## 二、修复方案

### 2.1 修改位置

文件：`/Users/luxiangnan/edict/scripts/bingbu_watchdog.py`

### 2.2 改动逻辑

**新增功能：** Bot 离线 → 飞书通知 + 自动重启尝试

```python
# 在主循环中，bot_status 检查后增加：

# ── Bot 离线检测 ──
offline_bots = []
for port in [9090, 9091, 9092, 9093, 9094, 9095, 9096, 9097]:
    if not check_bot(port):
        offline_bots.append(port)

if offline_bots:
    bot_names = "/".join(map(str, offline_bots))
    log(f"Bot离线: {offline_bots}", "ERR")
    send_feishu_alert(
        "bot_offline",
        f"🤖 Bot掉线: {bot_names}",
        f"⚠️ 以下Bot无响应:\n" + "\n".join([f"• :909{port} → 🔴离线" for port in offline_bots]) + f"\n\n🔧 正在尝试重启...",
        template="red"
    )
    # 自动重启离线Bot
    for port in offline_bots:
        restart_bot(port)  # 需要实现 restart_bot()
else:
    if prev_offline:  # 有Bot刚从离线恢复
        send_feishu_alert(
            "bot_recover",
            "✅ Bot恢复",
            f"所有Bot已恢复在线",
            template="green"
        )
    prev_offline = False
```

### 2.3 新增函数

```python
def restart_bot(port: int):
    """重启指定端口的Bot（从overlay配置推断）"""
    overlay_map = {
        9090: "/Users/luxiangnan/freqtrade/config_9090_overlay.json",
        9091: "/Users/luxiangnan/freqtrade/config_9091_overlay.json",
        9092: "/Users/luxiangnan/freqtrade/config_9092_overlay.json",
        9093: "/Users/luxiangnan/freqtrade/user_data_okx/config_okx_fixed.json",
        9094: "/Users/luxiangnan/freqtrade/config_9094_overlay.json",
        9095: "/Users/luxiangnan/freqtrade/config_9095_overlay.json",
        9096: "/Users/luxiangnan/freqtrade/config_9096_overlay.json",
        9097: "/Users/luxiangnan/freqtrade/config_9097_overlay.json",
    }
    overlay = overlay_map.get(port)
    if not overlay:
        log(f"未知端口 {port}，无法重启", "ERR")
        return False

    # 杀进程
    result = subprocess.run(["pkill", "-f", f"freqtrade.*{port}"], capture_output=True)
    time.sleep(3)

    # 重启
    cmd = [
        sys.executable,
        "/Users/luxiangnan/freqtrade/.venv/bin/freqtrade",
        "trade", "-c", "/Users/luxiangnan/freqtrade/config_shared.json",
        "-c", overlay
    ]
    log_path = f"/tmp/ft_{port}.log"
    with open(log_path, "w") as lf:
        proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT,
                               cwd="/Users/luxiangnan/freqtrade")
    log(f"Bot {port} 重启请求已提交 PID={proc.pid}", "OK")
    return True
```

### 2.4 状态追踪（防重复通知）

```python
# 文件顶部状态变量
prev_offline_bots = set()  # 上一轮已知的离线Bot

# 主循环中
current_offline = set(offline_bots)
new_offline = current_offline - prev_offline_bots
recovered = prev_offline_bots - current_offline

if new_offline:
    # 发送新离线通知（send_feishu_alert 内部已有 cooldown 防重复）

if recovered:
    # 发送恢复通知

prev_offline_bots = current_offline
```

---

## 三、通知模板

| 类型 | 标题 | 模板 |
|------|------|------|
| Bot掉线 | `🤖 Bot掉线: 9091` | red |
| Bot恢复 | `✅ Bot恢复` | green |
| 重启失败 | `🚨 Bot重启失败: 9091` | red |

---

## 四、预期效果

| 场景 | 增强前 | 增强后 |
|------|--------|--------|
| Bot掉线 | 仅日志，无通知 | 飞书立即告警 |
| Bot恢复 | 未知 | 自动发恢复通知 |
| Bot持续离线 | 无人知晓 | 每5分钟重发提醒（cooldown） |
| 自动恢复 | 无 | 尝试自动重启 |

---

## 五、不修改文件清单

- `port_scan.py`（独立巡检脚本）
- `bingbu_patrol.py`（兵部巡查播报）
- `monitor_sentiment.py`（兵部舆情）
- 其他六部脚本

---

*本提案由太子执行，执行后更新本文档状态。*
