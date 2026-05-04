# MacB 原始交易系统文件读取报告

生成时间：2026-05-02 19:41  
读取目标：`192.168.13.48` / `TianLu-Mac`  
范围：只读原始源码、运行进程、脱敏配置与实时接口结构。未修改电脑 B 文件。

## 结论

G2 软件读取交易状态时，不应再读取 `edict_backup_*`、`real_report_202604xx.json` 等历史备份日报作为实时交易数据。

实时交易数据的真实源头应以电脑 B 正在运行的 9099 控制台为准：

- 公域：`https://console.tianlu2026.org`
- 内网：`http://192.168.13.48:9099`
- 本机：`http://127.0.0.1:9099`

G2 软件应优先读取这些实时接口：

1. `/api/dashboard/positions`：所有机器人端口、持仓、余额、利润聚合。
2. `/api/hero_cards/exit_ai_status`：出山 AI 持仓评测，当前能看到 28 个持仓。
3. `/api/prices/realtime`：白名单实时价格，Gate 直连代理。
4. `/api/v1/central_data`：M1-M5/M1-M4 统一实时数据流。
5. `/api/v1/ai_data_flow`：AI 数据流缓存。
6. `/api/hero_cards/bot_summary`：12 个机器人在线汇总。

## 正在运行的原始进程

### 9099 总控制台

进程：

- `console_server.py`
- 目录：`/Users/luxiangnan/freqtrade_console`
- 命令：`Python console_server.py`

原始文件：

- `/Users/luxiangnan/freqtrade_console/console_server.py`

这是主控制台，包含 9099 页面、实时接口、机器人聚合、天眼 AI、出山 AI、M1-M5 数据流、价格接口、持仓接口。

### 机器人执行器

进程：

- `bot_agent_generic.py --port 9090...9097`
- `bot_agent_generic.py --port 8081...8084`

原始文件：

- `/Users/luxiangnan/freqtrade_console/bot_agents/bot_agent_generic.py`
- `/Users/luxiangnan/freqtrade_console/bot_agents/base_agent.py`

职责：

- 每 60 秒抓取机器人信号和持仓，上报 9099。
- 监听 `port + 100` 的命令接收端口。
- Bot 自身不做 AI 决策，执行器只接收 9099 下发命令并回报。

关键源码说明：

```text
Bot 职责：
1. 每 60 秒：心跳上报（信号 + 持仓）→ 9099
2. 监听 port+100：接收 9099 命令 → 执行 → 回调
3. 定期向 9099 注册（报告 cmd_port）
```

### Freqtrade 真实机器人

目录：

- `/Users/luxiangnan/freqtrade`

运行命令模式：

```text
freqtrade trade -c config_shared.json -c config_909x_overlay.json --userdir ... -s FOttStrategy
```

策略文件：

- `/Users/luxiangnan/freqtrade/strategies/FOttStrategy.py`

策略性质：

```text
FOttStrategy V99 - 纯 API 对接层
V6.5 AutoPilot 全权管理所有交易规则。
本文件仅负责 freqtrade 框架接口，不产生任何入场/出场信号。
```

也就是说，策略层不产生交易信号，真正的入场、出场、风险评测由 9099 / V6.5 / 天眼 / 出山链路控制。

## 配置文件结构

### 共享配置

文件：

- `/Users/luxiangnan/freqtrade/config_shared.json`

脱敏摘要：

- `strategy`: `FOttStrategy`
- `dry_run`: `False`
- `trading_mode`: `futures`
- `margin_mode`: `isolated`
- `stake_currency`: `USDT`
- `stake_amount`: `unlimited`
- `max_open_trades`: `14`

### 端口 overlay 配置

文件：

- `config_9090_overlay.json` 到 `config_9097_overlay.json`
- `config_9098_overlay.json`
- `config_9099_overlay.json`

脱敏摘要：

- 9090-9092：`gateio`
- 9093-9097：`okx`
- 9099 overlay：`gateio`
- 每个主要端口白名单均为 5 个：
  - `BTC/USDT:USDT`
  - `ETH/USDT:USDT`
  - `SOL/USDT:USDT`
  - `BNB/USDT:USDT`
  - `DOGE/USDT:USDT`
- 黑名单约 33 个。
- API Server 端口对应 9090-9097。

敏感字段如密码、token、jwt、secret 已脱敏，不写入本报告。

## 9099 原始实时接口

### `/api/ports_status`

源码函数：

- `api_ports_status`

作用：

- 并行检测所有端口 `/api/v1/ping`。
- 返回每个机器人端口在线/离线。

端口范围：

```text
9090-9097 + 8081-8084
```

### `/api/dashboard/positions`

源码函数：

- `api_dashboard`
- `api_dashboard_positions`

作用：

- 聚合所有端口：
  - `/api/v1/status`
  - `/api/v1/balance`
  - `/api/v1/profit`
  - `/api/v1/autopilot/status`
- 汇总：
  - `total_balance`
  - `total_profit`
  - `active_ports`
  - `total_positions`
  - `open_trades`
  - `ports`
  - `positions`

实测结果：

- `active_ports`: 12
- `total_positions`: 28
- `open_trades`: 28
- 返回体约 173 KB，是真实实时持仓数据源。

G2 交易状态和语音问答中关于“当前持仓多少个”的回答应优先使用这里，而不是 mock 或备份日报。

### `/api/prices/realtime`

源码函数：

- `api_prices_realtime`

作用：

- 服务端代理 Gate.io 实时价格，绕过前端 CORS。
- 目前固定 5 个白名单：
  - BTC
  - ETH
  - SOL
  - BNB
  - DOGE

实测结果：

```text
BNB 615.0
BTC 78157.1
DOGE 0.1076
ETH 2301.6
SOL 83.69
```

G2 白名单实时价格应优先使用该接口；若未来要支持更多交易对，需要先扩展 9099 的 `PAIRS_MAP` 或改为读取配置白名单动态生成。

### `/api/v1/ai_data_flow`

源码函数：

- `api_ai_data_flow`
- `_get_m1_m4_data_flow_cached`

作用：

- M1-M4/M1-M5 AI 数据流缓存。
- 默认 pairs：
  - `btc,eth,sol,doge,bnb`
- 缓存 TTL：默认 45 秒。
- 返回 `pairs`、`cache_health`、`execution_policy`、`data_flow_cache` 等。

### `/api/v1/central_data`

源码函数：

- `api_central_data`

作用：

- 统一数据中枢。
- 用于 12 个机器人首选数据源。
- 包含：
  - M1 资金流
  - M2 支撑阻力
  - M3 巨量 K
  - M4 RSI/ATR/OI
  - L5/M5 微结构
  - 自动驾驶参数
  - 天眼/出山评测语音文案

源码注释明确：

```text
所有12个交易机器人(9090-9097 + 8081-8084)首选数据源
自动驾驶模块直接读取，无需单独采集
天眼AI / 出山AI 实时评测数据基础
```

### `/api/hero_cards/tianyan_status`

源码函数：

- `api_hero_tianyan_status`

作用：

- 天眼入场/早期持仓审计。
- 只展示有实际持仓的交易对。
- 规则里超过 180 分钟持仓会交给出山 AI。

实测：

- `active_count`: 0
- `handoff_count`: 28
- 原因：当前 28 个持仓均超过 `holding_min > 180m`，交给出山 AI。

### `/api/hero_cards/exit_ai_status`

源码函数：

- `api_hero_exit_ai_status`

作用：

- 出山 AI 持仓评测。
- 当前真实持仓评测主入口。

实测：

- `active_count`: 28
- 返回体约 1.37 MB。
- 包含每个持仓的 PnL、入场价、当前价、M1-M5 数据、出山判断、风险判断。

G2 的“整体持仓评测分析”应主要使用该接口，而不是历史日报。

### `/api/hero_cards/bot_summary`

源码函数：

- `api_hero_bot_summary`

实测：

- 12 个机器人在线。
- 端口：
  - 8081-8084
  - 9090-9097

## G2 软件当前应修正的数据源策略

### 禁止作为实时交易主源

以下内容只能作为历史记录、记忆、备份、审计，不得显示在“交易只读实时状态”的主卡片里：

- `knowledge-strategy/edict_backup_*/edict/data/reports/daily/real_report_*.json`
- `每日进化日志`
- `codex-memories/MEMORY.md`
- `Task Group` 类记忆索引

这些就是用户看到的“备份路径刷屏”的来源，应从交易实时 UI 中剔除。

### 交易实时状态建议读取顺序

1. `https://console.tianlu2026.org/api/dashboard/positions`
   - 真实端口、真实持仓、总持仓数量。
2. `https://console.tianlu2026.org/api/hero_cards/exit_ai_status`
   - 当前 28 个持仓的出山 AI 评测。
3. `https://console.tianlu2026.org/api/prices/realtime`
   - 白名单实时价格。
4. `https://console.tianlu2026.org/api/v1/central_data`
   - M1-M5 细分数据流。
5. `https://console.tianlu2026.org/api/hero_cards/bot_summary`
   - 12 个机器人在线概况。

## 对 G2 项目的直接改造建议

1. `trading-adapter` 不应再把 memory/backup report 当作实时交易 fallback。
2. 如果 `console.tianlu2026.org` 可用但某个接口失败，应显示“实时接口异常”，不要自动切换成备份日报。
3. “持仓交易对”应来自 `/api/dashboard/positions.positions` 或 `/api/hero_cards/exit_ai_status.position_evals`。
4. “整体持仓评测”应来自 `/api/hero_cards/exit_ai_status`，并提炼：
   - 总持仓数
   - 盈利持仓数
   - 浮盈/浮亏
   - 最高集中交易对
   - 急迫风险数
   - 出山 AI 建议摘要
5. “白名单实时价格”应来自 `/api/prices/realtime` 或 `/api/v1/central_data.pairs[*].price`，优先 `prices/realtime`。
6. 语音问答中询问“现在持仓是多少”“交易机器人运行如何”时，应返回实时接口结果，不应返回 mock。

## 已确认的实时状态快照

读取时间：2026-05-02 19:41 左右。

- 控制台：9099 在线。
- Bot：12 个在线。
- 总持仓：28。
- 天眼当前 active_count：0。
- 出山 AI 当前 active_count：28。
- 白名单价格接口正常。
- 备份日报不是实时主数据源。

