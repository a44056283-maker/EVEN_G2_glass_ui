# 兵部 · 运维与监控技能库

## 🔧 agent-autopilot (自动化工作流)

**来源**: edoserbia/agent-autopilot  
**用途**: 心跳驱动的自动化任务执行，日夜进度报告，长期记忆

### 核心功能

- 心跳驱动的任务执行
- 日/夜进度报告自动推送
- 长期记忆持久化
- 自我修复的错误恢复

### 兵部使用场景

1. **自动化巡检** - 替代现有cron定时巡检脚本
2. **故障自愈** - 监控Bot状态，异常自动重启
3. **日夜报告** - 自动向爸推送每日/夜间运行报告

### 配置建议

在 HEARTBEAT.md 中集成:
```markdown
### 兵部自动巡检
- Run `python3 ~/edict/scripts/bingbu_watchdog.py`
- Alert if any port 9090-9093 not responding
- Check bot positions for extreme leverage
- Send summary to Feishu if any P0/P1 issues
```

---

## 🐳 hyperliquid-analyzer (Hyperliquid市场监控)

**用途**: 实时价格监控、趋势分析、风险评估  
**无需API Key**

### 兵部使用场景

```bash
# 快速检查Hyperliquid各币种价格
curl -s https://api.hyperliquid.xyz/info -X POST \
  -H "Content-Type: application/json" \
  -d '{"type": "allMids"}' | jq '{BTC: .BTC, ETH: .ETH, SOL: .SOL}'

# 获取市场元数据
curl -s https://api.hyperliquid.xyz/info -X POST \
  -H "Content-Type: application/json" \
  -d '{"type": "metaAndAssetCtxs"}' | jq '.[0:4]'
```

### 兵部整合

兵部现有的 `bingbu_watchdog.py` 可整合此API获取实时市场数据，在极端行情时自动触发告警。

---

## 📊 兵部执行清单

- [x] hyperliquid-analyzer API: ✅ **已验证可用** (curl直接调用，无需安装)
  ```
  curl -s https://api.hyperliquid.xyz/info -X POST -H "Content-Type: application/json" \
    -d '{"type": "allMids"}' | jq '{BTC,ETH,SOL,HYPE}'
  ```
- [ ] agent-autopilot: ⚠️ 需要 `todo-management` skill 依赖，工部评估
- [ ] 将 hyperliquid-analyzer API 整合到 bingbu_watchdog.py
- [ ] 建立兵部自动化巡检标准流程
- [ ] 更新 bingbu_patrol.py 整合新的监控能力

---
*最后更新: 2026-03-30 by 天禄 | 状态: hyperliquid-analyzer已验证可用*
