# 三套系统分工与AI唯一执行权_实施记录

更新时间: 2026-04-27 18:08

## 一、最终权限边界

三套系统可以并行采集、并行评分、并行展示，但不能并行下单。

| 系统 | 主要职责 | 是否允许直接下单 | 是否允许直接出场 |
| --- | --- | --- | --- |
| 天眼AI + 出山AI自动驾驶 | 天眼AI负责入场决策；出山AI负责出场、止盈、止损决策 | 是，天眼AI唯一入场授权 | 是，出山AI唯一出场授权 |
| M1-M4场景AI英雄卡 | 统一采集、缓存、交叉验证、生成实时AI话术 | 否 | 否 |
| 12个交易机器人固定规则系统 | 读取M1-M4数据流，作为执行容器和备用本地数据源 | 否，AI模式下不自主入场 | 否，AI模式下不自主出场 |

统一规则:

```text
所有采集数据先汇总为M1-M4数据流，再交由天眼AI入场、出山AI出场；机器人不抢决策权。
```

## 二、已实施代码

### 1. 9099统一AI数据流

文件:

- `/Users/luxiangnan/freqtrade_console/console_server.py`

新增/修复:

- 新增 `/api/v1/ai_data_flow`
- 修复 `/api/v1/central_data`
- 修复 `/api/v1/bot_feed`
- 新增统一执行权结构 `_AI_EXECUTION_AUTHORITY`
- M1-M4统一为 `15m_primary_with_1h_4h_confirmation`
- M1-M4输出统一包含:
  - `m1`
  - `m2`
  - `m3`
  - `m4`
  - `narrative.tianyan_entry`
  - `narrative.chushan_exit`
  - `execution_policy`
- `central_data.autopilot` 只产生AI建议，不直接授予下单权限。

### 2. 出山AI M4数据结构兼容

修复:

- 出山AI提示词构建兼容 `m4_data["rsi"]` 为 float 的情况
- 同时兼容 `rsi_values / rsi_15m / rsi_1h / rsi_4h`
- 避免 `AttributeError: 'float' object has no attribute 'get'`

### 3. 机器人侧M1-M4订阅

文件:

- `/Users/luxiangnan/freqtrade/freqtrade/rpc/api_server/api_autopilot.py`
- `/Users/luxiangnan/freqtrade/.venv311/lib/python3.11/site-packages/freqtrade/rpc/api_server/api_autopilot.py`
- MacB:
  - `/Users/luxiangnan/freqtrade/freqtrade/rpc/api_server/api_autopilot.py`
  - `/Users/luxiangnan/freqtrade/.venv/lib/python3.11/site-packages/freqtrade/rpc/api_server/api_autopilot.py`

新增/修复:

- 新增M1-M4数据流订阅函数 `_fetch_m1_m4_flow_for_pairs`
- 支持环境变量:
  - `TIANLU_M1M4_FLOW_URLS`
  - `TIANLU_M1M4_FEED_URLS`
  - `TIANLU_M1M4_FEED_URL`
- 默认订阅:
  - `http://127.0.0.1:9099/api/v1/ai_data_flow`
  - `http://192.168.13.104:9099/api/v1/ai_data_flow`
- 自动驾驶循环中记录 `m1_m4_feed`
- `/api/v1/autopilot/status` 返回:
  - `ai_execution_authority`
  - `m1_m4_feed`
- 机器人端策略保持:
  - `robot_direct_entry = false`
  - `robot_direct_exit = false`

补充修复:

- 已同步源码副本和实际运行的 venv/site-packages 副本，避免机器人启动时加载旧 API。
- MacB 进程环境 `PYTHONPATH=/Users/luxiangnan/freqtrade`，因此必须同步 MacB 源码目录副本，否则 8081-8084 会继续返回旧状态字段。

### 3.1 12机器人管理脚本

文件:

- `/Users/luxiangnan/freqtrade/bot_manager.sh`

新增/修复:

- 机器人总数修正为 12 个:
  - MacA: 9090-9097
  - MacB: 8081-8084
- `status/start/stop/restart/restart-all/cleanup` 支持远程 MacB。
- MacA 使用 launchd submit 方式启动，减少终端退出后进程被带掉的问题。
- MacB 四个机器人使用远程 launchd submit 启动。
- 状态统计现在按 12 个机器人汇总。

### 3.2 9099数据流缓存与超时修复

文件:

- `/Users/luxiangnan/freqtrade_console/console_server.py`

新增/修复:

- `/api/v1/ai_data_flow` 改为缓存优先、后台刷新。
- `/api/v1/central_data` 和 `/api/v1/bot_feed` 同样读取缓存层。
- 首次请求无缓存时立即返回 15M 对齐的 warming 占位结构，后台补齐真实 M1/M2/M3/M4。
- 有旧缓存时先返回 stale 数据并后台刷新，避免 12 个机器人同时请求导致 9099 阻塞。
- 缓存状态通过 `data_flow_cache` 返回:
  - `state`
  - `age_sec`
  - `refreshing`
  - `ttl_sec`

### 3.3 M1量基线与机器人口径对齐

问题:

- 交易机器人量基线/倍数正确，M1量基线/倍数偏低，导致天眼AI长期读到 0.x/1.x 的错误量比。
- 根因不是安静期公式，而是 M1 拉 K 线时使用本机时间计算 `since=now-24h`。
- 当前机器时间领先交易所最新K线窗口时，M1会拿到错位旧窗口；机器人侧使用 `limit` 拉最近N根，不依赖本机时间，因此机器人倍数正确。
- M1 Gate 采集还存在 Gate 默认类型偏向现货的风险，需强制和机器人一致读取永续 swap。

修复:

- 文件: `/Users/luxiangnan/freqtrade_console/api_m1.py`
- Gate `defaultType` 改为 `swap`，和机器人 `_get_ccxt_with_auth()` 对齐。
- OKX/Binance/Gate 均改为按 `limit` 拉最近K线，不再传本机时间计算的 `since`。
- M1 K线窗口改为 `96 + 5 = 101`，和机器人 `_BASELINE_CANDLES + 5` 对齐。
- 清理 M1 本地与外挂盘旧 OHLCV 缓存后重算并写入 `m1_scan_results`。

验证样例:

```text
BTC  M1综合量比 6.687x  Gate 6.340x  OKX 5.093x  BNB 8.629x
SOL  M1综合量比 3.546x  Gate 4.118x  OKX 3.592x  BNB 2.927x
BNB  M1综合量比 4.391x  Gate 3.854x  OKX 5.673x  BNB 3.645x
DOGE M1综合量比 3.723x  Gate 3.844x  OKX 4.234x  BNB 3.091x
ETH  M1综合量比 3.258x  Gate 3.813x  OKX 2.807x  BNB 3.153x
```

结论:

- M1现在使用交易机器人同一类“安静期基线 + 最近已收盘K线倍数”口径。
- M1不会再因为本机时间偏移拿到错误旧窗口，从而把真实放量压成低倍数。

### 3.4 机器人S/R改为M2三所交叉验证口径

问题:

- 机器人内部原有 `_get_sr_data()` 会自行拉K线并调用本地 `SupportResistanceEngine`。
- 这会导致 M2 英雄卡/天眼/出山看到的是一套三所交叉S/R，而机器人执行过滤又用另一套本地S/R。
- 本地S/R没有统一使用 M2 的 Gate+OKX+Binance 三所交叉验证结果，容易出现支撑/压力线错位。

修复:

- 文件:
  - `/Users/luxiangnan/freqtrade/freqtrade/rpc/api_server/api_autopilot.py`
  - `/Users/luxiangnan/freqtrade/.venv311/lib/python3.11/site-packages/freqtrade/rpc/api_server/api_autopilot.py`
  - MacB 同步到源码目录和 venv/site-packages。
- 机器人 `_get_sr_data()` 默认优先读取 9099:
  - `/api/bt2/sr_levels/<pair>`
- 新增 M2 转机器人适配:
  - `nearest_support / nearest_resistance`
  - `supports / resistances`
  - `dual_validated_count / triple_validated_count`
  - `validated_by / cross_validation_count`
  - 转换为机器人需要的 `sr_price / sr_type / sr_touches / sl_distance_pct`。
- 默认要求 M2 S/R 至少双所交叉验证；未达双验时机器人不使用本地S/R替代。
- 旧本地 `SupportResistanceEngine` 默认关闭，只能通过 `TIANLU_ALLOW_LOCAL_SR_BACKUP=1` 显式开启。

同时修复 M2 自身数据源:

- 文件: `/Users/luxiangnan/freqtrade_console/bt_tools/backtest_core/m2_sr_enhanced.py`
- Gate ccxt fallback 默认类型改为 `swap`。
- Binance K线和价格接口改为 USDT-M 永续:
  - `/fapi/v1/klines`
  - `/fapi/v1/ticker/price`
- 清理 M2 旧 S/R 缓存后重新生成三所交叉结果。

验证样例:

```text
BTC  S=77842.0  R=79453.0  双验=35  三验=16
ETH  S=2310.2   R=2464.0   双验=50  三验=26
SOL  S=85.0     R=97.64    双验=42  三验=25
BNB  S=627.8    R=687.5    双验=43  三验=24
DOGE S=0.0981   R=0.1175   双验=38  三验=19
```

运行验收:

- 12/12 机器人重启完成。
- 12/12 机器人继续接入 9099 M1-M4 数据流。
- MacA 和 MacB 日志均出现 `M2 S/R`，且每条日志带双验/三验计数。
- 机器人日志未再使用默认本地S/R作为主数据。

### 4. 英雄卡UI统一接入

文件:

- `/Users/luxiangnan/freqtrade_console/static/tabs/hero-cards.html`
- `/Users/luxiangnan/freqtrade_console/static/tabs/tianyan-ai.html`
- `/Users/luxiangnan/freqtrade_console/static/tabs/exit-ai.html`

新增/修复:

- 三个页面均优先读取 `/api/v1/ai_data_flow?pairs=btc,eth,sol,doge,bnb`
- 英雄卡统一显示 `15M主线`
- 同一卡片内展示 M1/M2/M3/M4 数据，不再只显示旧市场字段
- DOGE等低价币价格按四位小数展示
- 无持仓时仍展示实时 M1-M4 话术，而不是空白
- 出山/天眼卡片的实时话术来源改为统一数据流中的:
  - `narrative.tianyan_entry`
  - `narrative.chushan_exit`

## 三、验证结果

已通过:

```bash
python3 -m py_compile /Users/luxiangnan/freqtrade_console/console_server.py
python3 -m py_compile /Users/luxiangnan/freqtrade/freqtrade/rpc/api_server/api_autopilot.py
python3 -m py_compile /Users/luxiangnan/freqtrade/.venv311/lib/python3.11/site-packages/freqtrade/rpc/api_server/api_autopilot.py
node --check static/tabs/hero-cards.html 中的脚本
node --check static/tabs/tianyan-ai.html 中的脚本
node --check static/tabs/exit-ai.html 中的脚本
```

9099已重启并验证:

```bash
GET /api/v1/ai_data_flow?pairs=btc,eth,sol,doge,bnb
GET /api/v1/central_data?pairs=btc,eth,sol,doge,bnb
GET /api/v1/bot_feed?port=9090&pair=DOGE/USDT
```

验证结果:

- HTTP 200
- `/api/v1/ai_data_flow` 返回时间已从超时改为毫秒级缓存返回
- `data_flow_cache.state = fresh`
- M1-M4 `cache_health` 五个白名单币对全部 available
- `fallback_count = 0`
- DOGE价格按四位小数返回，例如 `0.0985`
- `bot_feed.direct_order_permission = false`
- `execution_policy.order_permission.robot_fixed_rules = false`
- `execution_policy.order_permission.tianyan_ai = true`
- `execution_policy.order_permission.chushan_ai = true`

### 12机器人运行验收

已重启并验证:

```text
MacA: 9090 9091 9092 9093 9094 9095 9096 9097
MacB: 8081 8082 8083 8084
```

验收结果:

- `bot_manager.sh status`: 12/12 运行中
- 12/12 返回 `ai_execution_authority`
- 12/12 返回 `m1_m4_feed.ok = true`
- 12/12 返回 `m1_m4_feed.pair_count = 5`
- MacA 数据源:
  - `http://127.0.0.1:9099/api/v1/ai_data_flow`
- MacB 数据源:
  - `http://192.168.13.48:9099/api/v1/ai_data_flow`
- 机器人直接下单权限保持关闭:
  - `robot_direct_entry = false`
  - `robot_direct_exit = false`

## 四、后续注意

## 五、2026-04-27 下单杠杆与广播修复

### 问题

- 天眼捕捉到入场信号后，实际 `forceenter` 请求没有把 `leverage` 放进 Freqtrade 识别的下单体，只尝试调用不存在的 `/api/v1/leverage`，导致订单落成 1X。
- Gate 端机器人没有 leverage tiers 缓存时，Freqtrade 的 `get_max_leverage()` 返回 1.0，会把传入的 5X/7X/10X 再次压成 1X。
- 天眼 `EXECUTE_LONG/EXECUTE_SHORT` 原执行路径只面向单个 `port`，不符合“捕捉信号后同时下发给全部机器人”的集群执行要求。

### 已修复

- `console_server.py`
  - `_do_tianyan_entry()` 下单体改为真实 `forceenter` 字段: `stakeamount`、`ordertype`、`leverage`、`entry_tag`。
  - 天眼 `EXECUTE_LONG/EXECUTE_SHORT` 默认广播到 12 个机器人；支持 `target_ports/ports` 定向覆盖。
  - 广播前逐端口检查同交易对持仓，已有持仓则跳过，避免重复或对冲。
  - 广播成功后逐端口写入天眼冷却锁，避免同一轮重复下发。
  - 天眼反手、出山反手、资金流猎杀、手动反手、手动补仓路径补齐 `leverage/stakeamount`。
- `freqtradebot.py`
  - 当交易所 leverage tiers 缺失且请求杠杆大于 1X 时，使用请求杠杆/配置杠杆作为运行上限，不再默认压回 1X。
  - 已同步 MacA 源码、MacA venv 运行包、MacB 源码、MacB venv 运行包。

### 验收

- `py_compile` 通过:
  - `/Users/luxiangnan/freqtrade_console/console_server.py`
  - `/Users/luxiangnan/freqtrade/freqtrade/freqtradebot.py`
  - `/Users/luxiangnan/freqtrade/.venv311/lib/python3.11/site-packages/freqtrade/freqtradebot.py`
  - MacB 对应源码与 venv 运行包
- 12 个机器人已重启并验证运行:
  - MacA: 9090-9097
  - MacB: 8081-8084
- 9099 控制台服务已重启。

### 注意

未手动触发真实下单验证。下一次天眼真实捕捉到信号时，日志应出现:

- `tianyan_auto_entry`
- `leverage` 为 AI/公式输出的 5X/7X/10X，而不是 1X
- `[天眼AI · 授权入场广播] ... 成功N/12`

后续修改自动驾驶 API 时，必须同时确认源码目录和实际运行的 venv/site-packages 副本是否一致。MacB 因为设置了 `PYTHONPATH=/Users/luxiangnan/freqtrade`，源码目录会优先于 venv 包加载。

不要手动调用 `run_once` 验证自动驾驶，因为它可能进入真实交易流程。验收应优先使用:

- `/api/v1/autopilot/status`
- `/api/v1/ai_data_flow`
- `/api/v1/central_data`
- `bot_manager.sh status`
## 2026-04-27 过去2小时多单捕捉审计与修复

- 触发模式: 20:30 SOL、21:38 BTC 均为天眼AI自动驾驶入场链路触发，`enter_tag=tianyan_auto_entry`。21:38 BTC 已广播到 12 个机器人，OKX 9093-9097 和 MacB 8081-8084 均有 5X BTC 多单记录；20:30 SOL 中 OKX 9093 因已有 SOL 持仓被跳过。
- 仓位金额问题: 杠杆已正确进入 5X，但天眼入场执行使用 AI 返回的固定 `stake_amount`，没有套用机器人 V6.5 的仓位公式。已修复为每个机器人按自己的 USDT 可用余额计算: `可用USDT × 5% × 杠杆`，并用 `可用USDT × 50%` 单笔封顶，AI 金额只作余额读取失败时的兜底。
- 过早平仓问题: SOL 在 21:15 被旧“方向错误”规则识别，21:16-21:17 执行强平。原因是旧规则把“做多入场价略低/贴近支撑 + 量比<1”判为方向错误；这与 V6.5 的 15M 支撑区做多逻辑冲突，属于过早平仓风险。
- 规则修复: 方向错误现在只在 S/R 有效击穿或明显站错区时触发；贴近支撑做多、贴近压力做空不再判错。非致命方向错误增加 60 分钟 15M 发育期保护。`premature_entry` 只观察/通知，不再进入自动 forceexit 执行分支，最终出场交给出山AI/持仓卫士。

## 2026-04-27 全链路三轮审计与空数据修复

- 审计范围: 9099统一数据中枢、M1/M2/M3/M4、天眼入场状态、出山出场状态、英雄卡、12个机器人 `bot_feed` 订阅口、12个机器人 RPC `ping/status/balance`。
- 初始三轮结果: 213项检查，HTTP失败0；发现字段级问题69项，集中在 M3无信号空字段、M4市场指数空 `position_advice`、天眼英雄卡持仓卡未兜底M1-M4、出山评测目标价/止损价为 null、自动驾驶总开关状态不持久化。
- 修复内容:
  - M3无巨量K线时补齐 `alert_desc/reversal_signal/last_giant/last_giant_candle`，不再返回空串或空对象。
  - M4市场指数为空仓位建议时补齐 `position_advice={action:observe,direction:neutral,order_permission:false}`。
  - 天眼/出山英雄卡持仓卡从统一 `ai_data_flow` 回填 M1-M4，补齐 AI话术、S/R、ATR、DCA默认值。
  - 出山AI状态补齐 `ai_target_price/ai_stop_price` 的 M2参考或V6.5保证金兜底值。
  - 自动驾驶开关增加状态文件持久化和关闭原因；审计中未直接打开真实自动执行开关。
  - S/R异常保护: 当聚合结果出现 `support >= resistance` 时，不允许触发方向错误强平，避免再次误判。
- 修复后三轮复验: 69项检查，HTTP失败0，字段级空值0。所有被审计链路三轮均通过。
