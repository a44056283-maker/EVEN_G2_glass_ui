# 2026-05-02 22:10 视觉提问与历史追问补丁报告

## 本轮范围

只修复视觉识别与呼叫天禄之间的“看图问题上下文”和“二次追问”缺口。

未修改：

- R1 相机状态机
- G2 麦克风 / ASR
- OpenCLAW
- 交易机器人接口
- 后端 `/vision` 路由

## 修改文件

- `apps/evenhub-plugin/index.html`
- `apps/evenhub-plugin/src/main.ts`
- `apps/evenhub-plugin/src/history.ts`
- `apps/evenhub-plugin/src/style.css`

## 功能变化

1. 视觉识别模块新增“看图问题”输入框。
   - 拍照或相册选图时，如果该输入框有内容，会作为 `/vision` 的 `prompt` 一起发送给 MiniMax 图文识别。
   - 例如：`这是什么？`、`帮我读一下文字`、`这个界面有什么风险？`

2. 呼叫天禄触发视觉意图时继续复用现有链路。
   - `tryAutoCaptureFromVoice(prompt, transcript)` 已经把语音转文字内容传给 `runCaptureFlow(prompt, ...)`。
   - 本轮让 `runCaptureFlow` 统一使用 `effectivePrompt`，保证语音问题不会丢失。

3. 视觉结果支持二次追问。
   - 新增 `askVisionFollowup(question)`。
   - 会把最近视觉描述、上次看图问题、上次视觉回答作为上下文发给 `askAssistant()`。
   - 回答会显示在视觉结果区、G2 reply 页面，并写入视觉历史。

4. 历史记录新增“继续追问”按钮。
   - 呼叫天禄回答区下方新增“继续追问”输入框。
   - 视觉历史：点击后回到视觉书签，并聚焦看图追问输入框。
   - 语音/交易等历史：点击后回到呼叫天禄，并聚焦手动文本输入框。

5. 保留“重播朗读”。
   - 历史项现在同时有“重播朗读”和“继续追问”。

## 验证结果

```text
npm run typecheck 通过
npm run build     通过
npm run pack:g2   通过
```

## EHPK

```text
apps/evenhub-plugin/g2-vision-voice-assistant.ehpk
```

SHA256:

```text
13ba88bba0d344a6fb07918168053dfa8235ee872d1cf800399842e9d3c96d26
```

## 真机验收建议

1. 进入视觉识别，在“看图问题”输入框写：`这是什么？`
2. 点击“直接拍照”或“相册选图”。
3. 确认识别结果不是单纯描述图片，而是围绕问题回答。
4. 点击视觉历史中的“继续追问”，输入：`它有什么需要注意的？`
5. 确认新回答会结合上一张图片和上一次回答。
6. 在呼叫天禄中说：`你好天禄，帮我看一下这是什么`
7. 确认自动进入视觉流程后，语音问题被带入 `/vision`。

## 未解决问题

- 真机上“语音看图意图 -> 自动拍照”仍取决于当前相机流/拍照链路是否可用。
- 本轮不处理真实 ASR 精度和 R1 拍照控制。
