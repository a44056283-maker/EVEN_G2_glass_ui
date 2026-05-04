# 交易状态公网实时控制台升级测试报告

时间：2026-05-02 20:13

## 本轮目标

把眼镜软件的交易状态从旧的本地/备份记忆读取，切换为公网 9099 控制台只读实时数据源：

```text
https://console.tianlu2026.org
```

本轮只做只读数据展示和聚合，不实现任何交易动作。

## 修改范围

- `packages/shared/src/index.ts`
- `packages/trading-adapter/src/index.ts`
- `services/api-server/src/server.ts`
- `apps/evenhub-plugin/index.html`
- `apps/evenhub-plugin/src/main.ts`
- `apps/evenhub-plugin/src/history.ts`
- `docs/gpt-advisor/handoffs/20260502_1941_macb_original_trading_files_read_report.md`

## 数据源

当前交易只读数据源：

```text
https://console.tianlu2026.org
```

已接入的只读接口：

- `GET /health`
- `GET /api/ports_status`
- `GET /api/prices/realtime`
- `GET /api/dashboard/positions`
- `GET /api/monitor/positions`
- `GET /api/l5/fund_flow_v2`
- `GET /api/l5/daily_attribution?hours=24`

已明确移除/降级：

- 不再把 `192.168.13.48:9099` 作为前端实时读取源。
- 不再把 `edict_backup`、`real_report_*`、`MEMORY.md`、`daily-evolution` 等备份/记忆路径展示为交易状态数据。
- 历史记录详情增加清洗逻辑，隐藏旧记录里的备份路径噪声。

## 新增眼镜聚合接口

后端新增只读聚合接口：

- `GET /glasses/api/summary`
- `GET /glasses/api/prices`
- `GET /glasses/api/positions`
- `GET /glasses/api/l5`
- `GET /glasses/api/pair/:pair`
- `GET /glasses/api/alerts`

这些接口只返回适合眼镜端展示的小 JSON，并带有：

```text
ok / ts / source / stale
```

## 前端交易页分类

交易状态页现在按子模块展示：

1. 交易数据源
2. 白名单实时价格
3. 机器人在线
4. 整体持仓评测
5. 真实持仓交易对
6. M1-M5 / L5 资金流
7. 真实订单归因

眼镜/网页书签动作调整为：

- 刷新状态
- 白名单价格
- 持仓评测
- L5资金流

## 当前接口测试结果

### `/glasses/api/summary`

测试命令：

```bash
curl -sS http://127.0.0.1:8787/glasses/api/summary
```

返回摘要：

```json
{
  "ok": true,
  "source": "https://console.tianlu2026.org",
  "console": {"health": "healthy"},
  "bots": {"online": 12, "total": 12, "macA": "8/8", "macB": "4/4"},
  "portfolio": {"positions": 31, "notional": 25490.727751689996, "unrealizedPnl": -46.32580809},
  "prices": {
    "BNB/USDT": 615.8,
    "BTC/USDT": 78147.2,
    "DOGE/USDT": 0.10755,
    "ETH/USDT": 2302.34,
    "SOL/USDT": 83.81
  },
  "risk": {"level": "normal", "score": 22.6}
}
```

说明：持仓数量来自实时接口，随控制台实时变化。

### `/glasses/api/l5`

测试命令：

```bash
curl -sS http://127.0.0.1:8787/glasses/api/l5
```

返回摘要：

```json
{
  "ok": true,
  "source": "https://console.tianlu2026.org",
  "fundFlow": {
    "source": "/api/l5/fund_flow_v2",
    "pairCount": 5,
    "summary": "BNB/USDT outflow 置信65.05；BTC/USDT outflow 置信68.09；DOGE/USDT inflow 置信53.78；ETH/USDT inflow 置信64.43；SOL/USDT inflow 置信58.13"
  },
  "attribution": {
    "source": "/api/l5/daily_attribution?hours=24",
    "sampleCount": 1286,
    "winRatePct": 32.11,
    "avgRealizedPnlPct": -0.9341,
    "avgUnrealizedPnlPct": 0.5221
  }
}
```

## 构建验证

已执行：

```bash
npm run typecheck
npm run build
npm run pack:g2
```

结果：通过。

## EHPK

```text
apps/evenhub-plugin/g2-vision-voice-assistant.ehpk
```

SHA256：

```text
e41804b4f054a13f7cd72cdc64ebcd59370f2a3afd940edd321c74951a70dba2
```

## 未解决问题

1. 需要用户在 Even App / G2 真机中刷新确认交易页显示是否已经不再出现旧备份路径。
2. R1 电量仍未稳定读取，疑似 SDK 未直接暴露 R1 battery 或字段未命中。
3. 交易状态的朗读文案还可继续压缩成更适合 G2 的 5-8 行摘要。

## 下一步建议

1. 真机安装/刷新最新 EHPK，确认交易状态页读取公网控制台。
2. 若交易页仍有旧备份路径，先清空前端历史记录或继续扩大 `history.ts` 清洗规则。
3. 下一轮优化“交易状态眼镜端分页”：第一页总览，第二页白名单价格，第三页持仓评测，第四页 L5/归因。
