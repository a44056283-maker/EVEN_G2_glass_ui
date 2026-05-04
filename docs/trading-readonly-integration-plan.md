# G2 Vision AI 交易系统只读集成方案

更新日期：2026-05-01

## 目标

把 G2 Vision AI 扩展成“视觉 + 语音 + 交易只读看板”：

1. 语音查看白名单币种实时价格。
2. 语音查看 12 个交易机器人的在线状态。
3. 语音查看机器人持仓、未实现盈亏、盈亏比、集中度风险。
4. 结合天禄记忆库和 V6.5/V6.6 规则做只读分析与风险提示。

硬边界：

1. G2 插件不下单。
2. G2 插件不平仓。
3. G2 插件不改仓位、不改止盈止损、不推送机器人命令。
4. G2 插件只调用只读接口，只输出状态、解释和风险提醒。

## 当前可用基础

项目当前已经具备：

1. MiniMax 文本问答：`/ask`
2. MiniMax TTS：`/tts`
3. 手机摄像头视觉识别：`/vision`
4. G2 麦克风 PCM 采集：`/transcribe` 已接入等待 MiniMax ASR 端点
5. 天禄记忆库只读检索：`/memory/search`
6. 远程记忆缓存：`data/remote-memory-cache`

从同步记忆中看到的交易系统线索：

1. 机器人端口：`8081-8084`、`9090-9097`
2. 控制台聚合端口：`9099`
3. 风控/事件总线端口：`7891`
4. 常见只读接口：
   - `/api/ports_status`
   - `/api/edict/bridge_status`
   - `/api/autopilot/status`
   - `/api/l5/market_intel?pair=all`
   - `/api/rules/v65/bots`
   - `/api/l5/backtest_orderbook_status`

这些接口需要现场二次确认，不能只依赖历史记忆直接上线。

## 推荐架构

```text
G2 / iPhone WebView
        |
        | 语音/文字问题
        v
G2 API Server
        |
        | /trading/overview
        | /trading/prices
        | /trading/bots
        | /trading/positions
        v
Trading Readonly Adapter
        |
        | 只读 HTTP / SSH / 本地缓存
        v
交易系统控制台 9099 / 风控 7891 / 机器人只读状态
```

## 后端新增模块

建议新增包：

```text
packages/trading-adapter/
```

负责：

1. 从环境变量读取交易系统只读地址。
2. 只允许 `GET`。
3. 只允许白名单 endpoint。
4. 对返回数据做脱敏和压缩。
5. 给 `/ask` 提供结构化上下文。

建议环境变量：

```text
TRADING_READONLY_ENABLED=false
TRADING_BASE_URL=http://192.168.13.48:9099
TRADING_RISK_BASE_URL=http://192.168.13.48:7891
TRADING_ALLOWED_SYMBOLS=BTC,ETH,SOL,BNB,DOGE
TRADING_CACHE_TTL_MS=5000
```

默认必须是 `false`，审核包和公开包不自动启用交易功能。

## API 设计

### 1. 总览

```text
GET /trading/overview
```

返回：

```json
{
  "enabled": true,
  "readOnly": true,
  "botsOnline": 12,
  "botsTotal": 12,
  "autopilotEnabled": false,
  "riskReady": false,
  "warnings": ["SOL/USDT 集中度偏高"],
  "updatedAt": "2026-05-01T18:30:00+08:00"
}
```

语音示例：

```text
天禄，交易系统现在正常吗？
```

### 2. 白名单价格

```text
GET /trading/prices
GET /trading/prices?symbols=BTC,ETH,SOL
```

返回：

```json
{
  "symbols": [
    {
      "symbol": "BTC",
      "price": 61234.5,
      "change24hPct": -1.2,
      "fundingRatePct": 0.0082,
      "source": "trading-system"
    }
  ],
  "updatedAt": "2026-05-01T18:30:00+08:00"
}
```

语音示例：

```text
天禄，看一下 BTC 和 SOL 现在价格。
```

### 3. 机器人状态

```text
GET /trading/bots
```

返回：

```json
{
  "summary": {
    "online": 12,
    "total": 12,
    "unhealthy": []
  },
  "bots": [
    {
      "port": 9090,
      "name": "bot-9090",
      "online": true,
      "exchange": "okx",
      "positions": 2,
      "unrealizedPnlPct": -0.8
    }
  ]
}
```

语音示例：

```text
天禄，所有机器人在线吗？
```

### 4. 持仓和盈亏

```text
GET /trading/positions
```

返回：

```json
{
  "summary": {
    "openPositions": 8,
    "avgUnrealizedPnlPct": -1.1,
    "worstSymbol": "SOL/USDT",
    "concentrationRisk": "high"
  },
  "positions": [
    {
      "bot": 9090,
      "symbol": "SOL/USDT",
      "side": "long",
      "entryPrice": 142.3,
      "markPrice": 140.8,
      "unrealizedPnlPct": -1.05,
      "leverage": 10
    }
  ]
}
```

语音示例：

```text
天禄，我现在持仓盈亏怎么样？
```

## `/ask` 智能路由

在 `/ask` 中增加交易意图识别：

```text
价格：价格、行情、BTC、ETH、SOL、涨跌
机器人：机器人、在线、端口、9090、9099
持仓：持仓、仓位、盈亏、PnL、浮盈、浮亏
风险：集中度、风险、预检、自动驾驶、V6.5
```

命中后流程：

1. 调用交易只读 adapter。
2. 取结构化数据。
3. 再交给 MiniMax M2.7 总结成 G2 小屏幕短回答。
4. 同时用 TTS 朗读。

示例回答：

```text
12 个机器人在线。
当前 8 个持仓，平均浮亏约 1.1%。
SOL 仓位集中度偏高，建议只做观察，不在 G2 执行操作。
```

## 审核策略

第一轮 Even 官方审核建议：

1. 保持交易功能默认关闭。
2. 商店描述只写“只读记忆检索”和“问答能力”。
3. 不在公开视频/截图里展示交易盈亏和账户信息。
4. 隐私和条款里保留“交易相关只读分析，不执行自动交易”的声明。

原因：

1. 金融交易功能会显著提高审核敏感度。
2. 当前语音、视觉、TTS、G2 显示还需要整体稳定性测试。
3. 交易系统涉及账户和仓位，先内部测试更稳。

内部测试包可以启用：

```text
TRADING_READONLY_ENABLED=true
```

公开审核包保持：

```text
TRADING_READONLY_ENABLED=false
```

## 分阶段落地

### 阶段 A：只读记忆增强

不接实时交易 API，只用当前 `data/remote-memory-cache`：

1. 支持问“V6.5 规则是什么”
2. 支持问“9090 最近有什么故障”
3. 支持问“12 个机器人仓位规则是否一致”

风险最低，已经基本具备。

### 阶段 B：接 9099 只读总览

新增：

1. `/trading/overview`
2. `/trading/bots`
3. `/trading/positions`

只读取 9099 聚合状态，不访问交易所密钥。

### 阶段 C：接白名单价格

新增：

1. `/trading/prices`
2. 白名单币种过滤
3. 5 秒缓存
4. 失败时返回最近一次缓存和数据时间

### 阶段 D：G2 语音联动

语音：

```text
天禄，看一下 BTC 价格
天禄，机器人在线吗
天禄，我现在盈亏怎么样
天禄，当前风险高不高
```

显示：

1. G2 只显示 3-4 行摘要。
2. 手机页面显示完整表格。
3. 历史记录保存查询摘要，不保存密钥和完整账户详情。

## 安全验收清单

上线前必须逐项确认：

1. 没有任何 `POST /order`、`POST /close`、`POST /trade`、`DELETE`、`PUT` 调用。
2. 交易网关只允许白名单 GET endpoint。
3. 所有返回数据脱敏，不展示 API Key、secret、cookie。
4. G2 前端不保存交易系统地址和密钥。
5. 后端日志不记录完整仓位明细中的敏感账户字段。
6. 交易相关回答必须带“只读/不执行”边界。
7. 公开审核包默认关闭实时交易功能。

