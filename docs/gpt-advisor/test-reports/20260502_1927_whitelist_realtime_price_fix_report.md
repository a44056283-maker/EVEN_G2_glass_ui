# 2026-05-02 19:27 白名单实时价格修复报告

## 本轮目标

修复“获取实时白名单交易对实时价格存在问题”：

- 白名单价格只读取配置白名单 `TRADING_ALLOWED_SYMBOLS=BTC,ETH,SOL,BNB,DOGE`。
- 不再把持仓交易对混入白名单价格。
- 不再优先使用 `M4-disk_cache` 旧价。
- 交易公网源固定为 `https://console.tianlu2026.org`。

## 修改文件

- `packages/trading-adapter/src/index.ts`
- `packages/shared/src/index.ts`
- `apps/evenhub-plugin/src/main.ts`
- `services/api-server/src/server.ts`
- `.env.example`

## 修复内容

1. `buildWhitelistPrices()` 只接收白名单币种，不再合并持仓币种。
2. 新增 M1-M5 价格候选筛选逻辑：
   - 优先 M2 `m2_triple_exchange`。
   - 其次 M3/M5/M1。
   - M4 `disk_cache` 降级为旧价来源，不再抢占实时价。
3. 白名单价格输出新增：
   - `sourceLayer`
   - `freshness`
   - `status`
   - `updatedAt`
4. 交易问答回答中加入白名单价与来源层级。
5. 手机网页交易卡片显示白名单价来源与时间。
6. `.env.example` 交易源改为公网控制台域名，避免新环境默认写回局域网 `192.168.13.48:9099`。

## 验证结果

`GET http://127.0.0.1:8787/trading/overview`

```text
baseUrl=https://console.tianlu2026.org
openPositions=28
pairCount=5
whitelist_count=5
memoryHits=0
```

白名单实时价格：

```text
BNB  615.30   M2-m2_triple_exchange
BTC  78262.0  M2-m2_triple_exchange
DOGE 0.10770  M2-m2_triple_exchange
ETH  2303.9   M2-m2_triple_exchange
SOL  83.98    M2-m2_triple_exchange
```

`POST /ask {"text":"查看白名单交易对的实时价格"}`

```text
实时源：https://console.tianlu2026.org
白名单价：BNB 615.30(m2)；BTC 78262.0(m2)；DOGE 0.10770(m2)；ETH 2303.9(m2)；SOL 83.98(m2)
机器人：12 / 12 在线，自动驾驶开启
持仓：28 个，交易对：5 个
```

## 命令结果

```text
npm run typecheck 通过
npm run build     通过
npm run pack:g2   通过
```

## EHPK

```text
apps/evenhub-plugin/g2-vision-voice-assistant.ehpk
SHA256: ce7fe2e77a0c060d2d12da8c1363bc01a3c37347275b0cd1d5a607a0616c8052
```

## 当前结论

白名单实时价格已改为公网控制台 M2 实时行情来源。前端不应再显示备份报告路径、局域网 `192.168.13.48:9099 fetch failed`，也不应把 DOT 持仓价混入白名单价格。

## 后续建议

1. 真机刷新插件，确认交易只读卡片显示 5 个白名单币种。
2. 若控制台未来新增 DOT 白名单，需要把 `TRADING_ALLOWED_SYMBOLS` 明确加入 DOT，并确保 `/api/v1/ai_data_flow` 返回 DOT 的 M2/M3 数据。
3. 继续修复语音问答中交易问题答非所问的问题，确保所有交易问答走 `local:trading-live-readonly`。
