# v0.5.22 启动闪退与菜单不可点击热修报告

时间：2026-05-05 18:25

## 结论

v0.5.21 上传后出现闪退、进入后菜单不可点击。该问题按 P0 回归处理，本版本优先恢复启动稳定性和菜单可点击性。

## 修复

- 启动流程不再 `await initHistoryStorage(bridge)`。
- Even Bridge 历史读取改为后台异步执行，失败或耗时不会阻塞按钮事件绑定和首页渲染。
- 历史 Bridge hydration 增加 in-flight 防重入保护。
- `min_sdk_version` 从 `0.0.10` 降回 `0.0.9`，避免开发者平台或 Even App SDK 版本兼容导致启动失败。
- 保留 `location` manifest 权限，继续允许 Even App 向 WebView 授权定位。

## 验证

- `node node_modules/typescript/bin/tsc --noEmit -p apps/evenhub-plugin/tsconfig.json`：通过
- `node node_modules/typescript/bin/tsc -p packages/shared/tsconfig.json --noEmit`：通过
- `node node_modules/typescript/bin/tsc -p services/api-server/tsconfig.json --noEmit`：通过
- `node node_modules/typescript/bin/tsc -p packages/vision-adapter/tsconfig.json --noEmit`：通过
- `node ../../node_modules/typescript/bin/tsc -p tsconfig.json`：通过
- `esbuild` 前端构建：通过
- EvenHub CLI pack：通过

## 产物

- EHPK：`/Users/luxiangnan/Desktop/g2-vision-voice-assistant-v0.5.22-startup-menu-hotfix.ehpk`
- SHA256：`e3ccd33ef5367c350d3f7d86f68a7c4a95b1457782f4854c532fb352771a523f`

## 验收重点

1. 启动后不闪退。
2. 手机端菜单按钮可点击。
3. 设置页应能看到“实时定位诊断”。
4. 历史读取即使失败，也不能影响菜单点击。

