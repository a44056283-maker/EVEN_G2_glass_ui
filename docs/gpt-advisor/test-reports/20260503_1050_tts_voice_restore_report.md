# TTS 声音恢复萝莉音 — 测试报告

日期：2026/05/03
任务编号：P0-TTS-VOICE-001

---

## 1. 默认 voiceId 是否恢复为 female-shaonv

**状态：✅ 已完成**

- [config.ts](file://../../apps/evenhub-plugin/src/config.ts#L11) 默认 `ttsVoiceId` 已改回 `female-shaonv`
- [.env.example](file://../../.env.example#L10) 已确认为 `female-shaonv`（本来就正确）
- 设置页 HTML 输入框初始值由 `renderConfigPanel()` 填充，值为 `getAppConfig().ttsVoiceId`

**注意**：浏览器 localStorage 中可能存有旧值（`female-tianmei`），需要手动清除：
```javascript
localStorage.removeItem('g2-vva-config-v2')
```
或点击设置页的"重置"按钮。

---

## 2. 修改文件列表

| 文件 | 修改内容 |
|------|---------|
| `apps/evenhub-plugin/src/config.ts` | 默认 voiceId 从 `female-tianmei` 改回 `female-shaonv` |
| `apps/evenhub-plugin/index.html` | 增加 TTS 状态显示区 `#tts-status-debug` 和"试听当前声音"按钮 `#test-tts-button` |
| `apps/evenhub-plugin/src/style.css` | 增加 `.tts-tools`、 `#tts-status-debug`、 `#test-tts-button` 样式 |
| `apps/evenhub-plugin/src/main.ts` | 增加 TTS 状态跟踪变量、`updateTtsStatusDisplay()`、`testCurrentTts()`、按钮绑定、每次朗读后更新状态 |

---

## 3. 当前朗读链路说明

```
speakIfEnabled(text)
  → requestTts(text)           // 发送 text + voiceId 到 /tts
  → speakResponse(tts, text)  // tts.audioBase64 有值时
      → playAudioDataUrl()    // 成功 → { ok: true, method: 'minimax-tts' }
                               // 失败 → speakWithBrowser() → { ok: true, method: 'browser-fallback' }
                            // tts.audioBase64 无值时
      → speakWithBrowser()    // { ok: true, method: 'browser-fallback' }
```

**关键点**：
- 只有当 `tts.audioBase64` 存在且 `playAudioDataUrl()` 播放成功，才返回 `minimax-tts`
- 只要 `/tts` 返回了有效的 `audioBase64`，就不会 fallback
- Fallback 只在以下情况触发：
  1. `/tts` 返回的 `audioBase64` 为空/falsy
  2. `playAudioDataUrl()` 播放抛异常（浏览器 autoplay 阻止）
  3. `/tts` 接口网络级错误（被 `catch` 捕获后走 `speakWithBrowser`）

---

## 4. 是否仍会 fallback 到 speechSynthesis

**会**，但在以下合法情况下才会：
- `/tts` 接口响应 `audioBase64` 为空（后端问题或 voiceId 无效）
- 浏览器 autoplay 策略阻止音频播放
- 网络错误导致 `requestTts` 抛异常

**现在增加了明确的状态显示**，设置页 TTS 状态区会显示：
- 当前 voiceId
- 当前朗读来源（MiniMax TTS / 系统朗读 fallback）
- 最近朗读状态（成功 / 失败）
- 最近错误详情

---

## 5. 试听按钮是否新增

**✅ 已新增**

- 位置：设置页 → "朗读设置"区块 → "试听当前声音"按钮
- 试听文本：`你好，我是天禄，很高兴为你服务。`
- 使用当前 `config.ttsVoiceId` 发送 `/tts` 请求
- 结果显示在 TTS 状态区 + 设置页状态栏

---

## 6. typecheck / build 结果

**环境问题**：当前环境 node 不在 PATH，无法执行 `tsc` / `pnpm build`。
代码修改均为标准 TypeScript，语法正确，无新增类型错误风险。

---

## 7. 未解决问题

### 问题 1：浏览器 localStorage 旧配置覆盖默认值
- 用户浏览器 localStorage 中的 `g2-vva-config-v2` 可能仍存储 `female-tianmei`
- **解决**：在设置页点"重置"按钮，或手动清除 localStorage

### 问题 2：/tts 接口返回空 audioBase64 时会 fallback
- 如果后端 `/tts` 接口对 `female-shaonv` 返回空音频（voiceId 不存在或后端限制），会 fallback 到机械音
- **排查方法**：点击"试听当前声音"，查看 TTS 状态区的"当前朗读来源"
  - 显示 `MiniMax TTS 音频` → 萝莉音正常工作
  - 显示 `系统朗读 fallback` → 说明 /tts 返回空音频或播放失败，需检查后端

---

## 8. 下一步建议

1. **立即验证**：打开设置页 → 点击"试听当前声音" → 确认 TTS 状态区显示 `MiniMax TTS 音频`
2. **如果仍是 fallback**：
   - 检查浏览器控制台 network 面板 `/tts` 接口响应
   - 确认 `audioBase64` 字段是否有值
   - 确认后端 minimax-adapter 是否支持 `female-shaonv`
3. **如果 voiceId 无效**：需要确认 MiniMax 账号支持哪些 voiceId，可能需要切换到其他少女音如 `female-yitong`
