# 2026-05-02 23:09 · G2 眼镜首页三模块收敛报告

## 本轮目标

按用户最新要求，G2 眼镜首页只保留三个主版块：

1. 视觉识别
2. 呼叫天禄
3. 交易状态

设置、连接诊断、OpenCLAW 调试等功能继续保留在手机插件页面；手机端触发时仍可同步诊断页面到眼镜，但不再作为 G2 首页主书签。

## 修改文件

- `apps/evenhub-plugin/src/main.ts`
- `apps/evenhub-plugin/src/glass/glassScreens.ts`
- `apps/evenhub-plugin/app.json`
- `apps/evenhub-plugin/package.json`
- `package-lock.json`

## 关键修改

- `G2BookmarkId` 从 `vision | voice | trading | openclaw` 收敛为 `vision | voice | trading`。
- `g2Bookmarks` 删除第 4 个“设置”书签。
- G2 首页初始文本删除“设置”。
- Glass 首页 `renderHome()` 的 tabs 限制为 3 个，并删除 fallback 中的“设置”。
- 手机端设置/诊断按钮不再调用 `selectG2Bookmark('openclaw')`，改为直接进入 `enterSettingsPage()`。
- 删除当前 G2 书签为 `openclaw` 时的手动文本分流逻辑，避免三模块首页外的幽灵状态。

## 保留能力

- 手机插件端的设置、诊断、OpenCLAW 相关按钮仍保留。
- 手机端触发设置/诊断时，仍可通过 `enterSettingsPage()` 同步显示到眼镜。
- 本轮未改动视觉识别、呼叫天禄、交易状态业务链路。

## 验证结果

- `npm run typecheck`：通过
- `npm run build`：通过
- `npm run pack:g2`：通过

## EHPK

- 路径：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- 版本：`0.3.9`
- SHA256：`729d91392bd52d9039b863c344bc9ded4bef221fb57a03b21c3dc20a81c3fef4`

## 下一步建议

真机扫描新版 EHPK，确认 G2 首页只显示 3 个主版块；若手机插件仍显示设置/诊断，这是符合当前设计的。
