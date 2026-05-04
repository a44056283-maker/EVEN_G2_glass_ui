# 20260502 交易六项摘要与 AI 评测升级报告

## 本轮目标

用户反馈交易机器人内容很多，交易状态不应只总结三项。本轮将交易只读概览升级为：

- 至少 6 项交易摘要。
- 下方增加 MiniMax 或本地规则 AI 评测。
- 前端交易页显示六项摘要、AI 评测、建议和来源。
- 继续使用公网控制台 `https://console.tianlu2026.org`，不使用局域网 9099 或备份报告路径。

## 修改文件

- `packages/shared/src/index.ts`
- `packages/trading-adapter/src/index.ts`
- `services/api-server/src/server.ts`
- `apps/evenhub-plugin/src/main.ts`
- `apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`

## 实现内容

1. `TradingReadonlyOverview.aiAssessment` 新增：
   - `provider`
   - `summary`
   - `suggestions`
   - `summaryPoints`
   - `source`
   - `createdAt`

2. `trading-adapter` 新增本地六项摘要：
   - 持仓规模
   - 组合盈亏
   - 风险评分
   - 集中度
   - 主要交易对
   - L5 资金流
   - 订单归因

3. API 层新增 `enrichTradingOverviewWithAi()`：
   - 优先调用 MiniMax-M2.7 生成只读交易评测。
   - MiniMax 超时或失败时，自动保留 `local-rule-v1` 本地规则评测。
   - 不执行任何交易动作。

4. 手机/插件交易页新增 AI 评测卡片：
   - 显示“六项摘要”。
   - 显示 `MiniMax-M2.7 持仓评测` 或本地评测。
   - 显示建议与来源。

## 验证结果

### `/trading/overview`

返回摘要：

```json
{
  "positions": 31,
  "provider": "MiniMax-M2.7",
  "aiSource": "minimax-realtime-trading-assessment",
  "summaryPoints": 7
}
```

六项以上摘要示例：

```text
持仓规模：31 个，名义 25490.73。
组合盈亏：当前浮盈亏 -49.98。
风险评分：normal 23 分。
集中度：BNB/USDT 39.5%，仓位 10063.99。
主要交易对：BNB/USDT / ETH/USDT / BTC/USDT / SOL/USDT / DOT/USDT。
L5资金流：BNB/USDT outflow 置信65.05；BTC/USDT outflow 置信68.09；DOGE/USDT inflow 置信53.78；ETH/USDT inflow 置信64.43；SOL/USDT inflow 置信58.13。
订单归因：样本 1259，胜率 32.11%。
```

MiniMax 评测示例：

```text
实时短评：机器人全在线无异常，持仓31个浮亏49刀，风险评分23属正常区间。BNB集中度39.5%偏高，BTC资金流出信号较强。胜率仅32.1%，已实现亏损-0.93%，建议关注BTC仓位动向。
```

### `/glasses/api/summary`

返回摘要：

```json
{
  "ok": true,
  "source": "https://console.tianlu2026.org",
  "stale": false,
  "positions": 31,
  "provider": "MiniMax-M2.7",
  "summaryPoints": 7
}
```

眼镜聚合接口已包含 `aiAssessment`，前端可直接显示六项摘要和评测。

## 构建与打包

命令：

```bash
npm run typecheck
npm run build
npm run pack:g2
```

结果：

```text
全部通过
```

EHPK：

```text
apps/evenhub-plugin/g2-vision-voice-assistant.ehpk
```

SHA256：

```text
39f48b4e6aa76712c09dbab5a48ea99e9a8db2ce499ab2c38df35ac79d9aa47c
```

## 未解决问题

- 真机端需刷新确认交易页新增的 AI 评测卡片是否显示完整。
- R1 电量仍可能显示 `--`，属于 SDK/设备信息读取专项问题。
- 语音问答若询问交易状态，仍需确认前端问题路由使用最新 `/trading/overview` 结果。

## 下一步建议

1. 真机刷新交易状态页，确认显示：
   - 六项摘要
   - MiniMax-M2.7 持仓评测
   - 建议
   - 公网数据源
2. 将语音“交易状态/持仓/收益”回答统一改为复用同一套 `aiAssessment`。
3. 单独修复 R1 电量读取与显示。
