# 手机 UI 恢复与导航隔离审计报告

**审计时间**：2026-05-03 00:35
**审计人**：Claude Code
**任务名称**：P0-PHONE-UI-RECOVER-002

---

## 1. 本轮是否只修手机网页 UI 与导航隔离

**是**。本轮专注于修复手机网页 UI 的 bookmark 导航与 G2 眼镜 ring 导航的交叉污染问题，并建立两个独立的导航数据源。

---

## 2. 手机网页 UI 实际渲染文件路径

| 文件 | 职责 |
|------|------|
| `apps/evenhub-plugin/src/main.ts` | 手机网页 DOM 事件处理、bookmark 点击、`renderBookmarkChrome()`、`updateActiveBookmarkLayout()`、`app.dataset.activeBookmark` 状态管理 |
| `apps/evenhub-plugin/src/style.css` | 手机网页 CSS 样式、`data-active-bookmark` 选择器、面板显示/隐藏 |
| `apps/evenhub-plugin/dist/index.html` | 手机网页 HTML 结构（4个 bookmark 按钮、面板 section） |
| `apps/evenhub-plugin/src/ui/phoneNavigation.ts` | **新增** — 手机网页导航配置（4项：vision/voice/trading/openclaw） |

---

## 3. G2 Glass UI 实际渲染文件路径

| 文件 | 职责 |
|------|------|
| `apps/evenhub-plugin/src/glass/GlassRenderer.ts` | G2 显示引擎，通过 EvenHub SDK 创建/rebuild PageContainer |
| `apps/evenhub-plugin/src/glass/glassScreens.ts` | G2 屏幕状态渲染（home/vision_preparing/voice_idle/trading_status 等） |
| `apps/evenhub-plugin/src/glass/glassNavigation.ts` | **新增** — G2 眼镜端导航配置（3项：vision/voice/trading） |
| `apps/evenhub-plugin/src/display.ts` | G2 HUD 文本格式化（`formatForG2`） |

---

## 4. phoneNavigation.ts 内容摘要

```typescript
// apps/evenhub-plugin/src/ui/phoneNavigation.ts
export type PhoneBookmarkId = 'vision' | 'voice' | 'trading' | 'openclaw' | 'diagnostics' | 'history' | 'debug'

export const phoneBookmarks: PhoneBookmark[] = [
  { id: 'vision',    title: '视觉识别', controlId: 'capture-button',   action: '单击拍照识别',        cssValue: 'vision'   },
  { id: 'voice',     title: '呼叫天禄', controlId: 'voice-button',      action: '单击开始语音问答',    cssValue: 'voice'    },
  { id: 'trading',   title: '交易状态', controlId: 'trading-button',     action: '单击刷新交易只读',    cssValue: 'trading'  },
  { id: 'openclaw',  title: '设置',     controlId: 'openclaw-button',   action: '连接诊断、权限自检、配置保存', cssValue: 'openclaw' },
]
```

---

## 5. glassNavigation.ts 内容摘要

```typescript
// apps/evenhub-plugin/src/glass/glassNavigation.ts
export type GlassBookmarkId = 'vision' | 'voice' | 'trading'

export const glassBookmarks: GlassBookmark[] = [
  { id: 'vision',  title: '视觉识别', controlId: 'capture-button', action: '单击拍照识别'      },
  { id: 'voice',   title: '呼叫天禄', controlId: 'voice-button',   action: '单击开始语音问答'  },
  { id: 'trading', title: '交易状态', controlId: 'trading-button', action: '单击刷新交易只读'  },
]
```

---

## 6. 修改文件列表

| 文件 | 修改内容 |
|------|---------|
| `apps/evenhub-plugin/src/ui/phoneNavigation.ts` | **新增** — 手机网页导航配置 |
| `apps/evenhub-plugin/src/glass/glassNavigation.ts` | **新增** — G2 眼镜端导航配置 |
| `apps/evenhub-plugin/src/main.ts` | ① 导入 `PhoneBookmarkId`, `phoneBookmarks`, `getPhoneBookmarkById`；② 新增 `phoneActiveBookmarkId` 状态变量；③ `renderBookmarkChrome()` 改用 `phoneBookmarks`；④ `updateActiveBookmarkLayout()` 不覆盖 phone-only bookmark；⑤ `getBookmarkCardDescription()` 支持 `PhoneBookmarkId`；⑥ `enterSettingsPage()` 设置 `phoneActiveBookmarkId = 'openclaw'` |

---

## 7. 修复了哪些混用问题

### 问题 1：`g2Bookmarks`（3项）同时驱动手机网页和 G2 眼镜端

**根因**：`g2Bookmarks` 数组只有 3 项，但手机网页有 4 个 bookmark 按钮。`selectG2Bookmark('openclaw')` 无效（不在数组中），导致点击"设置"后 `g2BookmarkIndex` 不更新，但 `updateActiveBookmarkLayout()` 会用旧的 `g2BookmarkIndex` 覆盖 `app.dataset.activeBookmark`。

**修复**：引入 `phoneActiveBookmarkId` 独立状态，`updateActiveBookmarkLayout()` 只在当前是 g2Ids（vision/voice/trading）之一时同步 ring 导航结果，不覆盖 'openclaw'。

### 问题 2：`renderBookmarkChrome()` 用 `g2Bookmarks` 显示书签编号

**根因**：显示"书签 1 / 3"而不是"书签 4 / 4"，因为使用 `g2BookmarkIndex` 和 `g2Bookmarks.length`。

**修复**：改用 `phoneBookmarks` 和 `phoneActiveBookmarkId` 计算编号。

### 问题 3：`getBookmarkCardDescription()` 不支持 openclaw

**修复**：将参数类型从 `G2BookmarkId` 扩展为 `PhoneBookmarkId`，添加 openclaw 分支。

---

## 8. 视觉 tab 最终内容

- 进度条：待命 / 拍照采集 / 压缩图片 / 上传后端 / AI 识别 / 语音朗读
- 视觉结果面板（`.vision-result-panel`）：识别结果文本、Camera/R1 Debug 信息
- 追问图片输入框和按钮
- 视觉历史面板（`.history-panel-vision`）
- 操作按钮：`直接拍照` / `相册选图`（`.bookmark-action-row-vision`）

---

## 9. 呼叫天禄 tab 最终内容

- 语音 orb 按钮（按住说话）
- 手动文本输入框和发送按钮
- Voice Debug 面板
- 语音历史面板（`.history-panel-voice`）

---

## 10. 交易状态 tab 最终内容

- 交易只读标题 + 刷新按钮
- 风险摘要、白名单价格、持仓评测按钮（`.bookmark-action-row-trading`）
- 交易历史面板（`.history-panel-trading`）

---

## 11. 设置/诊断 tab 最终内容

- 配置面板（`.config-panel`）：后端地址、朗读声音 ID、录音时长、自动朗读/自动监听开关
- 连接与权限诊断工具（`#permission-tools`）
- 一键扫描 / 一键修复 / 权限自检 / 一键请求权限 按钮
- 设置历史面板（`.history-panel-settings`）

---

## 12. typecheck / build / pack 结果

```
✓ tsc --noEmit           — 通过，无错误
✓ vite build             — 25 modules transformed, 179.10 kB JS
✓ evenhub pack           — g2-vision-voice-assistant.ehpk (75572 bytes)
```

---

## 13. EHPK 路径和 SHA256

- **路径**：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- **大小**：74 KB (75572 bytes)
- **SHA256**：`2dab644238737685fb2ae019a5ec990b6eb91d5983beba6d334586a1c21a700e`

---

## 14. 未解决问题

1. **`g2Bookmarks` 仍保留在 main.ts 中**：与 `glassBookmarks` 重复，未来应统一从 `glassNavigation.ts` 导入。当前 `g2Bookmarks` 仍被 `selectG2Bookmark()` / `getCurrentG2Bookmark()` 使用，但不影响手机 UI 逻辑。
2. **Glass UI 尚未使用 `glassBookmarks`**：`GlassRenderer` / `glassScreens.ts` 仍通过硬编码字符串渲染眼镜 HUD，未引用 `glassNavigation.ts`。眼镜端三大模块逻辑未受影响，但导航数据未统一。
3. **CSS 样式未做 Phone/Glass 作用域隔离**：当前 Phone UI 和 Glass UI 共享 `style.css`，但 Glass UI 主要通过 SDK 渲染文本，不依赖 DOM CSS。风险低，但建议后续分离。

---

## 15. 下一步建议

1. **重命名 `g2Bookmarks` 为 `glassBookmarks`** 并统一从 `glassNavigation.ts` 导入，消除重复定义
2. **确认眼镜端 Glass UI 不受影响**：安装新 EHPK 后，验证 G2 主菜单仍只显示"视觉识别 / 呼叫天禄 / 交易状态"三项
3. **确认手机网页 bookmark 导航正常**：安装新 EHPK 后，验证点击"设置"书签显示"书签 4 / 4"和配置面板
4. **考虑文件级 CSS 隔离**：如果后续继续修改 Glass UI，建议将 Phone UI CSS 和 Glass UI CSS 放在不同文件
