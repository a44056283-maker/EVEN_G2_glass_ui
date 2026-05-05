# 新 crash 审计报告

时间：2026-05-05

## 范围

- 前端：`apps/evenhub-plugin/src/runtimeErrorReporter.ts`
- 前端接入：`apps/evenhub-plugin/src/main.ts`
- 后端：`services/api-server/src/server.ts`
- 日志落点：`docs/gpt-advisor/logs/runtime-errors.jsonl`

## 实现结论

1. `window.onerror` 已安装，发生页面运行时错误时会记录 `kind=error`。
2. `window.onunhandledrejection` 已安装，未捕获 Promise rejection 会记录 `kind=unhandledrejection`。
3. `safeShowOnG2` 捕获 G2 文本显示失败后会记录 `kind=g2-display`，不阻断网页流程。
4. `safeGlassShow` 捕获 GlassRenderer 渲染失败后会记录 `kind=glass-show`，不阻断网页流程。
5. 后端新增 `POST /debug/runtime-error`，按 JSON Lines 追加写入 `docs/gpt-advisor/logs/runtime-errors.jsonl`。
6. 前后端均执行脱敏：API key、Bearer token、token/key/password/secret 查询参数或键值、data image base64 会被替换。

## 数据格式

每行一条 JSON：

```json
{"receivedAt":"2026-05-05T00:00:00.000Z","kind":"error","message":"TypeError: example","detail":"...","createdAt":"2026-05-05T00:00:00.000Z","page":"http://localhost:5173/","source":"evenhub-plugin"}
```

## 注意

- 前端网络不可用时仍会保留最近 40 条脱敏记录到 `localStorage:g2-vva-runtime-errors-v1`。
- 后端日志目录由接口按需创建，不需要手工预建。
