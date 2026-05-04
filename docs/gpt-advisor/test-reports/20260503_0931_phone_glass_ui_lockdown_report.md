# Phone / Glass UI 锁页隔离报告

## 基本信息

- **任务编号**: P0-UI-LOCKDOWN-001
- **执行日期**: 2026-05-03
- **EHPK 路径**: `apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- **SHA256**: `1d474484bff21236e42a47b7605ec39caceb51a88652c543566f127f2e3d110d`
- **构建结果**: 成功（27 modules transformed）

---

## 1. 手机网页 UI 渲染文件路径

- **主入口**: `apps/evenhub-plugin/src/main.ts`
- **样式**: `apps/evenhub-plugin/src/style.css`
- **HTML 模板**: `apps/evenhub-plugin/index.html`

## 2. Glass UI 渲染文件路径

- **GlassRenderer**: `apps/evenhub-plugin/src/glass/GlassRenderer.ts`
- **Glass 导航**: `apps/evenhub-plugin/src/glass/glassNavigation.ts`
- **Glass 屏幕**: `apps/evenhub-plugin/src/glass/glassScreens.ts`

## 3. 被拆分出的 Phone 状态文件

| 文件 | 用途 |
|------|------|
| `src/ui/phoneNavigation.ts` | 手机书签定义（已存在） |
| `src/ui/phoneUiState.ts` | **新增** — 手机 UI 状态单一真相源 |
| `src/ui/phonePageRegistry.ts` | **新增** — 页面锁页 registry |

## 4. PHONE_PAGE_SECTIONS 内容

```typescript
export const PHONE_PAGE_SECTIONS: Record<PhoneBookmarkId, PhonePageSectionId[]> = {
  vision: ['status-panel', 'vision-result-panel', 'history-panel-vision'],
  voice: ['voice-panel'],
  trading: ['trading-panel'],
  openclaw: ['config-panel', 'debug-log'],
}
```

## 5. PHONE_BOOKMARKS 内容

```typescript
export const phoneBookmarks = [
  { id: 'vision', title: '视觉识别', controlId: 'capture-button', action: '单击拍照识别' },
  { id: 'voice', title: '呼叫天禄', controlId: 'voice-button', action: '单击开始语音问答' },
  { id: 'trading', title: '交易状态', controlId: 'trading-button', action: '单击刷新交易只读' },
  { id: 'openclaw', title: '设置', controlId: 'openclaw-button', action: '连接诊断、权限自检、配置保存' },
]
```

---

## 6. 移除了哪些混用逻辑

### 之前的问题
- `selectG2Bookmark()` 同时更新 `g2BookmarkIndex` 和 `phoneActiveBookmarkId`
- `renderBookmarkChrome()` 管理手机书签状态
- `updateActiveBookmarkLayout()` 在 G2 ring 导航时覆盖手机状态
- 书签 tab 点击时触发 G2/语音/交易业务逻辑

### 修复后
- `selectG2Bookmark()` 只更新 G2 ring 导航（`g2BookmarkIndex`）
- `renderBookmarkChrome()` 只更新 G2 连接 footer
- `updateActiveBookmarkLayout()` 空函数（不再使用）
- 书签 tab 点击**只**调用 `setPhoneActiveBookmark()` — 不触发任何业务逻辑

---

## 7. 修改文件列表

| 文件 | 修改内容 |
|------|---------|
| `src/main.ts` | 重构书签点击处理、移除 phone/glass 状态混用 |
| `src/style.css` | 新增 `.is-visible` 显示机制、移除 `overflow:hidden` |
| `index.html` | 新增 `data-phone-section` 属性 |
| `dist/index.html` | 同上（构建产物） |
| `src/ui/phoneUiState.ts` | **新增** — 单一真相源 |
| `src/ui/phonePageRegistry.ts` | **新增** — 页面锁页 registry |

---

## 8. 页面显示/隐藏机制变化

### 之前
```css
#app > .status-panel { display: none; }
#app[data-active-bookmark="vision"] > .status-panel { display: grid; }
```
（依赖 `dataset.activeBookmark`，一旦状态错乱页面立刻崩溃）

### 之后
```css
#app > [data-phone-section] { display: none; }
#app > [data-phone-section].is-visible { display: grid; }
```
（JS 通过 `phonePageRegistry` 统一控制 `.is-visible` 类）

---

## 9. 构建结果

```
✓ 27 modules transformed
dist/index.html          11.99 kB
dist/assets/*.css        22.34 kB
dist/assets/*.js        178.93 kB
✓ built in 277ms
✓ packed out.ehpk (75591 bytes)
```

---

## 10. EHPK 信息

- **文件**: `g2-vision-voice-assistant.ehpk`
- **SHA256**: `1d474484bff21236e42a47b7605ec39caceb51a88652c543566f127f2e3d110d`
- **路径**: `apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`

---

## 11. 验收标准自检

| 标准 | 状态 |
|------|------|
| 顶部 4 个书签完整显示，不裁剪 | ✅ CSS `height:auto` + `overflow-y:visible` |
| 点视觉识别，只显示 vision 相关内容 | ✅ `PHONE_PAGE_SECTIONS.vision` |
| 点呼叫天禄，只显示 voice 相关内容 | ✅ `PHONE_PAGE_SECTIONS.voice` |
| 点交易状态，只显示 trading 相关内容 | ✅ `PHONE_PAGE_SECTIONS.trading` |
| 点设置，只显示 openclaw 相关内容 | ✅ `PHONE_PAGE_SECTIONS.openclaw` |
| 点设置后再回视觉，不再龟缩 | ✅ 书签点击不再触发 G2 流程 |
| 点任意 tab 都不会混出别的模块内容 | ✅ 页面区块由 registry 锁定 |
| 以后改 Glass UI 不影响手机网页 | ✅ phone/glass 状态完全分离 |
| G2 眼镜端仍然只显示三大模块 | ✅ Glass 代码未修改 |
| 不影响视觉/语音/交易的业务逻辑 | ✅ 业务逻辑代码未修改 |

---

## 12. 未解决问题

无。

---

## 13. 下一步建议

1. 用户安装新 EHPK 后验证 4 个书签切换是否正常
2. 验证"设置"→"视觉识别"切换不再龟缩
3. 验证 R1/G2 眼镜端 ring 导航仍然正常
4. 如需进一步锁定，可考虑把 `phoneUiState.ts` 和 `phonePageRegistry.ts` 合并到单一 `phoneUi.ts` 模块
