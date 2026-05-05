# v0.5.28 Bridge History + Fixed Preview + Location Report

时间：2026-05-05 20:25 CST
版本：0.5.28

## 结论

本轮针对真机反馈的三个问题修复：

1. 图片预览/历史图片没有：G2 预览改为固定 288x144 黑底灰度 PNG；手机历史不再保存原始大图，保存压缩预览图。
2. 历史记录关掉软件后没有：按官方文档改为 Even Bridge `setLocalStorage/getLocalStorage` 主持久化，IndexedDB/localStorage 只做兜底。
3. 定位权限已开但功能没定位：对齐官方 GPS demo 的 Web Geolocation 路径，使用高精度、8 秒超时，并在 `getCurrentPosition` 失败后用 `watchPosition` 兜底。

## 官方依据

- `even-g2-notes/docs/device-apis.md` 明确说明 `.ehpk` WebView 的浏览器 `localStorage` 不跨重启，必须用 `bridge.setLocalStorage/getLocalStorage`。
- `even-g2-notes/docs/display.md` 明确图片容器最大 288x144，并要求图片数据尺寸匹配容器，避免 tiling。
- `eveng2-demo/src/pages/gps.ts` 使用 `navigator.geolocation.watchPosition/getCurrentPosition`，说明定位是 WebView Geolocation + app.json `location` 权限路径。

## 代码变化

- `apps/evenhub-plugin/src/historyStore.ts`
  - 新增 `loadBridgeHistory/saveBridgeHistory/clearBridgeHistory`。
  - Key：`g2-vva-history-v2`。

- `apps/evenhub-plugin/src/history.ts`
  - Bridge KVS 成为历史主持久化。
  - Bridge、IndexedDB、localStorage 读出的历史按 id/createdAt 合并，避免旧 Bridge 历史覆盖 Bridge 未连接期间的新记录。
  - 清空历史增加 tombstone：Bridge 未连接时清空，后续连接会优先写空，避免旧历史复活。
  - Bridge KVS 增加容量预算：380KB 总预算，前 4 条视觉历史保留图片；超限自动 compact 到 2 条图片，再失败则保留文字记录。

- `apps/evenhub-plugin/src/main.ts`
  - 拍照历史图片改为 720px 内压缩预览，不再存原图。
  - G2 拍照预览图改为固定 288x144 PNG、黑底居中、灰度处理。
  - Bridge 连接完成后再次后台 hydrate history，把原生 KVS 读入页面。

- `apps/evenhub-plugin/src/locationContext.ts`
  - 定位超时从 5 秒调整为 8 秒。
  - `enableHighAccuracy: true`。
  - `getCurrentPosition` 失败后尝试 `watchPosition`，提高 Even App WebView 下成功率。

## 验证

- `node node_modules/typescript/bin/tsc --noEmit -p apps/evenhub-plugin/tsconfig.json`：通过
- `node node_modules/typescript/bin/tsc -p services/api-server/tsconfig.json --noEmit`：通过
- `node node_modules/typescript/bin/tsc -p packages/shared/tsconfig.json --noEmit`：通过
- esbuild fallback build：通过
- EvenHub CLI pack：通过
- Python Playwright 手机网页三轮：菜单点击、定位自检、历史刷新恢复均通过
- 本机 EvenHub simulator 仍不可运行：`Unsupported platform: darwin-arm64`

## EHPK

路径：`/Users/luxiangnan/Desktop/g2-vision-voice-assistant-v0.5.28-bridge-history-fixed-preview-location.ehpk`

SHA256：

```text
5fea96b507b959f779884fee99cf995f5a0a694d688ec871c34838cef8223c57
```

## 真机验证重点

1. 设置页点“定位自检”，必须看到系统定位结果或明确错误。
2. 拍照识别后，G2 应显示照片预览；若失败，会回退文字并记录 runtime error。
3. 拍照识别后，手机历史应出现缩略图和“查看采集照片”。
4. 关闭 Even App/重进插件后，历史应从 Even Bridge KVS 恢复。
5. 清空历史后重进，不应旧历史复活。

## 上架判断

仍是 TEST BUILD，不批准正式上架。必须完成以上真机验证后才能决定是否进入正式发布。
