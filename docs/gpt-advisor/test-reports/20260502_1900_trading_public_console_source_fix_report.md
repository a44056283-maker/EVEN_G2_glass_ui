# 交易状态公网数据源修复报告

时间：2026-05-02 19:00

## 本轮问题

用户反馈：语音问答中交易机器人持仓回答仍显示旧 mock 数据，例如 `mock-momentum`、持仓 `2` 个，与控制台真实数据不一致。

截图同时显示前端曾尝试访问：

```text
http://192.168.13.48:9099
```

该局域网地址在外出、手机公网、Even 插件公网环境下不可用，因此不应作为 G2 助手默认实时数据源。

## 修复内容

1. 将交易只读默认源改为公网控制台：

```text
https://console.tianlu2026.org
```

2. 更新 `.env`：

```text
TRADING_BASE_URL=https://console.tianlu2026.org
TRADING_BASE_URLS=https://console.tianlu2026.org
```

3. 更新 `packages/trading-adapter/src/index.ts` 默认交易源。

4. 更新 `services/api-server/src/server.ts`：

- 交易类问题不再走旧 `tradingBotAdapter` mock。
- `/ask` 交易意图直接读取 `getTradingReadonlyOverview()`。
- 回答中明确显示实时源、机器人在线数、持仓数量、交易对数量、名义仓位、浮盈亏、风险、持仓交易对、简短评测。
- 如果实时源不可用，不再伪造 mock 持仓，改为明确提示控制台接口不可用。

5. 移除交易页和交易问答中的备份记忆展示：

- `getTradingReadonlyOverview()` 不再检索 `edict_backup_* / real_report_*` 这类历史备份报告。
- `/trading/overview` 返回 `memoryHits: []`。
- 前端交易状态页不再渲染备份报告路径。
- 交易历史不再把 `memoryHits` 写入详情。

## 验证结果

本机交易概览：

```text
GET http://127.0.0.1:8787/trading/overview
```

返回摘要：

```text
baseUrl: https://console.tianlu2026.org
portsOnline: 12 / 12
openPositions: 28
pairCount: 5
totalNotional: 22757.55
totalUnrealizedPnl: -40.32
riskLevel: normal
memoryHits: 0
has_backup: false
```

本机问答：

```text
POST http://127.0.0.1:8787/ask
```

公网问答：

```text
POST https://g2-vision.tianlu2026.org/ask
```

均返回：

```text
provider: local:trading-live-readonly
实时源：https://console.tianlu2026.org
持仓：28 个，交易对：5 个
```

不再返回：

```text
mock-momentum
持仓：2 个
来源：mock
edict_backup_*
real_report_*
```

## 当前口径说明

当前公网 API 实时返回 `openPositions=28`。如果控制台页面人工查看为 `29`，需要继续核对控制台页面与 API 字段的刷新延迟或统计口径。

## 验证命令

```bash
npm run typecheck
npm run build
npm run pack:g2
```

结果：均已通过。

## EHPK

```text
apps/evenhub-plugin/g2-vision-voice-assistant.ehpk
```

SHA256：

```text
f448c18bafe2d8de06347bf0107377a074ba39dbea9b8eabb7c0411a3e66ea0c
```

## 后续

1. 前端交易状态页需要刷新后确认不再展示局域网 `192.168.13.48:9099`。
2. 若前端仍显示旧局域网失败信息，需要清理浏览器缓存或旧 localStorage。
3. 继续核对 `openPositions=28/29` 的控制台页面与 API 口径。
