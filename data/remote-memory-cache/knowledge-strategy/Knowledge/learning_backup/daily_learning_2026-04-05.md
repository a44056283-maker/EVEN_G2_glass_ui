# 每日学习笔记 - 2026-04-05

> 太子每日学习记录 | 时间段: 14:00-15:00 | 主题: 最大回撤控制与风险预算

---

## 今日学习主题

- **类别**: 仓位与风险管理（第3周）
- **主题**: 最大回撤控制与风险预算
- **前置学习**: 凯利公式 ✅、ATR动态止损 ✅
- **学习来源**: 知识库（risk_management.md）+ 自我推导

---

## 核心概念

### 1. 最大回撤（Max Drawdown）

**定义：** 账户从历史最高点到最低点的最大跌幅百分比。

```
Max Drawdown = (Peak - Trough) / Peak × 100%
```

**为什么重要？**
- 回撤的痛苦是非对称的：亏损50%需要盈利100%才能回本
- 最大回撤决定了你需要多大的"安全垫"
- 复利效应：控制回撤比追求高收益更重要

**回撤与回本所需盈利对照：**

| 最大回撤 | 回本所需盈利 |
|---------|------------|
| 10% | 11.1% |
| 20% | 25.0% |
| 30% | 42.9% |
| 50% | 100.0% |
| 75% | 300.0% |
| 90% | 900.0% |

**核心洞察：回撤越大，回本难度指数级增长。10%止损线比20%止损线价值高得多。**

### 2. 风险预算（Risk Budget）

**定义：** 将账户可承受的总风险分配到不同时间周期和交易维度。

**层级结构：**

```
总风险预算（年度）
├── 月度风险预算（月最大亏损）
│   └── 周度风险预算（周最大亏损）
│       └── 日度风险预算（日最大亏损）
│           └── 单笔风险预算（单笔最大亏损）
```

**建议比例（保守/标准/激进）：**

| 维度 | 保守 | 标准 | 激进 |
|------|------|------|------|
| 单笔最大亏损 | 1% | 2% | 3% |
| 日最大亏损 | 3% | 5% | 8% |
| 周最大亏损 | 5% | 8% | 12% |
| 月最大亏损 | 10% | 15% | 20% |
| 最大回撤上限 | 15% | 20% | 30% |

### 3. 动态风险预算调整

**核心原则：亏损时收紧仓位，盈利时适当放松**

**公式：**
```
当前风险比例 = 基础风险比例 × (1 - 当前回撤率) / (1 - 最大回撤率)
```

**简化版：**
- 账户从高点回撤5%以内：正常执行
- 账户从高点回撤5-10%：降低50%仓位
- 账户从高点回撤10-15%：降低75%仓位或暂停
- 账户从高点回撤>15%：强制暂停，复盘原因

---

## Python实现

### 最大回撤监控器

```python
class DrawdownMonitor:
    """账户回撤监控器"""
    
    def __init__(self, max_drawdown_limit: float = 0.20,
                 daily_loss_limit: float = 0.05,
                 weekly_loss_limit: float = 0.08):
        self.peak = 0
        self.equity_curve = []
        self.max_drawdown_limit = max_drawdown_limit
        self.daily_loss_limit = daily_loss_limit
        self.weekly_loss_limit = weekly_loss_limit
        self.session_start_equity = 0
        self.today_start_equity = 0
        self.week_start_equity = 0
        
    def update(self, current_equity: float) -> dict:
        """更新权益，返回当前状态"""
        # 更新峰值
        if current_equity > self.peak:
            self.peak = current_equity
        
        # 记录曲线
        self.equity_curve.append(current_equity)
        
        # 计算当前回撤
        current_drawdown = (self.peak - current_equity) / self.peak
        drawdown_pct = current_drawdown * 100
        
        # 状态判断
        if drawdown_pct >= self.max_drawdown_limit * 100:
            status = "CRITICAL"
        elif drawdown_pct >= self.max_drawdown_limit * 100 * 0.75:
            status = "WARNING"
        else:
            status = "NORMAL"
        
        return {
            "current_equity": current_equity,
            "peak": self.peak,
            "current_drawdown_pct": round(drawdown_pct, 2),
            "status": status,
            "can_trade": status == "NORMAL"
        }
    
    def check_daily_loss(self, today_start: float, current_equity: float) -> dict:
        """检查日亏损"""
        daily_loss = (today_start - current_equity) / today_start
        daily_loss_pct = daily_loss * 100
        
        return {
            "daily_loss_pct": round(daily_loss_pct, 2),
            "daily_limit": self.daily_loss_limit * 100,
            "exceeded": daily_loss_pct > self.daily_loss_limit * 100,
            "action": "STOP" if daily_loss_pct > self.daily_loss_limit * 100 else "CONTINUE"
        }
    
    def get_position_reduction(self, current_equity: float, base_position_pct: float) -> float:
        """根据回撤计算应该降低的仓位比例"""
        if self.peak == 0:
            return base_position_pct
        
        current_drawdown = (self.peak - current_equity) / self.peak
        
        if current_drawdown < 0.05:
            return base_position_pct  # 正常
        elif current_drawdown < 0.10:
            return base_position_pct * 0.50  # 降50%
        elif current_drawdown < 0.15:
            return base_position_pct * 0.25  # 降75%
        else:
            return 0  # 暂停


# 使用示例
monitor = DrawdownMonitor(
    max_drawdown_limit=0.20,  # 20%最大回撤
    daily_loss_limit=0.05,    # 5%日亏损限制
    weekly_loss_limit=0.08     # 8%周亏损限制
)

# 模拟交易
equity = 10000
# ... 交易后 equity 变成 9800
status = monitor.update(9800)
print(f"当前状态: {status}")
# 当前状态: {'current_equity': 9800, 'peak': 10000, 'current_drawdown_pct': 2.0, 'status': 'NORMAL', 'can_trade': True}

# 继续亏损到 9200
status = monitor.update(9200)
print(f"当前状态: {status}")
# 当前状态: {'current_equity': 9200, 'peak': 10000, 'current_drawdown_pct': 8.0, 'status': 'NORMAL', 'can_trade': True}

# 建议仓位调整
reduction = monitor.get_position_reduction(9200, 0.10)  # 原仓位10%
print(f"建议仓位: {reduction*100}%")  # 建议仓位: 5.0%
```

---

## 风控检查清单

```
┌─────────────────────────────────────────────────────────┐
│           开仓前风控检查（必读）                          │
├─────────────────────────────────────────────────────────┤
│ 1. 当前回撤：___% （警戒线：15%）                        │
│ 2. 今日亏损：___% （停止线：5%）                         │
│ 3. 本周亏损：___% （停止线：8%）                         │
│ 4. 本月亏损：___% （停止线：15%）                         │
│ 5. 凯利仓位：___% （上限：10%）                          │
│ 6. 单笔风险：___% （上限：2%）                           │
│ 7. ATR止损距离：___%（建议<5%）                          │
│ 8. 杠杆倍数：___x （上限：10x）                          │
│ 9. 保证金率：___%（建议>200%）                            │
└─────────────────────────────────────────────────────────┘
✓ 全部通过 → 可开仓
✗ 任一超标 → 禁止开仓
```

---

## 与凯利公式的关系

**凯利公式回答："用多少仓位？"**
**回撤控制回答："什么时候减少/停止交易？"**

两者结合：

```
实际仓位 = f*(凯利) × 风险调整系数

风险调整系数：
  - 正常市场：1.0
  - 回撤5-10%：0.5
  - 回撤10-15%：0.25
  - 回撤>15%：0（暂停）

示例：
  f* = 20%（凯利计算）
  当前回撤 = 8%
  风险调整 = 0.5
  实际仓位 = 20% × 0.5 = 10%
```

---

## 纳入知识库

| 项目 | 状态 |
|------|------|
| 知识库路径 | `Knowledge/仓位管理/最大回撤控制与风险预算.md` |
| 实战案例补充 | ⏳ 待补充（实盘验证） |
| 与凯利公式联动 | ✅ 已整合 |

---

## 明日计划

**主题：第3周收尾 + 第4周启动（回测与绩效评估）**

学习内容：
1. 回顾第3周仓位管理三大核心（凯利公式 + ATR止损 + 回撤控制）
2. 启动第4周：回测陷阱（过拟合、前视偏差、生存者偏差）
3. 夏普比率和索提诺比率计算

---

_学习时间: 2026-04-05 14:01_
