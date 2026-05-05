# v0.5.27 P0/P1 Safe Boot + Location + History + Preview Report

时间：2026-05-05 20:05 CST
版本：0.5.27
任务：修复 v0.5.22/v0.5.26 后仍存在的插件加载、手机菜单点击、G2 首页显示、定位自检、历史持久化、图片预览兼容问题。

## 结论

- 本机没有可运行的 Even/G2 眼镜模拟器。
- 依赖中有 `@evenrealities/evenhub-simulator@0.6.2`，但当前 Mac 是 `darwin-arm64`，本地只装了 `sim-darwin-x64`，直接运行报 `Unsupported platform: darwin-arm64`。
- 已完成本地网页三轮自动化轮测：手机菜单可点击、定位自检入口可用、IndexedDB/localStorage 历史刷新后可恢复。
- 已按官方 SDK 0.0.10 约束修复：G2 图片预览先传 `Uint8Array`，再 base64/data URL 兜底；`audioControl` 只在 `createStartUpPageContainer` 成功后进入。
- 真机 G2 图片显示、G2 PCM、Even App WebView 定位授权仍必须在实机验收中确认。

## 代码修改

1. Safe Boot / G2 门禁
   - `apps/evenhub-plugin/src/main.ts`
   - 新增 `glassUiReady`，只有 `createStartUpPageContainer` 成功后才允许 G2 PCM / MicProbe / 诊断里的 `audioControl`。
   - G2 页面显示失败全部改为安全降级，不再中断手机网页 UI。
   - 启动页失败时状态显示为“手机端已就绪，G2 启动页创建失败”。

2. 图片预览兼容
   - `apps/evenhub-plugin/src/glass/GlassRenderer.ts`
   - `updateImageRawData` 顺序改为：`Uint8Array` -> base64 -> data URL。
   - 保持图片发送队列，避免并发发送。

3. G2 MicProbe 安全显示
   - `apps/evenhub-plugin/src/glass/glassMicProbe.ts`
   - MicProbe 内所有 `renderer.show` 增加本地 `safeShow`，显示失败不阻塞音频链路。

4. 定位自检
   - `apps/evenhub-plugin/index.html`
   - 设置页新增“定位自检”按钮；文案改为“视觉识别和呼叫天禄加入粗略定位”。
   - `apps/evenhub-plugin/src/main.ts`
   - 新增 `runLocationSelfCheck()`，明确请求/检测 `navigator.geolocation`。

5. 版本和 SDK
   - `apps/evenhub-plugin/app.json`：0.5.27，`min_sdk_version` 升至 0.0.10。
   - `apps/evenhub-plugin/package.json`：0.5.27。
   - `package-lock.json` workspace 版本同步。

## 本机模拟器结论

执行：

```bash
node node_modules/@evenrealities/evenhub-simulator/bin/index.js --help
```

结果：

```text
Unsupported platform: darwin-arm64
```

因此本机不能完成真实眼镜模拟器轮测。官方 README 也说明 simulator 只是辅助，不替代硬件测试。

## 本地轮测

### TypeScript

- `node node_modules/typescript/bin/tsc --noEmit -p apps/evenhub-plugin/tsconfig.json`：通过
- `node node_modules/typescript/bin/tsc -p services/api-server/tsconfig.json --noEmit`：通过
- `node node_modules/typescript/bin/tsc -p packages/shared/tsconfig.json --noEmit`：通过

### Build / Pack

- esbuild fallback build：通过
- EvenHub CLI pack：通过
- Code review HIGH 残留：已修复 handleTranscript 和 enterSettingsPage 的直接 G2 show 调用

### 手机网页三轮自动化

环境：`http://127.0.0.1:5187/`，Python Playwright，Chromium headless。

每轮执行：

- 点击视觉识别、呼叫天禄、交易状态、设置、历史五个主菜单。
- 点击设置页“定位自检”。
- 写入 IndexedDB + localStorage 历史记录。
- 刷新页面后进入“历史”，确认全部历史可恢复。

结果：

- Round 1：通过，定位 `约 31.23, 121.47`，历史恢复 `历史持久化测试 Round 1`
- Round 2：通过，定位 `约 31.23, 121.47`，历史恢复 `历史持久化测试 Round 2`
- Round 3：通过，定位 `约 31.23, 121.47`，历史恢复 `历史持久化测试 Round 3`

## EHPK

路径：`/Users/luxiangnan/Desktop/g2-vision-voice-assistant-v0.5.27-safeboot-location-history-preview.ehpk`

SHA256：

```text
e0134542a85ba1ed15962cac0bcab9ed56c2d725906695686bd0aa5c50aa25aa
```

## 剩余真机验收

必须在 Even App + G2 真机上确认：

1. 插件能在“我的插件”稳定显示。
2. 进入后手机网页五个主菜单可点击。
3. G2 首页能显示；如果不能显示，设置页/状态栏应报告“G2 启动页创建失败”。
4. 设置页“定位自检”能触发系统定位授权并返回粗略位置。
5. 视觉识别拍照后手机历史有缩略图和“查看采集照片”。
6. G2 拍照后预览能显示；若 SDK 返回 `imageSizeInvalid/sendFailed`，日志会记录失败并回退文本确认。
7. 退出/关闭 Even App 后再次进入，历史记录仍存在。
8. 呼叫天禄非交易问题带定位上下文；交易问题不带定位。
9. G2 PCM 只在首页创建成功后启动。
10. 交易白名单价格页仍只显示 BTC / ETH / SOL / BNB / DOGE。

## 上架判断

- 本地测试构建：通过。
- Store Release：仍不批准，必须完成真机验收后再判断。
