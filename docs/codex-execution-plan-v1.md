# Codex 执行台账 v1

依据：`../天禄 G2 运维助手 - Codex 执行手册 v1.txt`

目标产品：`天禄 G2 运维助手`

## 总原则

1. 只做一个 Even Hub 插件和一个后端桥接服务，不再拆散成多个软件。
2. 手机网页 UI 和 G2 眼镜 UI 分离。
3. G2 眼镜端只通过 `GlassRenderer` 渲染 576 x 288 container UI。
4. G2 麦克风主链路是 `audioControl(true)` -> `audioEvent.audioPcm` -> WebSocket -> 后端 ASR。
5. R1 相机控制必须建立在手机端已预热相机的前提下。
6. 交易模块第一版只读，不执行真实交易动作。
7. 每个阶段只解决本阶段问题，不把相机、语音、OpenCLAW、UI 混在一起调。

## 当前阶段

当前进入：`阶段 1 - GlassRenderer 与 TL OS 眼镜 HUD`

阶段 0 已完成：

- `AGENTS.md`
- `docs/current-state.md`
- `docs/architecture.md`
- `docs/glass-ui-design.md`
- `docs/acceptance-checklist.md`
- `docs/codex-execution-plan-v1.md`

## 最近一次阶段构建记录

时间：2026-05-02

范围：

- 阶段 1：`GlassRenderer` 回到稳定单 TextContainer 主路径。
- 阶段 1：`glassScreens.ts` 改为 TL OS 短行 HUD 页面。
- 阶段 2：`debug_input` 事件格式改为 `Envelope / Type / Source / State`。
- 阶段 2：第四书签临时作为设备诊断/输入调试入口。

验证：

- `npm --workspace apps/evenhub-plugin run typecheck`：通过。
- `npm --workspace apps/evenhub-plugin run build`：通过。
- `npm --workspace apps/evenhub-plugin run pack`：通过。

产物：

- `apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- `apps/evenhub-plugin/g2-视觉-语音助手.ehpk`

SHA256：

```text
fe750765815c16818a53b187addc121452e48bc9e10a00bf4909c7030dadbab3
```

## 最近一次布局修正记录

时间：2026-05-02

问题：

- 手机网页把主页、子菜单、状态、语音、交易、设置、历史、调试日志全部堆在一屏，主次不清。
- 隐藏区域里的按钮仍可能被 R1/键盘选择到，导致控制焦点混乱。

修正：

- 主页保留四个一级入口：视觉识别、天禄问答、交易状态、设置。
- 点击一级入口后，只显示该入口对应的二级模块。
- 视觉：显示二级动作 + 识别流程状态。
- 语音：显示二级动作 + 语音问答 + 历史。
- 交易：显示二级动作 + 交易只读。
- 设置：显示二级动作 + 配置/诊断/调试。
- R1/键盘选择过滤不可见按钮，避免跳到隐藏子模块。

验证：

- `npm --workspace apps/evenhub-plugin run typecheck`：通过。
- `npm --workspace apps/evenhub-plugin run build`：通过。
- `npm --workspace apps/evenhub-plugin run pack`：通过。

产物：

- `apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- `apps/evenhub-plugin/g2-视觉-语音助手.ehpk`

SHA256：

```text
db5c4db2283cdab9f7d61146fc56a7b21faed955b6ff816dd4709415d0738720
```

## 首页/子版块层级修正记录

时间：2026-05-02

问题：

- 一级菜单点击后直接执行动作，不符合“主页 -> 子版块”的结构。
- 页面仍容易把子模块堆在首页下方，主次不清。

修正：

- 一级入口只负责切换到对应版块，不再直接拍照/刷新。
- 视觉识别：进入视觉子版块后，再点二级动作“拍照识别/直接拍照”。
- 天禄问答：进入语音子版块后，再点二级动作。
- 交易状态：进入交易子版块后，再点“刷新只读/白名单价格/风险摘要”。
- 设置：进入设置/诊断子版块。
- R1/键盘选择继续过滤不可见按钮。

验证：

- `npm --workspace apps/evenhub-plugin run typecheck`：通过。
- `npm --workspace apps/evenhub-plugin run build`：通过。
- `npm --workspace apps/evenhub-plugin run pack`：通过。

产物 SHA256：

```text
af1652cb52497ec312fa0ae8c46047f8e325ad03b4829b4b43cebadfd5336520
```

## 阶段顺序

### 阶段 0：仓库审计与工程规则

状态：已完成。

结果：

- 已确认当前后端目录是 `services/api-server`，对应手册中的 `services/g2-bridge`。
- 已记录当前前端入口、G2 渲染、输入、相机、语音、后端接口和权限状态。
- 已标记 `SpeechRecognition`、浏览器麦克风、OpenCLAW 后端 endpoint、手机 DOM 等历史路径。

### 阶段 1：GlassRenderer 与 TL OS HUD

目标：

- 先让眼镜端 UI 稳定、清晰、可读。
- 不继续把手机网页 UI 同步到眼镜端。
- 不使用未经真机验证的复杂多容器。

本阶段交付：

- 整理 `GlassRenderer.ts`，保留稳定单 TextContainer 主路径。
- 整理 `glassScreens.ts`，按 TL OS 页面样张输出短行 HUD。
- 补齐 `risk_alert`、`diagnostics` 等规划页面。
- 保证每屏 8-10 行以内，避免标签换行导致第二行不可见。

验收：

- 眼镜首页不空白、不重叠。
- 首页、视觉、语音、交易、回复、设置、诊断都有清晰页面。
- 文案短行化，不再出现手机网页式大段说明。

### 阶段 2：R1/G2 输入调试

目标：

- 先确定 R1 的 envelope/type/source。
- 不先猜 R1 事件来源。

验收：

- `debug_input` 显示单击、双击、上滑、下滑。
- 记录真机 source，用于后续相机控制。

### 阶段 3：R1 相机控制

目标：

- 手机端负责相机授权和预热。
- R1 只负责截帧、确认发送、重拍、取消。

验收：

- 网页相机恢复可用。
- `vision_ready` 下 R1 单击立即拍照。
- `vision_captured` 下 R1 双击发送。

### 阶段 4：G2 Mic Probe

目标：

- 只验证 G2 PCM 是否到达。
- 不接真实 ASR，不接 OpenCLAW。

验收：

- G2 显示 PCM bytes/chunks。
- 不再触发浏览器麦克风权限错误。

### 阶段 5：ASR Adapter

目标：

- `probe/mock-asr/asr` 三模式清晰。
- 未配置真实 ASR 时明确显示 not-configured。

### 阶段 6：/ask + OpenCLAW + 交易只读

目标：

- 问答接交易状态 fallback。
- OpenCLAW timeout 不阻塞 G2 回复。

### 阶段 7：视觉增强

目标：

- OCR、屏幕读取、bot-screen、观察模式。

### 阶段 8：设备诊断与 Runbook

目标：

- 所有失败都有诊断页和处理步骤。

### 阶段 9：测试与打包

目标：

- build、pack、EHPK、SHA256、真机验收清单。
