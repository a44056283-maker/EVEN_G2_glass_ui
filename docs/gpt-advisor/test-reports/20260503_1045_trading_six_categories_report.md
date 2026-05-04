# 交易状态六类数据播报报告

## 基本信息

- **任务编号**: TRADING-SIX-CATEGORIES
- **执行日期**: 2026-05-03
- **EHPK 路径**: `apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- **SHA256**: `98a4687b08023cb3af86048827d84f457750fec636fad04e3c9f014d3ecefb5a`
- **构建结果**: 成功（29 modules transformed）

---

## 1. 交易六类数据分类

### 手机网页书签（6个预设快捷按钮）

| 按钮 | ID | 功能 |
|------|-----|------|
| 运行状态 | `trading-preset-status` | 调用 `runTradingOverview()` 刷新并显示总览 |
| 白名单价格 | `trading-preset-prices` | 切换到眼镜价格页，或调用 `/ask` 查询 |
| 持仓盈亏 | `trading-preset-positions` | 切换到眼镜持仓页，或调用 `/ask` 查询 |
| 风控状态 | `trading-preset-risk` | 切换到眼镜告警页，或调用 `/ask` 查询 |
| 资金分布 | `trading-preset-distribution` | 切换到眼镜资金分布页，或调用 `/ask` 查询 |
| 订单归因 | `trading-preset-attribution` | 切换到眼镜订单归因页，或调用 `/ask` 查询 |

### 眼镜端子页面（6个 R1 单触循环页面）

| 索引 | 页面 ID | 眼镜显示内容 |
|------|---------|-------------|
| 0 | `trading_status` | 运行状态 + 心跳 + 策略 + 持仓/挂单 + PnL + 风险 |
| 1 | `trading_prices` | BTC ETH SOL BNB DOGE 实时价格（前5个） |
| 2 | `trading_positions` | 持仓数 + 浮动盈亏 + 各交易对 PnL 明细（前4个） |
| 3 | `trading_distribution` | M1-M5 持仓集中度（前5个交易对） |
| 4 | `trading_attribution` | 胜率 + 平均已实现/未实现盈亏 + 样本数 |
| 5 | `trading_alerts` | 当前系统告警列表（分级显示） |

---

## 2. 手机网页交互

- 交易书签下显示 6 个按钮，3 列布局
- 点击「运行状态」→ 刷新总览数据
- 点击其他 5 个按钮 → 如果已有缓存数据直接切换眼镜页面；否则走 `runAssistantQuestion()` fallback

## 3. 眼镜端交互

- 进入「交易状态」后 R1 单击：循环切换 6 个分类页面（0→1→2→3→4→5→0...）
- 每个页面底部显示「R1单击切下一页」（总览返回首页，告警返回总览）

## 4. 数据来源

- 所有数据来自 `/trading/overview` 单次获取后缓存到 `lastTradingOverview`
- 不额外发起请求，直接使用已缓存的 `TradingReadonlyOverview.live`

## 5. 修改文件

| 文件 | 修改内容 |
|------|---------|
| `index.html` | 6 个交易预设按钮（替换原来 3 个） |
| `src/style.css` | 交易书签行 3 列布局 |
| `src/main.ts` | 添加 `tradingSubPageIndex`、`lastTradingOverview`、`showTradingSubPage()`、6 个按钮处理器、R1 交易子页面处理 |
| `src/glass/glassScreens.ts` | 新增 5 个交易子页面类型和渲染函数 |

## 6. 构建结果

```
✓ 29 modules transformed
dist/index.html          12.57 kB
dist/assets/*.css        22.89 kB
dist/assets/*.js       188.02 kB
✓ built in 833ms
✓ packed out.ehpk (77941 bytes)
```

## 7. EHPK 信息

- **文件**: `g2-vision-voice-assistant.ehpk`
- **SHA256**: `98a4687b08023cb3af86048827d84f457750fec636fad04e3c9f014d3ecefb5a`
- **路径**: `apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`

## 8. 下一步

- [ ] 真机验证 6 个眼镜页面内容正确
- [ ] 真机验证 R1 单击循环切换 6 个页面
- [ ] 真机验证手机网页 6 个按钮点击效果
