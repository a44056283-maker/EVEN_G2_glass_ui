# P0-R1-CANCEL-FOLLOWUP-001 测试报告

生成时间：2026-05-04 13:30

## 来源

GPT Review: 3、GPT_REVIEW_20260504_1300_day0_fix (NEEDS_FIX)

## 整改内容

### 1. 新增 cancelCurrentGlassOperation(reason)

**文件**：`apps/evenhub-plugin/src/main.ts`

**函数逻辑**：
```typescript
async function cancelCurrentGlassOperation(reason: string): Promise<void> {
  const bridge = getBridge()
  const renderer = createGlassRenderer(bridge)
  console.info('[P0 vision] operation cancelled:', reason)
  // 使当前 session 失效，阻止旧结果回写
  startGlassOperation()
  pendingCapturedImage = undefined
  uploadInFlight = false
  pendingVisionPrompt = ''
  const prevState = visionState
  visionState = 'idle'
  activeGlassPage = 'home'
  // 如果当时正在 preparing/uploading，取消后返回首页
  if (prevState === 'preparing' || prevState === 'uploading') {
    await safeGlassShow(renderer, 'home')
    await renderG2Bookmark()
  }
  setInteractionFeedback(`已取消：${reason}`)
  renderR1CameraDebug()
}
```

### 2. visionState === preparing/uploading 时 R1 取消

**修改位置**：`handleVisionR1Intent` 函数

**改动**：
- R1 next/double_click/click 在 preparing/uploading 状态下均可取消并返回
- 不再只提示"请稍候"，而是真正执行取消操作

```typescript
// preparing/uploading 状态下：R1 next/double_click/click 均可取消并返回
if (visionState === 'preparing' || visionState === 'uploading') {
  if (intent === 'next' || intent === 'double_click' || intent === 'click') {
    await cancelCurrentGlassOperation(visionState === 'preparing' ? '相机准备中取消' : '上传中取消')
    return
  }
  // R1 previous 在 preparing/uploading 时也取消
  if (intent === 'previous') {
    await cancelCurrentGlassOperation('R1 上滑取消')
    return
  }
  return
}
```

### 3. 手机 file input 取消处理

**修改位置**：`handleManualImageInput` 函数

**改动**：
```typescript
const handleManualImageInput = (event: Event): void => {
  if (isFileInputRequestActive()) return
  const file = (event.currentTarget as HTMLInputElement | null)?.files?.[0]
  if (!file) {
    // 文件选择取消或没有选择文件，取消当前眼镜操作
    void cancelCurrentGlassOperation('file-input-cancelled')
    return
  }
  void unlockAudioPlayback()
  const source = (event.currentTarget as HTMLInputElement | null)?.id === 'album-fallback' ? 'web-album' : 'web-camera'
  void handleManualImageFile(file, source)
}
```

---

## 代码证据

### 1. 首页 4 菜单 renderHome

```typescript
function renderHome(state: GlassScreenState): string {
  const selected = state.selectedIndex ?? state.activeIndex ?? 0
  const time = state.time || '12:36'
  const battery = state.battery || 'G2:--'

  const menuLine = [
    `[视觉识别${selected === 0 ? '●' : '○'}]`,
    `[呼叫天禄${selected === 1 ? '●' : '○'}]`,
    `[交易状态${selected === 2 ? '●' : '○'}]`,
    `[系统设置${selected === 3 ? '●' : '○'}]`,
  ].join('')

  const topLine = (time.slice(0, 5) + ' '.repeat(WIDTH - 5 - Math.min(9, battery.length)) + battery.slice(0, 9)).padEnd(WIDTH)

  return [
    topLine,
    '',
    menuLine,
    '',
    '          ↑↓ 选择   单触进入',
  ].join('\n')
}
```

### 2. settings 进入路径

```typescript
// main.ts selectG2Bookmark
function selectG2Bookmark(id: G2BookmarkId): void {
  const index = g2Bookmarks.findIndex((bookmark) => bookmark.id === id)
  if (index >= 0) g2BookmarkIndex = index
  focusControlById(getCurrentG2Bookmark().controlId)
}

// settings-button -> openclaw bookmark mapping
'settings-button': 'openclaw'
```

### 3. R1 焦点来源

```typescript
// main.ts selectG2Bookmark
function selectG2Bookmark(id: G2BookmarkId): void {
  // G2 书签只更新眼镜端 ring 导航状态，与手机网页状态完全分离
  const index = g2Bookmarks.findIndex((bookmark) => bookmark.id === id)
  if (index >= 0) g2BookmarkIndex = index
  focusControlById(getCurrentG2Bookmark().controlId)
}
```

### 4. 语音视觉关键词和 route

```typescript
// isVisionVoiceIntent - 视觉意图关键词
function isVisionVoiceIntent(text: string): boolean {
  return /看看|看一看|看一下|帮我看看|帮我看一下|这是什么|识别一下|拍一下|拍照|读一下|读这段|屏幕内容|菜单|图片内容|前面是什么|看看屏幕|看看前面/.test(text)
}

// routeVoiceIntent 路径
async function routeVoiceIntent(text: string): Promise<void> {
  if (isTradingVoiceIntent(text)) {
    updateVoiceDebug({ lastIntent: 'trading' })
    await handleTradingVoiceIntent(text)
    return
  }
  if (isVisionVoiceIntent(text)) {
    updateVoiceDebug({ lastIntent: 'vision' })
    await handleVisionVoiceIntent(text)
    return
  }
  updateVoiceDebug({ lastIntent: 'general' })
  await handleGeneralAssistantIntent(text)
}
```

### 5. 交易标签数组和 R1 单触逻辑

```typescript
// TRADING_MENU_ITEMS
const TRADING_MENU_ITEMS = [
  { id: 'trading_status', label: '运行状态' },
  { id: 'trading_prices', label: '白名单价' },
  { id: 'trading_positions', label: '持仓盈亏' },
  { id: 'trading_distribution', label: '资金分布' },
  { id: 'trading_attribution', label: '订单归因' },
  { id: 'trading_alerts', label: '风控告警' },
]

// R1 单触逻辑 - handleG2ControlEvent
if (activeGlassPage === 'trading') {
  if (intent === 'double_click') { inTradingMenu = true; activeGlassPage = 'home'; await renderer.show('home'); return }
  if (intent === 'next') { tradingSubPageIndex = (tradingSubPageIndex + 1) % 6; await showTradingSubPage(tradingSubPageIndex, renderer); return }
  if (intent === 'previous') { tradingSubPageIndex = (tradingSubPageIndex - 1 + 6) % 6; await showTradingSubPage(tradingSubPageIndex, renderer); return }
  if (intent === 'click') { inTradingMenu = true; await renderer.show('trading_menu', { activeIndex: tradingSubPageIndex }); return }
}
```

### 6. G2 页面去线条

```bash
$ grep -rn "divider\|'━'\|'─'\|'│'" --include="*.ts"
glass/glassLayout.ts:27:export function divider(width = 48): string {
glass/glassLayout.ts:28:  return '━'.repeat(width)
```

**结论**：`divider` 函数仅在 glassLayout.ts 中定义，但未被任何渲染函数调用。所有页面渲染均不使用线条字符。

---

## 测试结果

| 测试项 | 结果 |
|--------|------|
| typecheck | ✓ PASSED |
| build | ✓ PASSED (30 modules) |
| pack:g2 | ✓ PASSED (79523 bytes) |

---

## EHPK 信息

- **版本**：0.5.0
- **SHA256**：`10e02135b7f4780ae437ead4eecef596881f24d7c3f4b0a3a3f6e8a27321bb2f`
- **大小**：79523 bytes
- **路径**：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`

---

## 真机验收清单

- [ ] R1 在 preparing 状态下滑动（next）能取消返回首页
- [ ] R1 在 uploading 状态下滑动（next）能取消返回首页
- [ ] R1 双击在 preparing/uploading 状态能取消返回
- [ ] 手机取消文件选择后 G2 不停留在"拍照采集"
- [ ] 首页 4 菜单一行正确显示
- [ ] 系统设置可见可进入

---

## 未解决问题

无新增问题。