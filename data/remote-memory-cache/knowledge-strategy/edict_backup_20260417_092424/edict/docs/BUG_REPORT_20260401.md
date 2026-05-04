# 交易系统BUG报告

**日期：** 2026-04-01
**编写：** 天禄（太子）
**指派：** 天福（二弟）

---

## BUG-001: `audit_guard.py status` 崩溃

**严重程度：** 🔴 高
**影响文件：** `audit_guard.py` 第201-204行

**问题描述：**
执行 `python3 audit_guard.py status` 时崩溃：
```
ValueError: time data '?' does not match format '%Y-%m-%d %H:%M:%S'
```

**根因：**
当 `bingbu_freeze.json` 中 `frozen=false` 时，`last_freeze_at` 字段不存在。代码取默认值 `"?"` 后，`strptime` 解析失败。

**当前 `bingbu_freeze.json` 内容：**
```json
{
  "frozen": false,
  "frozen_pairs": [],
  "timestamp": "2026-03-31T17:21:07.774781"
}
```

**修复方案：**
```python
last = freeze.get("last_freeze_at", "?")
if last == "?":
    print(f"冻结状态: ✅ 未冻结（从未冻结过）")
else:
    # 正常计算cooldown
```

---

## BUG-002: `bingbu_intervention.json` 数据污染

**严重程度：** 🔴 高
**影响文件：** 写入逻辑

**问题描述：**
`bingbu_intervention.json` 中存在大量重复的 `id=101` unfreeze 记录（至少40+条完全相同的记录），时间跨度从 2026-03-25 到 2026-03-31。

**根因分析：**
- `unfreeze` 逻辑没有去重检查
- 飞书卡片按钮可能被多次点击（无幂等性保护）
- 每次点击都写入一条新记录

**修复方案：**
1. `unfreeze` 前先检查最近一条记录是否已为 `unfreeze`，避免重复
2. 或者用 `id` 作为唯一键，更新而非追加

---

## BUG-003: 黑天鹅Cooldown与实际市场持续恐慌不匹配

**严重程度：** 🟡 中
**影响文件：** `monitor_sentiment.py`

**问题描述：**
- 当前 `FREEZE_COOLDOWN_MINUTES = 30`
- Fear & Greed 指数从 2026-03-28 起持续在 8-14 区间（极度恐慌）
- 黑天鹅警报频繁触发，但30分钟内被跳过
- 导致 `pending_approvals.json` 堆积大量历史提案（部分已rejected）

**当前待审批堆积：**
- `BS-03312045-3504` (2026-03-31 20:45, FG=11, status=rejected)
- `BS-03301320-0046` (2026-03-30 13:20, FG=8, status=rejected)
- `BS-03290935-7629` (2026-03-29 09:35, FG=9, status=rejected)

**修复方案：**
1. 当 FG 持续低于20超过 N 小时（如4小时），自动延长Cooldown至更长（如2小时）
2. 或者增加"强黑天鹅"等级：FG≤10 时不进入Cooldown
3. 定期清理 `pending_approvals.json` 中的历史提案

---

## BUG-004: 调度日志误报 "CLI failed"

**严重程度：** 🟡 中
**影响文件：** 调度脚本/cron配置

**问题描述：**
```
System: [2026-04-01 03:56:19 GMT+8] Exec completed (delta-sh, code 0) :: CLI failed
```

实际 exec 返回码为 0（成功），但日志显示 "CLI failed"。

**可能原因：**
- 调度命令 `cd /Users/luxiangnan/edict/scripts/qintianjian && python3 aggregator.py && python3 ../monitor_sentiment.py` 中有某个子命令非0退出码
- 或者日志记录逻辑有误

**排查方向：**
检查 aggregator.py 和 monitor_sentiment.py 中所有 `sys.exit()` 调用

---

## BUG-005: 缺少数据目录初始化

**严重程度:** 🟢 低
**影响文件:** 多个脚本

**问题描述：**
`qintianjian/data/` 目录存在但为空，无 `.gitkeep`。
脚本运行时依赖的JSON文件（如 `bingbu_freeze.json`）需要预先存在。

**修复方案：**
- 确保 `bingbu_freeze.json`、`bingbu_intervention.json`、`pending_approvals.json` 在初始化时就存在
- 或在脚本启动时自动创建

---

## 附录：当前系统状态

### 冻结状态
- `frozen`: false
- `frozen_pairs`: []
- 最后冻结时间: 2026-03-31 17:21:07（手动解冻后未再冻结）

### 待审批队列
- 共 3+ 历史提案，全部 rejected
- 无 pending 状态提案

### 当前市场情绪
- Fear & Greed: 11（极度恐慌）
- 信号: 极度恐慌
- 方向: NEUTRAL
- 紧急度: 8

### 服务端口
- 9090-9093: freqtrade instances
- 9099: console_server.py
- 7891: edict/qintianjian
- 9081: aivm
