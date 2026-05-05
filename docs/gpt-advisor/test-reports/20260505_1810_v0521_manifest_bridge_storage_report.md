# v0.5.21 Manifest 权限与 Bridge 持久化修复报告

时间：2026-05-05 18:10

## 结论

用户截图显示手机端设置页没有 v0.5.20 的定位诊断区块，同时历史记录在关闭软件后丢失。结合官方/社区开源文件复查，本轮修复两个根因：

1. `app.json` 漏声明 `location` 权限，Even App 不会给插件 WebView 授权定位。
2. `.ehpk` WebView 内普通 `localStorage` 不保证跨重启持久化，历史记录必须使用 Even Bridge 的 `setLocalStorage/getLocalStorage`。

本版本状态：允许上传测试，不批准正式上架。

## GitHub / 本地开源依据

- `eveng2-demo/app.json` 使用 `{ "name": "location", "desc": "GPS demo: test geolocation" }`。
- `eveng2-demo/src/pages/gps.ts` 使用 `navigator.geolocation.watchPosition`，并在权限拒绝时提示 Host App 需要把 location 授权给 WebView。
- `even-g2-notes/docs/device-apis.md` 明确说明 `.ehpk` WebView 的 browser `localStorage` 不会在 App 或眼镜重启后保留，需要使用 `bridge.setLocalStorage/getLocalStorage`。
- Even SDK README 明确提供 `setLocalStorage(key, value)` 和 `getLocalStorage(key)`。

## 变更

- 版本号：0.5.21
- `app.json`
  - 新增 `location` 权限。
  - `min_sdk_version` 提升到 `0.0.10`，与当前项目安装的 Even SDK 版本对齐。
- 历史记录
  - 新增 Even Bridge 持久化主存储：`bridge.getLocalStorage` / `bridge.setLocalStorage`。
  - 启动后先从 Bridge 读取历史，再合并 IndexedDB/localStorage 旧数据。
  - 新写入历史时优先写 Bridge，同时保留 IndexedDB/localStorage 作为兜底。
  - 清空历史时同步清空 Bridge 历史 key。
  - Bridge 存储过大时保留文字和缩略图，避免整条历史保存失败。

## 对用户反馈的判断

- 设置页没有定位诊断：若截图来自 v0.5.20，说明手机端实际加载的不是新包页面，或者开发者平台/Even App 缓存了旧版本；同时 v0.5.20 也确实缺少 `location` manifest 权限。
- 历史关软件后消失：不是用户操作问题，普通 `localStorage/IndexedDB` 在 Even `.ehpk` WebView 里不可靠，需改为 Bridge 存储。
- 图片预览：官方 SDK 支持 `ImageContainerProperty + updateImageRawData`，但真机是否显示取决于 Even App/SDK 图片管线。当前仍保留 v0.5.19 的灰度低分辨率 SDK 路径。

## 验证

- `node node_modules/typescript/bin/tsc --noEmit -p apps/evenhub-plugin/tsconfig.json`：通过
- `node node_modules/typescript/bin/tsc -p packages/shared/tsconfig.json --noEmit`：通过
- `node node_modules/typescript/bin/tsc -p services/api-server/tsconfig.json --noEmit`：通过
- `node node_modules/typescript/bin/tsc -p packages/vision-adapter/tsconfig.json --noEmit`：通过
- `node ../../node_modules/typescript/bin/tsc -p tsconfig.json`：通过
- `esbuild` 前端构建：通过
- EvenHub CLI pack：通过

## 产物

- EHPK：`/Users/luxiangnan/Desktop/g2-vision-voice-assistant-v0.5.21-manifest-bridge-storage-test.ehpk`
- SHA256：`651dfda72defd045113efb16a7215099949a6c53ea0d0503580509090b816f8f`

## 发布注意

建议在开发者平台删除旧测试包或至少确认只保留并安装 v0.5.21。若 Even App 仍加载旧页面，说明平台或手机端有旧 EHPK 缓存，需要卸载插件、清理开发者平台旧版本后重新安装。

