# v0.5.20 定位诊断与视觉/语音定位上下文报告

时间：2026-05-05 17:35

## 结论

本版本直接实现定位功能增强，不再等待 v0.5.19 真机反馈。定位已变成可见、可诊断、可写入上下文的产品功能。

本版本状态：允许上传测试，不批准正式上架。

## 变更

- 设置页新增“实时定位诊断”：
  - 显示 `navigator.geolocation` 是否可用。
  - 显示浏览器/Even WebView 权限状态。
  - 支持“检测定位”和“请求定位”。
  - 显示定位状态、粗略坐标、精度、粗略地址和失败原因。
- 定位上下文增强：
  - 5 秒定位超时。
  - 5 分钟定位缓存。
  - 5 分钟粗略地址缓存。
  - 定位失败不阻塞视觉识别和呼叫天禄。
  - 交易状态不附带定位。
- 地址解析：
  - 成功拿到经纬度后尝试用公开反向地理编码获取粗略地址。
  - 如果地址解析失败，仍使用粗略经纬度作为 AI 场景辅助。
- 视觉识别：
  - 视觉请求附带粗略地址/粗略坐标/精度/时间。
  - 视觉历史详情写入本次定位上下文。
- 呼叫天禄：
  - 非交易类语音问答附带实时定位上下文。
  - 语音历史详情写入本次定位上下文。
- 设置历史：
  - 每次定位诊断会写入设置历史，便于审计权限失败原因。

## 边界

如果 Even App WebView 没有暴露 `navigator.geolocation`，插件无法强行获取定位。v0.5.20 会明确显示：

- `WebView API：不可用`
- 权限状态
- 失败原因
- 处理建议

这可以把问题区分为插件问题、系统权限问题、网络/超时问题或 Even App 宿主能力问题。

## 验证

- `node node_modules/typescript/bin/tsc --noEmit -p apps/evenhub-plugin/tsconfig.json`：通过
- `node node_modules/typescript/bin/tsc -p packages/shared/tsconfig.json --noEmit`：通过
- `node node_modules/typescript/bin/tsc -p services/api-server/tsconfig.json --noEmit`：通过
- `node node_modules/typescript/bin/tsc -p packages/vision-adapter/tsconfig.json --noEmit`：通过
- `node ../../node_modules/typescript/bin/tsc -p tsconfig.json`：通过
- `esbuild` 前端构建：通过
- EvenHub CLI pack：通过

## 产物

- EHPK：`/Users/luxiangnan/Desktop/g2-vision-voice-assistant-v0.5.20-location-diagnostics-test.ehpk`
- SHA256：`16e8c1440468d9497e286fd4bbc767a88191645ae9cd7ce31c7b1176b53cfcf1`

## 真机验收重点

1. 设置页确认版本号为 0.5.20。
2. 设置页点击“请求定位”，查看是否出现粗略坐标、精度和粗略地址。
3. 若定位失败，记录失败原因：不可用、拒绝、超时或错误。
4. 视觉识别 3 次，确认视觉历史详情包含定位上下文。
5. 呼叫天禄 3 次，确认语音历史详情包含定位上下文。
6. 交易状态 3 次，确认不包含定位上下文。

