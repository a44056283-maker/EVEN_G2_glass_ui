# 风控管理学习笔记

## 2025-03-30 | 保证金率与强平计算

---

## 学习主题：强平价计算

### 核心公式

**强平价（Liquidation Price）计算：**

```
多仓（Long）：
  强平价 = 开仓价 × (1 - 维持保证金率)
         = 开仓价 × (1 - 1/杠杆倍数)

空仓（Short）：
  强平价 = 开仓价 × (1 + 维持保证金率)
         = 开仓价 × (1 + 1/杠杆倍数)
```

**注意：** 实际强平价还需考虑手续费、资金费率等，这里是简化模型。

### 不同杠杆倍数下的强平价示例

以 BTC 开仓价 $100,000 为例：

| 杠杆倍数 | 维持保证金率 (≈1/杠杆) | 多仓强平价 | 多仓距离开仓价跌幅 |
|---------|----------------------|-----------|------------------|
| 10x     | 10%                  | $90,000   | -10%             |
| 20x     | 5%                   | $95,000   | -5%              |
| 50x     | 2%                   | $98,000   | -2%              |
| 100x    | 1%                   | $99,000   | -1%              |

### Python实现：强平价计算器

```python
def calculate_liquidation_price(
    entry_price: float,
    leverage: float,
    direction: str  # "long" or "short"
) -> dict:
    """
    计算合约强平价
    
    Args:
        entry_price: 开仓价格
        leverage: 杠杆倍数 (e.g., 10, 20, 100)
        direction: 仓位方向 "long"(多) 或 "short"(空)
    
    Returns:
        包含强平价和风险参数的字典
    """
    if leverage <= 0:
        raise ValueError("杠杆倍数必须大于0")
    
    if direction not in ["long", "short"]:
        raise ValueError("direction必须是'long'或'short'")
    
    # 维持保证金率 ≈ 1 / 杠杆倍数
    maintenance_margin_rate = 1 / leverage
    
    if direction == "long":
        liquidation_price = entry_price * (1 - maintenance_margin_rate)
    else:  # short
        liquidation_price = entry_price * (1 + maintenance_margin_rate)
    
    # 计算距强平价的幅度
    distance_pct = abs((liquidation_price - entry_price) / entry_price * 100)
    
    return {
        "entry_price": entry_price,
        "leverage": leverage,
        "direction": direction,
        "liquidation_price": round(liquidation_price, 2),
        "maintenance_margin_rate": round(maintenance_margin_rate * 100, 2),
        "distance_from_entry_pct": round(distance_pct, 2),
        "max_loss_pct": round(distance_pct + 0.5, 2)  # 预估手续费
    }


# 测试用例
if __name__ == "__main__":
    # 示例1: 10倍杠杆做多
    result = calculate_liquidation_price(100000, 10, "long")
    print(f"10x Long @ $100,000 → 强平价: ${result['liquidation_price']}")
    
    # 示例2: 20倍杠杆做空
    result = calculate_liquidation_price(100000, 20, "short")
    print(f"20x Short @ $100,000 → 强平价: ${result['liquidation_price']}")
```

---

## 学习主题：风险度量基础

### 1. VaR（Value at Risk）

**定义：** 在给定置信水平下，在特定时间段内可能遭受的最大损失。

```
VaR = 投资组合价值 × 波动率 × Z-score × √时间
```

| 置信水平 | Z-score |
|---------|---------|
| 95%     | 1.645   |
| 99%     | 2.326   |

**示例：** 组合价值 $100,000，日波动率2%，95%置信水平
```
VaR(95%, 1天) = 100,000 × 0.02 × 1.645 × √1 = $3,290
```

### 2. 最大回撤（Max Drawdown）

**定义：** 从历史最高点到最低点的最大跌幅。

```
Max Drawdown = (最低点 - 最高点) / 最高点 × 100%
```

**Python实现：**
```python
def calculate_max_drawdown(equity_curve: list) -> dict:
    """
    计算最大回撤
    
    Args:
        equity_curve: 每日/每小时权益列表
    
    Returns:
        最大回撤信息和恢复时间
    """
    peak = equity_curve[0]
    max_dd = 0
    peak_at = 0
    trough_at = 0
    
    for i, value in enumerate(equity_curve):
        if value > peak:
            peak = value
            peak_at = i
        
        drawdown = (peak - value) / peak
        if drawdown > max_dd:
            max_dd = drawdown
            trough_at = i
    
    return {
        "max_drawdown_pct": round(max_dd * 100, 2),
        "peak_value": peak,
        "trough_value": equity_curve[trough_at],
        "peak_at_index": peak_at,
        "trough_at_index": trough_at
    }


# 测试
equity = [100000, 105000, 110000, 95000, 90000, 105000, 120000]
result = calculate_max_drawdown(equity)
print(f"最大回撤: {result['max_drawdown_pct']}%")  # 输出: 18.18%
```

### 3. 止损档位设计逻辑

**设计原则：**

1. **分级止损**：根据持仓大小设置不同止损点
   - 轻仓（<10%）：宽止损，容忍波动
   - 重仓（>30%）：严格止损，控制风险

2. **动态调整**：
   - 盈利时可适当放宽止损
   - 亏损扩大时绝不放松

3. **档位参考**（以BTC为例）：
   | 杠杆倍数 | 建议止损幅度 | 止损类型 |
   |---------|-------------|---------|
   | 5x      | 8-10%       | 固定止损 |
   | 10x     | 4-6%        | 固定止损 |
   | 20x     | 2-3%        | 时间止损 |
   | 50x+    | 1-2%        | 硬止损   |

4. **资金管理**：
   - 单笔交易最大亏损 ≤ 总资金2%
   - 单日最大亏损 ≤ 总资金5%

---

## 本周学习总结

### 核心公式

1. **强平价（多仓）**：`强平价 = 开仓价 × (1 - 1/杠杆)`
2. **强平价（空仓）**：`强平价 = 开仓价 × (1 + 1/杠杆)`
3. **VaR**：`VaR = 组合价值 × 波动率 × Z-score × √时间`
4. **最大回撤**：`MaxDD = (最低点 - 最高点) / 最高点`

### 风控核心原则

- **先算风险，后下单**
- **止损永远是对的，市场永远是对的**
- **宁可少赚，不可大亏**
- **杠杆越高，仓位越轻**
