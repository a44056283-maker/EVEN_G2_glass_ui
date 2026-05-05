# v0.5.26 Safe Boot + 手机点击/G2 边界轮测报告

时间：2026-05-05 19:10

## 结论

- 本地自动化轮测通过：手机插件网页主菜单 5 项可切换。
- G2 Bridge 失败被 Safe Boot 捕获，不再阻塞手机端 UI。
- 本报告不是三轮真实手机 + 真实 G2 佩戴验收；真机仍需上传 EHPK 后确认。

## 本轮修复

1. 修复 esbuild 兜底打包时 `import.meta.env.VITE_*` 首屏崩溃风险。
2. 手机主菜单只保留早期事件代理，移除重复 tab click 绑定。
3. 手机主菜单增加 `pointerup` / `touchend` 兜底，适配 Even WebView。
4. 清除不存在的 `settings-button`，统一为真实 DOM 中的 `openclaw-button`。
5. `app.json` 增加 `location` 权限声明。
6. 权限自检增加 `geolocation` 能力检测和定位请求结果。
7. `GlassRenderer` 检查 SDK 返回码：启动页非 success、页面重建 false、文本更新 false 均视为失败。
8. 移除前端 `VITE_G2_SESSION_TOKEN` / WebSocket token query / Authorization 注入风险。
9. G2 后台文本更新增加 `.catch()`，避免返回 false 后形成未处理 rejection。

## 自动化轮测

### 手机插件网页

本地 dist mock 轮测结果：

```json
{
  "ok": true,
  "results": [
    "capture-button:vision->vision",
    "voice-button:voice->voice",
    "trading-button:trading->trading",
    "openclaw-button:openclaw->openclaw",
    "history-button:history->history"
  ],
  "active": "history"
}
```

### G2 Bridge 失败隔离

mock 环境中 Flutter handler 不可用，`createStartUpPageContainer` 返回失败、`rebuildPageContainer` 返回失败。

结果：

- Safe Boot 捕获 `G2 startup page create failed`
- Safe Boot 捕获 `G2 rebuild page failed: home`
- 手机菜单仍继续通过轮测

## 编译与打包

- `node node_modules/typescript/bin/tsc --noEmit -p apps/evenhub-plugin/tsconfig.json`：通过
- `node node_modules/typescript/bin/tsc -p services/api-server/tsconfig.json --noEmit`：通过
- `node node_modules/typescript/bin/tsc -p packages/shared/tsconfig.json --noEmit`：通过
- esbuild 兜底构建：通过
- EvenHub CLI pack：通过
- dist 安全扫描：未发现 `VITE_G2_SESSION_TOKEN`、`Authorization`、`token=`

## 产物

- EHPK：`/Users/luxiangnan/Desktop/g2-vision-voice-assistant-v0.5.26-safeboot-full-candidate.ehpk`
- SHA256：`4486d50493a062982830e1b445c2aad5f02e6458dec4434059c8cf9eccaad12b`

## 真机验收重点

1. 安装后插件能在“我的插件”显示。
2. 进入插件后，手机端五个主菜单都能点动。
3. 子菜单按钮能点动。
4. G2 首页显示成功；若 G2 显示失败，手机端仍可继续操作。
5. 设置页权限自检能看到 `geolocation` 和定位结果。
6. 拍照后历史记录出现视觉历史，包含缩略图/查看采集照片入口。
