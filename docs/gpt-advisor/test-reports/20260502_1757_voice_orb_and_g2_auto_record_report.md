# 20260502_1757 Voice Orb And G2 Auto Record Report

## 本轮范围

本轮只处理呼叫天禄入口的交互与显示：

1. 手机/网页端把语音圆形图案改成真实可按压录音按钮。
2. 下方语音面板标题从“语音对话”改为“手动文本对话”。
3. 眼镜端进入“呼叫天禄”后自动启动 G2 录音。
4. R1 单击在录音中用于停止录音并进入识别。

未修改视觉识别、交易接口、OpenCLAW 真实链路、ASR 后端策略。

## 修改文件

- `apps/evenhub-plugin/index.html`
- `apps/evenhub-plugin/src/main.ts`
- `apps/evenhub-plugin/src/style.css`
- `apps/evenhub-plugin/src/glass/glassScreens.ts`

## 行为变化

### 手机/网页端

- 新增 `#voice-orb-action` 圆形语音按钮。
- 圆形按钮支持按住开始录音、松开停止录音。
- 顶部书签区仍保留“按住语音对话”入口。
- 两个入口共用同一套 hold-to-talk 逻辑。
- 录音中两个按钮都会进入 `is-recording` 状态，并显示按压/录音反馈。

### G2 眼镜端

- 进入“呼叫天禄”后，如果存在 Even Bridge，直接调用 `startHoldToTalkSession({ strategy: 'g2-pcm', mode: 'asr' })`。
- G2 显示录音态。
- R1 单击会走既有 `handleVoiceR1Intent`，停止录音并进入识别。
- G2 菜单文案改为“进入后自动录音 / R1 单触结束识别”。

## 验证结果

```bash
npm run typecheck
npm run build
npm run pack:g2
```

结果：全部通过。

EHPK:

`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`

SHA256:

`f2f8e58ce97c545e011f57a88dce0c6d0ce68797dd8ead98c51f744802f39db5`

## 仍需真机验证

1. 在普通网页环境按住圆形按钮是否能调用手机/耳机麦克风。
2. 在 Even 插件模式进入“呼叫天禄”后，G2 是否立即进入录音态。
3. R1 单击是否能停止 G2 录音并触发 ASR。
4. 录音按钮反馈是否足够明显。

