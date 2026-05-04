# 下一步任务

更新时间：2026-05-03


## 2026-05-03 09:31 锁页隔离（P0-UI-LOCKDOWN-001）

### Phone UI / Glass UI 架构级隔离

状态：**已完成代码修改和打包**，待真机验收。

验证步骤：
1. 安装新 EHPK：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
2. SHA256：`1d474484bff21236e42a47b7605ec39caceb51a88652c543566f127f2e3d110d`
3. 顶部 4 个书签完整可见，不裁剪
4. 点视觉识别 → 只显示状态进度条 + 视觉结果 + 视觉历史
5. 点呼叫天禄 → 只显示语音面板
6. 点交易状态 → 只显示交易面板
7. 点设置 → 只显示配置面板 + 连接诊断，**不再龟缩**
8. 从设置切回视觉识别 → 正常显示，不再串页
9. G2 眼镜端 ring 导航仍只显示"视觉识别 / 呼叫天禄 / 交易状态"三项
10. 业务逻辑未受影响：视觉/语音/交易功能正常

已修改文件：
- `src/main.ts` — 重构书签点击处理
- `src/style.css` — 新增 `.is-visible` 显示机制
- `index.html` / `dist/index.html` — 新增 `data-phone-section`
- `src/ui/phoneUiState.ts` — **新增**
- `src/ui/phonePageRegistry.ts` — **新增**

报告：`docs/gpt-advisor/test-reports/20260503_0931_phone_glass_ui_lockdown_report.md`


## 2026-05-03 09:43 电量显示修复（P0-BATTERY-001）

### G2 / R1 电量多来源缓存 + 设置页调试区

状态：**已完成代码修改和打包**，待真机验收。

验证步骤：
1. 安装新 EHPK：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
2. SHA256：`2d6b2f0d08642ebfc97e9254e842ce0859ac8f9d8a0810564b4a004d01f12987`
3. 打开页面，顶部不再长期显示 `--%` 或 `加载中`（从缓存恢复或实时更新）
4. 进入设置页，查看"设备电量"调试区显示 G2/R1 电量、来源、更新时间
5. 点击"刷新电量"按钮重新获取电量
6. 连接 G2/R1 后，顶部实时显示真实电量值

已修改文件：
- `src/main.ts` — 引入电池模块，初始化缓存，应用到 UI
- `src/style.css` — 新增 `.battery-tools` 样式
- `index.html` / `dist/index.html` — 新增电量调试面板
- `src/device/batteryCache.ts` — **新增**
- `src/device/extractBatterySnapshot.ts` — **新增**

报告：`docs/gpt-advisor/test-reports/20260503_0943_battery_display_fix_report.md`


## 2026-05-03 全天完工计划

明天按根目录计划执行：

```text
20260503_天禄G2运维助手全天完工计划.md
```

核心顺序：

1. 08:30 启动检查。
2. 09:00-11:00 呼叫天禄语音闭环。
3. 11:00-12:00 语音触发视觉识别。
4. 13:00-15:00 交易状态公网实时只读页面。
5. 15:00-16:30 G2 四书签 UI 收敛。
6. 16:30-17:30 设备诊断与 R1 电量处理。
7. 17:30-18:30 第一轮真机测试。
8. 19:30-21:00 回归修复。
9. 21:00-22:00 最终打包。
10. 22:00-23:30 最终真机验收。

明天不要做实时视频识别、场景记忆、自动交易控制、整套 UI 重写。

## 2026-05-03 00:35 本轮修复（P0-PHONE-UI-RECOVER-002）

### 手机网页 UI 与 Glass UI 导航隔离

状态：**已完成构建打包**，待真机验收。

验证步骤：
1. 安装新 EHPK：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
2. SHA256：`2dab644238737685fb2ae019a5ec990b6eb91d5983beba6d334586a1c21a700e`
3. 打开手机插件网页，顶部 4 个书签 tab 正常显示，不被裁剪
4. 点击"设置"书签，显示"书签 4 / 4"和配置面板
5. G2 眼镜端主菜单仍只显示"视觉识别 / 呼叫天禄 / 交易状态"三项

未解决问题：
- `g2Bookmarks` 仍保留在 main.ts 中，建议后续统一从 `glassNavigation.ts` 导入
- Glass UI 尚未使用 `glassNavigation.ts` 导航数据，当前眼镜端三大模块逻辑未受影响但数据未统一

## 当前执行顺序

### 当前新升级工作流

已读取上级计划包：

```text
/Users/luxiangnan/Desktop/EVEN G2视觉和语音对讲系统/tianlu_g2_module_plans_codex_prompts
```

正式工作流已写入：

```text
docs/gpt-advisor/MODULE_UPGRADE_WORKFLOW.md
```

当前优先级调整为：

1. P0：修复呼叫天禄语音闭环、结果展示、历史记录和意图路由。
2. P0：语音“看一看/这是什么”触发视觉识别。
3. P0：拍照结果朗读、G2 显示、重播。
4. P1：交易状态分页与语音交易问答复用 7 项摘要 + MiniMax 评测。
5. P1：设备诊断中心和 R1 电量状态解释。
6. P1：Glass UI TL-OS 分层优化。

### P1：R1 电量真机验证

状态：已修复解析路径，等待真机确认。

结果：

- 已避免 R1 被 `isWearing` 等字段误归类为 G2。
- 已扩展 R1 电量字段识别：`r1Battery`、`ringBattery`、`r1BatteryLevel`、`ringBatteryLevel`、`remoteBattery`、`controllerBattery`、`r1Power`、`ringPower` 等。
- 已支持嵌套设备状态和字符串百分比。
- 新 EHPK：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- SHA256：`9c556cc213500b4d7368a2dc7c67a4c179e35765141fb63f0a2f77e6de4772a4`

下一步：

- [ ] 真机刷新确认顶部是否显示 R1 电量。
- [ ] 如果仍显示“未上报”，抓取 `[G2 device status]`、`[G2 battery update]`、`[G2 battery fallback]` 日志，确认 Even App 是否上报 R1 电量字段。
- [ ] 若 SDK 不上报 R1 电量，在设置诊断中明确显示“R1 电量未由 Even App 上报”，不要伪造数值。

下一轮补丁任务：

```text
docs/gpt-advisor/patch-requests/20260502_2048_r0_003_voice_answer_display_and_intent_fix.md
```

本轮只修“呼叫天禄”，不碰 R1 视觉相机状态机。

### 已完成补丁：交易状态公网实时控制台升级

状态：已完成，等待真机刷新确认。

结果：

- 白名单价格只显示 `BTC/ETH/SOL/BNB/DOGE`。
- 价格源改为 `https://console.tianlu2026.org/api/prices/realtime`。
- 交易状态统一读取 `https://console.tianlu2026.org`，不再读取局域网 `192.168.13.48:9099`。
- 新增只读聚合接口：`/glasses/api/summary`、`/glasses/api/prices`、`/glasses/api/positions`、`/glasses/api/l5`、`/glasses/api/pair/:pair`、`/glasses/api/alerts`。
- 交易页新增交易数据源、白名单价格、机器人在线、整体持仓评测、真实持仓交易对、M1-M5/L5 资金流、真实订单归因等分区。
- 不再把持仓交易对混入白名单价格。
- 不再展示 `edict_backup`、`real_report_*`、`MEMORY.md` 等备份路径作为交易数据。
- 新 EHPK：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- SHA256：`e41804b4f054a13f7cd72cdc64ebcd59370f2a3afd940edd321c74951a70dba2`

下一步：

- [ ] 真机刷新交易状态页，确认不再出现备份报告路径。
- [ ] 真机确认白名单价格显示 BNB/BTC/DOGE/ETH/SOL。
- [ ] 继续把交易眼镜端拆成分页：总览 / 白名单价格 / 持仓评测 / L5归因。

### P0-001：网页视觉识别闭环

状态：已完成，用户真机反馈可拍照、上传并识别。

目标：

```text
视觉识别 -> 拍照/选图 -> 图片压缩 -> POST /vision -> 显示结果 -> 历史记录
```

验收：

- [x] 手机网页点击“视觉识别”只进入视觉二级页。
- [x] 点击拍照/选择图片走网页识别闭环，不再走 R1 状态机。
- [x] 图片压缩后不会触发 `Request body is too large` 的风险已降低。
- [x] `/vision` 公网接口已用项目 cover 图测试返回 200。
- [x] 网页新增稳定结果面板。
- [x] 结果写入历史记录。
- [x] 手机真机 Even App WebView 实测。

### P0-002：R1 相机控制与眼镜菜单确认

状态：已改为 R1 单触两步流程，待真机确认。

目标：

```text
首页 R1 选择视觉识别
-> R1 单击打开手机拍照入口
-> 手机端完成拍照后进入 captured
-> R1 再次单击发送
-> R1 上滑重拍
-> R1 下滑取消
```

验收：

- [ ] R1 在首页上下切换一级菜单。
- [ ] R1 单击“视觉识别”进入视觉下一级页。
- [ ] R1 单击可以打开手机拍照入口。
- [ ] 手机拍照返回后 `pendingCapturedImage=yes`。
- [ ] captured 状态下 R1 单击 600ms 内只提示，再次单击上传。
- [ ] 上传日志显示 `lastUploadSource=r1-single-confirm`。
- [ ] R1 上滑可以重拍。
- [ ] R1 下滑可以取消。

### P0-003：设置诊断真实化

状态：已完成，待真机确认。

目标：

```text
设置书签 -> 一键扫描 / 一键修复 / 权限自检
眼镜诊断页中文显示并支持 R1 单击扫描、上滑修复、下滑返回
```

验收：

- [x] 设置书签下方不再显示“语音问 CLAW / 读取天禄记忆”等旧占位。
- [x] 网页设置面板有一键扫描和一键修复。
- [x] 眼镜诊断页为中文。
- [x] R1 单击触发扫描。
- [x] R1 上滑触发修复。
- [x] 打包版本 `0.2.5`。

### R0-003a：呼叫天禄 G2 麦克风采集入口

状态：已扩展为 R0-003 按住说话 / G2 PCM / 本地 Whisper ASR / 意图路由，待真机验收音频采集。

目标：

```text
点击“呼叫天禄 / 语音对话”
-> 手机按住说话或 R1 单触开始/结束
-> 调用 bridge.audioControl(true)
-> 收到 audioEvent.audioPcm
-> /audio?mode=asr 接收 PCM
-> 发送 end_of_speech
-> 本地 Whisper 返回 final_transcript
-> final_transcript 进入 handleTranscript
-> routeVoiceIntent 分流到视觉/交易/普通问答
```

验收：

- [ ] G2 显示语音录音状态。
- [ ] Voice Debug 显示 `audioControlCalled: true`。
- [ ] Voice Debug 显示 `wsStatus: open`。
- [ ] 对着眼镜说话后 `totalBytes/chunks` 增长。
- [ ] 松开或 R1 再次单触后发送 `end_of_speech`。
- [x] 本地 Whisper ASR 服务已启动并托管。
- [x] 后端 `/transcribe` 已能返回真实转写文本。
- [ ] `/audio?mode=asr` 收到 G2 PCM 后返回 `final_transcript`。
- [ ] `final_transcript` 进入 `handleTranscript`。
- [ ] “看一看/这是什么”进入视觉意图。
- [ ] “交易机器人运行如何/今天收益”进入交易意图。
- [ ] 如果 5 秒没有 PCM，显示 `未收到 G2 麦克风数据`，不假装成功。
- [ ] 不默认调用 `SpeechRecognition` 或浏览器 `getUserMedia({ audio:true })`。

下一步分支：

- 如果手机或 G2 录音能上传：继续完善语音意图和播报。
- 如果手机/G2 都无法采集音频：继续查 Even App WebView 麦克风权限、`audioControl(true)` 和 `audioEvent.audioPcm`。

### P1：G2 眼镜显示视觉结果

### P1：交易状态 AI 评测真机回归

目标：

```text
公网 console 实时数据 -> 六项摘要 -> MiniMax-M2.7 / 本地规则评测 -> 手机网页与眼镜显示
```

验收：

- [x] `/trading/overview` 返回至少 6 项摘要。
- [x] `/glasses/api/summary` 返回 `aiAssessment`。
- [x] MiniMax-M2.7 可生成实时短评。
- [ ] 真机交易页显示“六项摘要”和“MiniMax-M2.7 持仓评测”。
- [x] 语音问交易状态时复用同一套 AI 评测结果，而不是旧 mock 简答。

### P0：呼叫天禄普通问答质量

目标：

```text
语音/文字问题 -> /ask -> MiniMax 正常回答 -> 页面和眼镜直接显示
```

验收：

- [x] 拦截“我已收到问题 / 会显示在这里 / Telegram”等占位回答。
- [ ] 普通问题不再返回空泛占位。
- [ ] 回答区域不显示 Voice Debug。
- [ ] 语音历史最多保留最近 15 条。

### 2026-05-02 21:46 当前修复后验收

- [ ] 安装最新 `g2-vision-voice-assistant.ehpk`，测试普通问题是否直接回答，不再显示“收到问题/稍后显示”。
- [ ] 测试呼叫天禄回答后网页是否仍停留在呼叫天禄书签，不再自动跳回首页第一菜单。
- [ ] 确认 Voice Debug 默认不显示在回答下方。
- [ ] 若仍出现占位回答，记录用户原问题和 `/ask` 返回 provider，继续收窄后端回答路径。
- [ ] “看一看 / 这是什么”命中视觉意图后切到视觉流程。
- [ ] 真机测试按住说话 10-20 秒，确认按钮时长显示连续、松开后录音大小与时长合理。
- [ ] 若仍出现 “ASR 没有返回文字”，记录 Voice Debug 的 `sizeBytes / durationMs / provider / mimeType`。
- [ ] 交易页继续修：只显示 `https://console.tianlu2026.org` 的实时只读数据，移除备份文件路径和历史报告列表。
- [ ] 真机测试视觉识别“看图问题”输入框，确认 `/vision` 回答围绕用户问题。
- [ ] 真机测试“呼叫天禄：帮我看一下这是什么”，确认语音问题能带入视觉识别结果。
- [ ] 真机测试视觉历史“继续追问”，确认回答能结合上一张图片上下文。

下一步：

- 优先真机刷新交易页。
- 然后把“呼叫天禄”里的交易问答接到同一套 `/trading/overview` AI 评测。

目标：

```text
/vision 结果 -> GlassRenderer reply 页面 -> G2 可读显示
```

验收：

- [ ] 眼镜端不空白。
- [ ] 结果不溢出。
- [ ] 失败时显示明确错误摘要。

### P2：R1 输入调试真机记录

目标：

```text
R1 单击/双击/上滑/下滑 -> envelope/type/source/state
```

验收：

- [ ] 单击日志。
- [ ] 双击日志。
- [ ] 上滑日志。
- [ ] 下滑日志。
- [ ] G2 镜腿事件日志。

### P3：R1 控制相机

目标：

```text
进入视觉页预热相机 -> R1 单击截帧 -> R1 再次单击发送 -> R1 下滑取消
```

验收：

- [ ] 第一次 R1 单击就能拍照。
- [ ] R1 再次单击能发送当前图片。
- [ ] R1 下滑能取消。

## 暂缓任务

- 真实 ASR。
- OpenCLAW 深度联调。
- 交易实盘接口接入。
- 观察模式。
- 自动交易动作。
- 复杂眼镜端图形 UI。
