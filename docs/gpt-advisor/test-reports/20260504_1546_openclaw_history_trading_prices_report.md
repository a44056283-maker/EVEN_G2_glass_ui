# P1-OPENCLAW-HISTORY-TRADING-PRICES-001 测试报告

## 1. OpenCLAW 配置

| 配置项 | 值 |
|--------|-----|
| OPENCLAW_BASE_URL | https://even2026.tianlu2026.org |
| OPENCLAW_TOKEN | tianlu2026 (placeholder, see below) |
| OPENCLAW_MODEL | tianlu |
| OPENCLAW_AGENT_MODEL | tianlu |
| OPENCLAW_AGENT_NAME | tianlu |
| OPENCLAW_TIMEOUT_MS | 30000 |

**Token 状态**: `OPENCLAW_GATEWAY_TOKEN` 待用户提供。当前代码优先读取 `OPENCLAW_GATEWAY_TOKEN`，fallback 到 `OPENCLAW_TOKEN`。需填入真实 gateway token 才能解决 401。

## 2. OpenCLAW 401 修复

- 代码已确认：`services/api-server/src/openclaw.ts` 第 45 行 `const token = process.env.OPENCLAW_GATEWAY_TOKEN ?? process.env.OPENCLAW_TOKEN`
- 401 错误提示已正确设置为 "OpenCLAW 认证失败，请检查 OPENCLAW_GATEWAY_TOKEN"
- **待完成**: 需要用户提供 `OPENCLAW_GATEWAY_TOKEN` 真实值

## 3. 历史记录 Fallback 机制

### 修改文件
- `apps/evenhub-plugin/src/history.ts`

### 修改内容
1. 增加 `lastHistoryError` 变量和 `getLastHistoryError()` getter
2. 增加 `memoryHistoryFallback` 内存兜底数组
3. `addHistory()` 增加 try/catch，失败时 dispatch `g2vva:history-error` 事件
4. `getHistory()` 在 localStorage 失败时返回 memory fallback
5. `clearHistory()` 同时清除内存 fallback 和 error 状态
6. `renderHistory()` 在有 error 时显示 "历史保存失败：${error}"

### 错误提示文案
```
历史保存失败：localStorage 不可用 / 容量不足 / WebView 禁止存储
```

## 4. 眼镜白名单价格极简显示

### 修改文件
- `apps/evenhub-plugin/src/glass/glassScreens.ts`

### renderTradingPrices 最终模板
```
BTC  68321.45      ETH  3520.18
SOL  172.31        BNB  597.20
DOGE 0.1534
```

### 格式规则
- BTC/ETH/BNB/SOL >= 1: 2 位小数
- DOGE 或 < 1 的币种: 4 位小数
- 无值: `--`

## 5. 交易子菜单按钮修复

### 问题
1. `runTradingOverview()` fetch 数据后没有重新渲染眼镜，导致价格 strip 为空
2. 手机按钮在没有 `lastTradingOverview` 时调用 `runAssistantQuestion` 而不是加载数据

### 修复内容
1. `runTradingOverview()` 成功后重新调用 `renderer.show('trading_menu', { extendedData: { prices: ... } })` 渲染带价格 strip 的菜单
2. 手机 preset 按钮在无缓存时先调用 `runTradingOverview()` 等其完成后再调用 `showTradingSubPage()`

## 6. OpenCLAW Gateway 测试脚本

### 文件
- `scripts/gpt-advisor/test_openclaw_gateway.sh`

### 用法
```bash
OPENCLAW_BASE_URL=https://even2026.tianlu2026.org \
# 先在 shell 中设置 OPENCLAW_GATEWAY_TOKEN
OPENCLAW_MODEL=tianlu \
bash scripts/gpt-advisor/test_openclaw_gateway.sh
```

## 7. 待完成事项

| 事项 | 状态 |
|------|------|
| 提供 OPENCLAW_GATEWAY_TOKEN | 待用户输入 |
| typecheck / build / pack:g2 | Node 环境不可用，待在开发机执行 |
| EHPK 路径和 SHA256 | 待构建后生成 |

## 8. 未解决问题

1. **OpenCLAW 401**: 需要真实的 `OPENCLAW_GATEWAY_TOKEN`。当前本地 OpenCLAW token 为占位值，不是远程 gateway 的真实 token。
2. **白名单价格为空**: 可能是 console API `/api/prices/realtime` 未返回数据，需检查 `https://console.tianlu2026.org/api/prices/realtime` 是否正常。
