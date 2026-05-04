# 2026-05-02 22:45 Glass HUD UI 重塑测试报告

## 本轮目标

根据 `tianlu_g2_all_glass手机端UI重塑/tianlu_g2_all_glass_text_previews.md`，重塑 Even G2 眼镜端单 TextContainer 文本 HUD。

本轮只改眼镜端 UI 文案与布局，不改语音、视觉、交易业务主链路。

## 修改文件

- `apps/evenhub-plugin/src/glass/glassScreens.ts`
- `apps/evenhub-plugin/src/glass/glassText.ts`
- `apps/evenhub-plugin/app.json`
- `apps/evenhub-plugin/package.json`
- `package-lock.json`

## 改造内容

### 1. 主页 Home

改为 TL-OS 风格：

- `TL-OS // TIANLU`
- 居中标题：天禄 G2 运维助手
- 三列主模块：视觉识别 / 呼叫天禄 / 交易状态
- 使用 `● / ○` 表示当前选中项
- 底部显示 `G2 ONLINE / R1 READY / LINK OK`

### 2. 视觉识别

新增 TL-CAM 风格：

- START / READY / CAPTURED / SENDING
- 相机就绪、已锁定画面、上传识别中都有独立页面
- 文案改为居中和短句，适配 576x288

### 3. 呼叫天禄

新增 TL-AI 风格：

- VOICE 菜单
- RECORDING 录音中
- FINALIZING 识别中
- HEARD 听到内容
- ANSWER 天禄回复
- NO PCM 无麦克风数据
- PCM PROBE 麦克风诊断

### 4. 交易状态

新增 TL-BOT 风格：

- STATUS 运行状态
- RISK 风险告警
- 指标采用左右对齐 `label/value` 形式

### 5. 设置与诊断

新增 TL-SYS 风格：

- SETTINGS 设置
- DIAG 诊断中心
- ERROR 错误页

## 技术说明

- 继续使用单 TextContainer 渲染，保持 Even G2 兼容性。
- 保留 GlassRenderer 技术路线，不依赖 HTML/CSS。
- `sanitizeForG2Text` 不再把 `━━━━━━━━` 强制替换成 `-`，以保留 GPT 设计稿中的 HUD 分隔线。
- 每屏内容控制在约 10-11 行，避免眼镜端堆满。

## 验证结果

```text
npm run typecheck: PASS
npm run build: PASS
npm run pack:g2: PASS
```

## EHPK

```text
apps/evenhub-plugin/g2-vision-voice-assistant.ehpk
```

SHA256:

```text
bcf480227b764ab8db03c401472a8426207ba361ed75e9e032851e0b0d92d2d8
```

## 待真机确认

- G2 是否能正常显示 `━━━━━━━━` 分隔线。如果真机不支持，应回退为 ASCII `----------------------`。
- 主页三列模块在真实眼镜端是否换行正常。
- 呼叫天禄、视觉识别、交易状态、设置四个书签是否不再混显示。
- R1 选中状态是否能跟随 `● / ○` 正确切换。

## 下一步

明天按根目录 `20260503_天禄G2运维助手全天完工计划.md` 继续：

1. 先稳定呼叫天禄语音闭环。
2. 再校验这版 Glass HUD 真机显示。
3. 如 HUD 分隔线不兼容，回退分隔线但保留布局结构。
