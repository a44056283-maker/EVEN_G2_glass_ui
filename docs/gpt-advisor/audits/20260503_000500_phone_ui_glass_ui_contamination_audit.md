# 手机 UI 与眼镜 UI 污染审计报告

**审计时间**：2026-05-03 00:05
**审计人**：Claude Code
**任务名称**：P0-UI-RECOVER-001

---

## A. 手机网页 UI 当前由哪些文件渲染

- `index.html` - HTML 结构（4个书签按钮）
- `src/style.css` - 样式和 `data-active-bookmark` 选择器
- `src/main.ts` - 主逻辑、导航控制和 `renderBookmarkChrome()`

## B. G2 眼镜端 UI 当前由哪些文件渲染

- `src/glass/glassScreens.ts` - 眼镜屏幕文本渲染（只用于 G2）
- `src/display.ts` - G2 显示逻辑
- `src/glass/GlassRenderer.ts` - 眼镜渲染器
- `src/main.ts` 中 `createGlassRenderer().show()` 调用

## C. 是否存在同一个数组/状态同时驱动手机网页和 G2 眼镜主菜单

**是**。`g2Bookmarks` 数组（main.ts:91-95）同时驱动：
- 手机网页的 `#bookmark-kicker` 显示（`书签 1 / 3`）
- G2 眼镜的主导航
- 书签按钮的高亮状态

但 `g2Bookmarks` 只有 3 项（vision, voice, trading），不包括 'openclaw'（设置）。

## D. 是否存在 getSelectableControls / bookmarks / controls 同时被手机 UI 和 Glass UI 使用

**是**。`getSelectableControls()` (main.ts:3201) 包含：
- `'capture-button'`, `'voice-button'`, `'trading-button'`, `'openclaw-button'`
- 以及其他操作按钮

此函数用于 R1 戒指导航，但也影响手机 UI 的某些逻辑。

## E. 为什么线上页面仍显示四个书签

**根因**：`index.html` 中仍有 4 个书签按钮，但 `g2Bookmarks` 数组只有 3 个项目。

当点击"设置"按钮时：
1. `enterSettingsPage()` 被调用
2. **问题**：该函数只更新眼镜端 Glass UI (`activeGlassPage = 'diagnostics'`)，没有更新手机的 `app.dataset.activeBookmark`
3. 导致 CSS 规则 `#app[data-active-bookmark="openclaw"] > .config-panel` 永远不触发
4. 配置面板不显示，但眼镜端显示诊断页

## F. 为什么手机网页里出现了视觉、交易、设置按钮混排

**根因**：`data-active-bookmark` 没有正确更新，导致：
1. 点击不同书签时，CSS 显示/隐藏面板的逻辑错乱
2. `renderBookmarkChrome()` 使用 `g2Bookmarks` 来决定按钮高亮，但 openclaw 不在其中
3. 书签卡片显示的信息与实际激活的面板不匹配

## G. 哪些改动应该回滚或隔离

**隔离方案**：
1. `enterSettingsPage()` 需要同时更新 `app.dataset.activeBookmark = 'openclaw'`
2. `renderBookmarkChrome()` 需要特殊处理 openclaw 情况
3. 手机网页导航（4项）和 G2 眼镜导航（3项）使用不同数据源

## H. 最小修复方案

### 已执行的修复

**修复 1：更新 enterSettingsPage 函数**
- 位置：`main.ts` 第 2843-2859 行
- 修改：添加 `app.dataset.activeBookmark = 'openclaw'` 和 `renderBookmarkChrome()`

**修复 2：更新 renderBookmarkChrome 函数**
- 位置：`main.ts` 第 2693-2721 行
- 修改：当 `data-active-bookmark="openclaw"` 时，显示"书签 4 / 4"并高亮 openclaw 按钮

## I. 修复后的行为

### 手机网页 UI
- 点击"设置"书签 → `app.dataset.activeBookmark = 'openclaw'`
- CSS 触发 `#app[data-active-bookmark="openclaw"] > .config-panel { display: grid }`
- 配置面板正确显示
- 书签卡片显示"书签 4 / 4"、"设置"、"连接诊断、权限自检、配置保存"
- openclaw 按钮正确高亮

### G2 眼镜端 UI
- 点击"设置"书签 → 眼镜显示诊断页
- `g2Bookmarks` 仍只有 3 项（vision, voice, trading）
- G2 主菜单仍只显示三大模块
- **不受手机 UI 修改影响**

---

## 修改文件列表

| 文件 | 修改内容 |
|------|---------|
| `apps/evenhub-plugin/src/main.ts` | `enterSettingsPage()` 添加 `app.dataset.activeBookmark = 'openclaw'` 和 `renderBookmarkChrome()` 调用 |
| `apps/evenhub-plugin/src/main.ts` | `renderBookmarkChrome()` 添加 openclaw 特殊处理 |

## 未解决问题

1. 手机网页和 G2 眼镜仍共享 `g2Bookmarks` 数组（建议后续完全分离）
2. 需要重新构建才能生效：`npm run build`

## 下一步建议

1. 执行 `npm run build` 和 `npm run pack:g2` 构建新 EHPK
2. 真机测试：点击"设置"书签，验证配置面板是否正确显示
3. 真机测试：G2 眼镜主菜单是否仍只有三大模块
4. 考虑文件级隔离：创建 `phoneNavigation.ts` 和 `glassNavigation.ts`
