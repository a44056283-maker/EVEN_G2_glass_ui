# 天禄 G2 运维助手定时进度日志

更新时间：2026-05-02

用途：记录每一个开发工作块的目标、修改、测试结果、阻塞点和下一步。以后 Codex 执行、GPT 桌面版审计、真机反馈都统一写到这里，避免工程方向再次散乱。

## 记录规则

1. 每完成一个明确工作块，追加一条日志。
2. 每次真机测试后，必须追加“现象 / 判断 / 下一步”。
3. 每次打包 EHPK 后，必须记录包路径和 SHA256。
4. 每次 GPT 审计后，必须记录审计结论和采纳项。
5. 不在日志中写入 API Key、Token、密码、私钥等敏感信息。

## 固定记录模板

```md
### YYYY-MM-DD HH:mm

- 阶段：
- 目标：
- 修改文件：
- 验证命令：
- 结果：
- 阻塞：
- 下一步：
- 负责人：Codex / GPT / 用户
```

## 今日主线

今天只按一个主线推进：

```text
先修网页视觉识别闭环
再修 G2 眼镜结果显示
再记录 R1 输入真实事件
再做 R1 控制拍照与发送
```

今日不再同时混修：

```text
真实 ASR
OpenCLAW 深度联调
交易实盘接口
观察模式
复杂眼镜 UI 动画
```

## 阶段进度快照

| 阶段 | 名称 | 状态 | 当前判断 |
| --- | --- | --- | --- |
| 0 | 工程审计与协作基线 | 已完成 | GPT 交接、路线图、基础文档已建立 |
| 1 | 手机网页主版块与二级版块 | 进行中 | 已拆主页/二级版块，但仍需视觉闭环验证 |
| 2 | 网页视觉识别闭环 | 下一步 P0 | 当前最优先修复 |
| 3 | G2 Glass UI 稳定 | 进行中 | 已有 GlassRenderer，但真机显示仍需逐屏验收 |
| 4 | R1/G2 输入调试 | 待真机记录 | 必须拿到真实 envelope/type/source |
| 5 | R1 控制相机 | 待真机验收 | 已改为 R1 单触两步：单触拍照/暂存，再单触上传，上滑重拍，下滑取消 |
| 6 | G2 Mic Probe | 待真机验收 | 先只看 PCM bytes/chunks，不接真实 ASR |
| 7 | ASR | 未完成 | 当前不作为第一优先级 |
| 8 | 天禄问答/OpenCLAW/交易只读 | 部分完成 | 交易状态可用，OpenCLAW 需稳定联调 |
| 9 | 视觉增强 | 未开始 | 等基础视觉闭环后再做 |
| 10 | 诊断与 Runbook | 待完善 | 需要把错误原因写清楚 |
| 11 | 自动化测试与打包发布 | 部分完成 | typecheck/build/pack 可跑 |

## 日志

### 2026-05-02 09:16

- 阶段：0 工程审计与协作基线
- 目标：把 GPT 桌面版审计需要的工程信息集中到根目录。
- 修改文件：`GPT_DESKTOP_HANDOFF.md`
- 验证命令：未运行构建，仅文档整理。
- 结果：已记录项目路径、关键命令、EHPK 路径、当前问题和下一步。
- 阻塞：无。
- 下一步：建立正式软件路线图。
- 负责人：Codex

### 2026-05-02 09:30

- 阶段：0 / 1 总路线梳理
- 目标：生成软件制作路线图，明确先后顺序。
- 修改文件：`SOFTWARE_ROADMAP.md`
- 验证命令：未运行构建，仅文档整理。
- 结果：已把工程拆成 12 个阶段，当前总进度估算约 28%，今日优先级固定为 P0 网页视觉识别闭环。
- 阻塞：无。
- 下一步：创建定时日志，并开始修复网页视觉识别。
- 负责人：Codex

### 2026-05-02 09:35

- 阶段：项目管理
- 目标：建立定时进度日志，后续所有开发、测试、打包都按同一份记录追加。
- 修改文件：`TIMED_PROGRESS_LOG.md`
- 验证命令：未运行构建，仅文档整理。
- 结果：已建立记录规则、模板、今日主线、阶段进度快照。
- 阻塞：无。
- 下一步：进入阶段 2，先修网页上的相机拍照与视觉识别闭环。
- 负责人：Codex

### 2026-05-02 09:40

- 阶段：GPT / Codex 协作规范
- 目标：建立固定 GPT Advisor Folder，统一存放 GPT 建议、审计、整改任务、交接和测试报告。
- 修改文件：`docs/gpt-advisor/`
- 验证命令：未运行构建，仅文档和目录初始化。
- 结果：已创建 `README.md`、`CURRENT_STATUS.md`、`NEXT_ACTIONS.md`、`ISSUE_REGISTER.md`、`DECISION_LOG.md`、`MODULE_MAP.md` 以及 prompts/audits/module-reviews/patch-requests/handoffs/test-reports/screenshots 子目录。
- 阻塞：无。
- 下一步：后续 GPT 新建议放入 `docs/gpt-advisor/prompts/`，具体整改任务放入 `docs/gpt-advisor/patch-requests/`。
- 负责人：Codex

### 2026-05-02 09:42

- 阶段：GPT 本地项目快照交接
- 目标：在不读取整台电脑、不输出敏感信息的前提下，把当前 G2 项目的真实代码状态汇总给 GPT 审计。
- 修改文件：`docs/gpt-advisor/handoffs/20260502_0942_local_project_snapshot_for_gpt.md`
- 验证命令：读取项目内路线图、GPT Advisor 文件、前端插件、Glass UI、相机、语音、后端 API 相关文件；未读取 `.env`。
- 结果：已汇总网页视觉识别、R1 相机控制、Glass UI、G2 MicProbe、ASR、OpenCLAW、交易只读状态和最小修复集合。
- 阻塞：无。
- 下一步：把该 handoff 文件内容交给 GPT 审计，然后按 GPT 建议优先修 P0 网页视觉识别闭环。
- 负责人：Codex

### 2026-05-02 14:13

- 阶段：5 R1 控制相机
- 目标：按 GPT 收敛方案改成 R1 单触两步视觉识别流程。
- 修改文件：`apps/evenhub-plugin/src/main.ts`、`apps/evenhub-plugin/src/glass/glassScreens.ts`、`apps/evenhub-plugin/src/display.ts`、`apps/evenhub-plugin/src/camera/visionEngine.ts`、`apps/evenhub-plugin/index.html`、`apps/evenhub-plugin/package.json`、`package-lock.json`、`docs/gpt-advisor/test-reports/20260502_1413_r1_single_touch_capture_confirm_report.md`
- 验证命令：`npm run typecheck`、`npm run build`、`npx evenhub pack app.json dist -o g2-视觉-语音助手.ehpk`
- 结果：全部通过；版本 `0.3.7`；SHA256 `99fefd64f8a0aeda6f850da4ad80eb4c7545a0d7d0acb58a4d2dd5a8761151c7`。
- 阻塞：真机仍需验证 R1 第二次单触是否在 `captured` 状态抵达插件。
- 下一步：上传新 EHPK，真机验证 `pendingCapturedImage=yes` 后 600ms 再单触上传。
- 负责人：Codex

### 2026-05-02 10:11

- 阶段：P0-001 网页视觉识别闭环
- 目标：一级“视觉识别”只切版块，二级“拍照识别”才获取图片并请求 `/vision`，网页稳定显示结果。
- 修改文件：`apps/evenhub-plugin/index.html`、`apps/evenhub-plugin/src/main.ts`、`apps/evenhub-plugin/src/style.css`、`packages/shared/src/index.ts`、`services/api-server/src/server.ts`、`docs/gpt-advisor/*`
- 验证命令：`npm run typecheck`、`npm run build`、`npm run pack:g2`、公网 `/health`、公网 `/vision` cover 图测试。
- 结果：typecheck/build/pack 全部通过；公网 `/vision` 返回 200；新 EHPK SHA256 为 `530c9cfa2f35c9cfa3fbd41a66eed20d64bf1aa9fcb1b39b1596018e4589e6ca`。
- 阻塞：还需要用户用手机 Even App WebView 真机测试拍照/选图是否可弹出，并确认 G2 结果显示。
- 下一步：用户测试 P0；通过后进入 P0-002 R1 相机控制。
- 负责人：Codex

### 2026-05-02 10:18

- 阶段：P0-001 真机反馈 / P0-002 启动
- 目标：记录用户真机反馈，并进入 R1 相机控制与眼镜菜单确认整改。
- 修改文件：`docs/gpt-advisor/patch-requests/20260502_1018_p0_002_r1_camera_control_patch_request.md`
- 验证命令：用户真机反馈。
- 结果：用户确认手机网页可以拍照、上传并识别。
- 阻塞：R1 仍需要能进入下一级菜单、控制拍照和确认发送。
- 下一步：审计并修复 `handleG2ControlEvent()`、`executeCurrentG2Bookmark()`、`handleVisionR1Intent()`。
- 负责人：Codex

### 2026-05-02 10:23

- 阶段：P0-002 R1 相机控制与眼镜菜单确认
- 目标：让 R1 在首页能进入视觉下一级页，并在视觉页控制拍照、发送、重拍和取消。
- 修改文件：`apps/evenhub-plugin/src/main.ts`、`apps/evenhub-plugin/src/glass/glassScreens.ts`、`docs/gpt-advisor/*`
- 验证命令：`npm run typecheck`、`npm run build`、`npm run pack:g2`
- 结果：typecheck/build/pack 全部通过；新 EHPK SHA256 为 `1d1900476b4b642a0218a0d511155ea1a9c0412f72672768f90bf9e3c4813344`。
- 阻塞：需要用户真机测试 R1 是否能进入视觉页、单击拍照、单击/双击发送、上滑重拍、下滑取消。
- 下一步：真机通过后进入 P0-003 R1 输入日志表与 G2 结果显示稳定性；不通过则先开 `debug_input` 记录 envelope/type/source。
- 负责人：Codex

### 2026-05-02 10:37

- 阶段：R0-002 / P0-002 R1 视觉控制最小补丁
- 目标：根据 GPT 最小补丁提示词修复 R1 视觉页事件冲突、双击误触、相机权限触发和图片过大风险。
- 修改文件：`apps/evenhub-plugin/index.html`、`apps/evenhub-plugin/src/main.ts`、`apps/evenhub-plugin/src/camera/cameraStream.ts`、`apps/evenhub-plugin/src/glass/glassScreens.ts`、`docs/gpt-advisor/*`
- 验证命令：`npm run typecheck`、`npm run build`、`npm run pack:g2`
- 结果：全部通过；新 EHPK SHA256 为 `b6f9496eb16e42b7a5fca1fc63a60823cb4109e986e8e64573c366c43b057ee4`。
- 阻塞：需要用户真机测试手机端“启用R1相机”、R1 单击拍照、双击发送、上滑重拍、下滑取消。
- 下一步：若仍失败，优先记录 R1 envelope/type/source，而不是继续改业务逻辑。
- 负责人：Codex

### 2026-05-02 10:45

- 阶段：R1 视觉控制行为修正
- 目标：按用户确认的 R1 行为规划，恢复“R1 单击进入视觉识别时自动启动相机”的主体验。
- 修改文件：`apps/evenhub-plugin/src/main.ts`、`docs/gpt-advisor/test-reports/20260502_1037_r1_vision_control_minimal_patch_report.md`、`docs/gpt-advisor/CURRENT_STATUS.md`
- 验证命令：`npm run typecheck`、`npm run build`、`npm run pack:g2`
- 结果：全部通过；新 EHPK SHA256 为 `08d1b5c432b41b908a13dc265704ee6fcdecf4e38977ded02f17dff292205609`。
- 阻塞：若真机仍提示相机自动启动失败，则说明 Even/iOS WebView 不把 R1 当作相机 user activation，需要改为手机端首次启用相机后 R1 控制截帧。
- 下一步：用户真机测试 R1 进入视觉页是否能自动打开相机并进入 `vision_ready`。
- 负责人：Codex

### 2026-05-02 10:58

- 阶段：EHPK 版本缓存修正
- 目标：解决眼镜端仍显示旧 UI/旧逻辑的问题，避免 Even 平台和真机继续加载 `0.2.0` 缓存构建。
- 修改文件：`apps/evenhub-plugin/app.json`、`apps/evenhub-plugin/package.json`、`docs/gpt-advisor/CURRENT_STATUS.md`
- 验证命令：`npm run typecheck`、`npm run build`、`npm run pack:g2`
- 结果：全部通过；插件版本升至 `0.2.1`；新 EHPK SHA256 为 `14ba595a315a6dcb70481b9b31dbd17b61087bbd71929d1d4b7390115cbcc3ac`。
- 阻塞：需要用户上传/安装 `0.2.1` 新包后真机确认眼镜端 UI 与 R1 行为是否更新。
- 下一步：若眼镜端仍无变化，检查 Even App 是否实际加载新 build，必要时删除旧插件后重装。
- 负责人：Codex

### 2026-05-02 11:12

- 阶段：R1 视觉入口错误逻辑清理
- 目标：彻底删除“启用R1相机”错误路径，视觉识别入口改为直接自动启动相机，R1 单击拍照、双击发送。
- 修改文件：`apps/evenhub-plugin/src/main.ts`、`apps/evenhub-plugin/src/glass/glassScreens.ts`、`apps/evenhub-plugin/app.json`、`apps/evenhub-plugin/package.json`、`docs/gpt-advisor/CURRENT_STATUS.md`
- 验证命令：`rg "启用R1相机|启用 R1 相机|相机已启用|needs_phone_activation|vision-enable-camera"`、`npm run typecheck`、`npm run build`、`npm run pack:g2`
- 结果：错误路径已无搜索结果；全部构建通过；插件版本升至 `0.2.2`；新 EHPK SHA256 为 `28d176bcff109b0151eb159ecd3600884807aa7ea6787deff439aca0e0bcee23`。
- 阻塞：需要真机安装 `0.2.2` 后确认 R1 视觉链路。
- 下一步：真机测试首页选择视觉识别后，是否直接出现相机准备/就绪页，R1 单击是否拍照，双击是否发送。
- 负责人：Codex

### 2026-05-02 11:22

- 阶段：R1 相机平台限制方案落地
- 目标：按 GPT 审计结论停止 R1 事件链直接启动 `getUserMedia`，改为手机 DOM 首次启动“天禄视觉引擎”，R1 后续只控制截帧、重拍、取消和发送。
- 修改文件：`apps/evenhub-plugin/src/camera/visionEngine.ts`、`apps/evenhub-plugin/src/main.ts`、`apps/evenhub-plugin/index.html`、`apps/evenhub-plugin/src/style.css`、`apps/evenhub-plugin/app.json`、`apps/evenhub-plugin/package.json`、`docs/gpt-advisor/CURRENT_STATUS.md`
- 验证命令：`npm run typecheck`、`npm run build`、`npm run pack:g2`
- 结果：全部通过；插件版本升至 `0.2.3`；新 EHPK SHA256 为 `436a86a91ce7090caa52bfd6a33b6f1341f34a27283028c173c4a8296c21c8ea`。
- 阻塞：首次视觉引擎启动仍必须由手机 DOM 按钮触发，这是 iOS/WKWebView/Even Hub 当前能力边界。
- 下一步：真机先点手机端“启动天禄视觉引擎”，确认视频流就绪后，再用 R1 进入视觉识别、单击拍照、双击发送。
- 负责人：Codex

### 2026-05-02 11:34

- 阶段：权限自检与错误诊断
- 目标：避免把所有相机启动失败误报为“权限未开”，在设置页增加相机、手机/耳机麦克风、G2 麦克风开关的自检与一键请求入口。
- 修改文件：`apps/evenhub-plugin/index.html`、`apps/evenhub-plugin/src/main.ts`、`apps/evenhub-plugin/src/camera/cameraStream.ts`、`apps/evenhub-plugin/src/style.css`、`docs/gpt-advisor/CURRENT_STATUS.md`
- 验证命令：`npm run typecheck`、`npm run build`、`npm run pack:g2`
- 结果：全部通过；插件版本 `0.2.4`；新 EHPK SHA256 为 `6789e1733f63045bca286a380125647b135cbee7f2130ece19f0bfa0e30f4fbb`。
- 阻塞：系统级权限无法由网页“一键强制开启”，只能通过用户点击触发权限请求和读取错误诊断。
- 下一步：用户进入设置页点击“权限自检 / 一键请求权限”，把具体错误名反馈回来。
- 负责人：Codex

## 下一工作块

### P0-002：R1 相机控制真机验收

目标：

```text
R1 选择视觉识别
-> 单击进入视觉页
-> 单击拍照
-> 单击/双击发送识别
-> 上滑重拍
-> 下滑取消
```

验收：

- [ ] R1 能进入视觉下一级页。
- [ ] R1 单击能拍照。
- [ ] R1 单击或双击能发送。
- [ ] R1 上滑能重拍。
- [ ] R1 下滑能取消。

### 2026-05-02 15:40

- 阶段：R0-003a 呼叫天禄 G2 麦克风采集入口
- 目标：点击“呼叫天禄 / 语音对话”后真实进入 G2 Mic Probe，调用 `bridge.audioControl(true)`，监听 `audioEvent.audioPcm`，通过 WebSocket 发送到 `/audio?mode=probe&source=g2`，并在 G2/手机 Voice Debug 显示 PCM bytes/chunks。
- 修改文件：`apps/evenhub-plugin/index.html`、`apps/evenhub-plugin/src/style.css`、`apps/evenhub-plugin/src/main.ts`、`apps/evenhub-plugin/src/glass/glassMicProbe.ts`、`apps/evenhub-plugin/src/glass/glassScreens.ts`、`apps/evenhub-plugin/src/voice/g2MicProbe.ts`、`services/api-server/src/server.ts`、`docs/gpt-advisor/*`
- 验证命令：`npm run typecheck`、`npm run build`、`npm run pack:g2`
- 结果：全部通过；新 EHPK SHA256 为 `c4d4cbbf209bda6ef6fcd0c5b7eb585a203588cefc3798f31f669ccf8be4718d`。
- 阻塞：本地无法替代真机确认 G2 `audioEvent.audioPcm` 是否增长。
- 下一步：真机安装后点“呼叫天禄 / 语音对话”，确认 Voice Debug 的 `audioControlCalled=true`、`wsStatus=open`、`totalBytes/chunks` 是否增长。
- 负责人：Codex

### 2026-05-02 16:24

- 阶段：R0-003a 补丁：手机/耳机麦克风真实录音兜底
- 目标：替换导致 `not-allowed` 的 Web Speech Recognition 主路径，改为 `getUserMedia({ audio }) + MediaRecorder` 真实采集音频，松开后上传 `/transcribe`。
- 修改文件：`apps/evenhub-plugin/src/voice/phoneMicRecorder.ts`、`apps/evenhub-plugin/src/main.ts`、`apps/evenhub-plugin/src/api.ts`、`packages/shared/src/index.ts`、`packages/asr-adapter/src/index.ts`
- 验证命令：`npm run typecheck`、`npm run build`、`npm run pack:g2`
- 结果：全部通过；新 EHPK SHA256 为 `7d574e4f842bb970fd3c6df94193ff0a8c1185d0b0eaec5b80668a170f43f8c2`。
- 阻塞：如果 Even App WebView 仍拒绝 `getUserMedia({ audio })`，说明容器禁用手机/耳机麦克风；下一步应测试 Safari 直开域名或专注 G2 PCM 链路。
- 负责人：Codex

### 2026-05-02 16:53

- 阶段：R0-003 呼叫天禄按住说话 / G2 PCM / mock-asr / 意图路由
- 目标：按 GPT 指导实现呼叫天禄独立子菜单、手机按住说话、R1 单触开始/结束、120 秒录音上限、G2 `audioControl(true)` + `audioEvent.audioPcm` 主链路、`/audio` end_of_speech、mock-asr transcript、`handleTranscript -> routeVoiceIntent`。
- 修改文件：`apps/evenhub-plugin/src/main.ts`、`apps/evenhub-plugin/src/voice/g2PcmVoiceSession.ts`、`apps/evenhub-plugin/src/glass/glassScreens.ts`、`apps/evenhub-plugin/index.html`、`apps/evenhub-plugin/src/config.ts`、`services/api-server/src/server.ts`、`docs/gpt-advisor/*`
- 验证命令：`npm run typecheck`、`npm run build`、`npm run pack:g2`
- 结果：全部通过；新 EHPK SHA256 为 `ce18e373354684cb19b2263bc2bd1b3cc1eecbb3376e1d02e8d826355181c4dd`。
- 阻塞：本地无法替代真机确认 G2 `audioEvent.audioPcm` 是否增长；真实 ASR 仍未配置。
- 下一步：真机安装新 EHPK，点“呼叫天禄 / 语音对话”，确认 `audioControlCalled=true`、`wsStatus=open`、`totalBytes/chunks` 增长，并观察 mock-asr 是否返回 final_transcript。
- 负责人：Codex

### 2026-05-02 17:09

- 阶段：语音模块去除默认 mock-asr
- 目标：解决呼叫天禄返回预置“看一下交易状况”而不是真实录音转文字的问题。
- 修改文件：`apps/evenhub-plugin/src/main.ts`、`docs/gpt-advisor/test-reports/20260502_1709_voice_real_asr_mode_no_mock_report.md`
- 结果：前端默认语音模式从 `mock-asr` 改为 `asr`；手机网页按住说话强制走 `phone-media-recorder`；R1/G2 继续走 `g2-pcm`；ASR 未配置时显示真实错误，不再返回预置假文字。
- 验证命令：`npm run typecheck`、`npm run build`、`npm run pack:g2`
- 验证结果：全部通过；新 EHPK SHA256 为 `108b75e71b26188f8154fdb1305e5c9451a049db8ce58e7685ed143fe54cb7a3`。
- 阻塞：`.env` 中 `ASR_PROVIDER=minimax` 但 `MINIMAX_ASR_ENDPOINT` 为空，真实语音转文字仍未接入。
- 下一步：接入真实 ASR 服务，或新增本地 Whisper ASR 服务。
- 负责人：Codex

### 2026-05-02 17:30

- 阶段：本地 Whisper ASR 接入
- 目标：解决呼叫天禄返回预置 mock 文本、无法真实录音转文字的问题。
- 修改文件：`services/local-whisper-asr/server.py`、`services/local-whisper-asr/requirements.txt`、`scripts/start-local-whisper-asr.sh`、`scripts/stop-local-whisper-asr.sh`、`.env`、`~/Library/LaunchAgents/com.tianlu.g2.local-whisper-asr.plist`、`docs/gpt-advisor/test-reports/20260502_1730_local_whisper_asr_integration_report.md`
- 结果：本地 Whisper ASR 已由 launchd 托管在 `127.0.0.1:8791`；后端 `/asr/status` 返回 HTTP ASR 已配置；`/transcribe` 已能返回真实转写文本。
- 验证结果：测试音频“你好天禄 帮我看一下交易机器人运行如何”返回“你好天路,帮我看一下交易机器人运行如何。”。
- 验证命令：`npm run typecheck`、`npm run build`、`npm run pack:g2`
- 打包结果：全部通过；EHPK SHA256 为 `108b75e71b26188f8154fdb1305e5c9451a049db8ce58e7685ed143fe54cb7a3`。
- 阻塞：仍需真机确认 Even App 手机/耳机麦克风或 G2 `audioEvent.audioPcm` 是否能采集音频并上传。
- 下一步：真机测试呼叫天禄按住说话，若可录音上传则进入意图路由与播报回归。
- 负责人：Codex

### 2026-05-02 20:13

- 阶段：交易状态公网实时控制台升级
- 目标：根据 9099 控制台只读接口目录，把眼镜软件交易状态从局域网/备份记忆改为 `https://console.tianlu2026.org` 公网实时只读源，并完善交易页分类展示。
- 修改文件：`packages/shared/src/index.ts`、`packages/trading-adapter/src/index.ts`、`services/api-server/src/server.ts`、`apps/evenhub-plugin/index.html`、`apps/evenhub-plugin/src/main.ts`、`apps/evenhub-plugin/src/history.ts`、`docs/gpt-advisor/handoffs/20260502_1941_macb_original_trading_files_read_report.md`。
- 新增接口：`/glasses/api/summary`、`/glasses/api/prices`、`/glasses/api/positions`、`/glasses/api/l5`、`/glasses/api/pair/:pair`、`/glasses/api/alerts`。
- 验证结果：`/glasses/api/summary` 返回公网源、12/12 机器人在线、31 个实时持仓、BNB/BTC/DOGE/ETH/SOL 白名单价格；`/glasses/api/l5` 返回 L5 资金流和真实订单归因。
- 构建命令：`npm run typecheck`、`npm run build`、`npm run pack:g2`。
- 构建结果：通过。
- EHPK：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- SHA256：`e41804b4f054a13f7cd72cdc64ebcd59370f2a3afd940edd321c74951a70dba2`
- 阻塞：仍需真机刷新确认交易页不再显示旧备份路径；R1 电量仍未稳定读取。
- 下一步：交易眼镜端分页细化，总览 / 白名单价格 / 持仓评测 / L5归因。
- 负责人：Codex

### 2026-05-02 20:37

- 阶段：交易状态六项摘要与 AI 评测升级
- 目标：用户要求交易机器人信息不能只总结三项，至少总结 6 项，并在下面增加 MiniMax 或 GPT-5.5 评测。
- 修改文件：`packages/shared/src/index.ts`、`packages/trading-adapter/src/index.ts`、`services/api-server/src/server.ts`、`apps/evenhub-plugin/src/main.ts`。
- 结果：交易概览新增 `aiAssessment`，包含 `summaryPoints`、`summary`、`suggestions`、`provider`、`source`；本地规则会生成 7 项摘要，API 层优先调用 MiniMax-M2.7 生成实时只读交易评测，失败时保留本地评测。
- 验证：`/trading/overview` 返回 31 个持仓、7 项摘要、`provider=MiniMax-M2.7`；`/glasses/api/summary` 返回公网源 `https://console.tianlu2026.org`、31 个持仓、7 项摘要和 MiniMax 评测。
- 构建命令：`npm run typecheck`、`npm run build`、`npm run pack:g2`。
- 构建结果：通过。
- EHPK：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- SHA256：`39f48b4e6aa76712c09dbab5a48ea99e9a8db2ce499ab2c38df35ac79d9aa47c`
- 下一步：真机刷新交易页确认 AI 评测卡片；随后将“呼叫天禄”的交易问答复用同一套 AI 评测。
- 负责人：Codex

### 2026-05-02 20:48

- 阶段：读取后续模块计划并生成升级工作流
- 来源：`/Users/luxiangnan/Desktop/EVEN G2视觉和语音对讲系统/tianlu_g2_module_plans_codex_prompts`
- 结果：已创建 `docs/gpt-advisor/MODULE_UPGRADE_WORKFLOW.md`，将后续工作按当前缺口重新排序。
- 当前优先级：先修“呼叫天禄”语音闭环、结果展示、历史记录和意图路由；再做语音触发视觉、拍照结果朗读与 G2 显示。
- 新增补丁任务：`docs/gpt-advisor/patch-requests/20260502_2048_r0_003_voice_answer_display_and_intent_fix.md`
- 本轮未修改业务代码，未重新打包。
- 负责人：Codex

### 2026-05-02 21:14

- 阶段：呼叫天禄语音回答与交易路由修复
- 目标：修复语音按压不稳、交易语音问题走旧 mock/占位路径、普通回答占位过滤不足。
- 修改文件：`apps/evenhub-plugin/src/main.ts`、`apps/evenhub-plugin/src/style.css`、`services/api-server/src/server.ts`。
- 结果：圆形语音按钮增加触摸防打断；`pointercancel` 不再停止录音；交易语音问答改为直接读取 `/trading/overview` 并复用 MiniMax-M2.7 交易评测；前后端占位回答过滤增强。
- 验证命令：`npm run typecheck`、`npm run build`、`npm run pack:g2`。
- 构建结果：全部通过。
- EHPK：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- SHA256：`cd037732f28db27c096bcffc326b7435ee38d59331df5a8132d763dc201da236`
- 下一步：真机验证按住录音不再提前断；继续修普通问答真实回答质量、视觉意图自动切换、R1 电量读取。
- 负责人：Codex

### 2026-05-02 21:25

- 阶段：R1 电量读取修复
- 目标：修复顶部 R1 电量显示为“未上报 / --”的问题。
- 修改文件：`apps/evenhub-plugin/src/main.ts`。
- 结果：调整设备种类推断顺序，优先通过已知 G2 SN 反推未知设备为 R1；扩展 R1 电量字段和嵌套结构解析；支持 `"58%"` 字符串百分比。
- 验证命令：`npm run typecheck`、`npm run build`、`npm run pack:g2`。
- 构建结果：全部通过。
- EHPK：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- SHA256：`9c556cc213500b4d7368a2dc7c67a4c179e35765141fb63f0a2f77e6de4772a4`
- 阻塞：需要真机确认 Even App 是否实际上报 R1 电量字段。若仍未上报，需要抓 `[G2 device status]` 原始日志。
- 负责人：Codex

### 2026-05-02 21:46

- 阶段：呼叫天禄回答质量与面板稳定性修复
- 目标：修复普通问答答非所问/占位回复，以及语音页回答后网页飘回首页的问题。
- 修改文件：`services/api-server/src/server.ts`、`apps/evenhub-plugin/src/main.ts`、`apps/evenhub-plugin/src/style.css`。
- 结果：`/ask` 增加 MiniMax 严格二次追问和本地 fallback；语音状态更新时保持呼叫天禄书签激活；Voice Debug 默认强制隐藏。
- 本地测试：`/ask` 问“附近有什么好吃好玩”返回直接回答，不再出现“收到问题，会显示在这里”。
- 验证命令：`npm run typecheck`、`npm run build`、`npm run pack:g2`。
- 构建结果：全部通过。
- EHPK：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- SHA256：`5c79bc5fc0a3b527563d9e45ff7f6cbc3c4d2afaee43a33d4280572c92e5b284`
- 下一步：真机验证呼叫天禄普通问答、语音页不跳菜单；继续修真实 ASR 空文字、视觉意图触发和 R1 电量原始字段。
- 负责人：Codex

### 2026-05-02 21:58

- 阶段：呼叫天禄录音完整性与前端回答兜底修复
- 目标：修复按住说话录音可能不完整、旧配置导致 30 秒上限、ASR 空结果提示不清、旧占位回答仍显示的问题。
- 修改文件：`apps/evenhub-plugin/src/voice/phoneMicRecorder.ts`、`apps/evenhub-plugin/src/main.ts`。
- 结果：`MediaRecorder.stop()` 前强制 `requestData()`；录音最长时长统一为 120 秒；ASR 空结果提示包含 KB 和秒数；前端拦截占位回答并提供本地通用回答。
- 验证命令：`npm run typecheck`、`npm run build`、`npm run pack:g2`。
- 构建结果：全部通过。
- EHPK：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- SHA256：`41cab673e06cbc3d0daa8a0e2b09c6d7fff47475a082ceca13ffc1a28a8b94c7`
- 下一步：真机测试按住录音是否稳定录满；若 ASR 仍空，抓取 `durationMs / sizeBytes / mimeType / provider`。
- 负责人：Codex

### 2026-05-02 22:10

- 阶段：视觉识别提问与历史追问补丁
- 目标：视觉识别支持“带问题看图”；呼叫天禄的视觉意图把语音问题一起传给 `/vision`；视觉/语音历史支持继续追问。
- 修改文件：`apps/evenhub-plugin/index.html`、`apps/evenhub-plugin/src/main.ts`、`apps/evenhub-plugin/src/history.ts`、`apps/evenhub-plugin/src/style.css`。
- 结果：新增视觉问题输入框；`runCaptureFlow` 统一使用 `effectivePrompt`；新增 `askVisionFollowup`；历史项新增“继续追问”按钮。
- 验证命令：`npm run typecheck`、`npm run build`、`npm run pack:g2`。
- 构建结果：全部通过。
- EHPK：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- SHA256：`13ba88bba0d344a6fb07918168053dfa8235ee872d1cf800399842e9d3c96d26`
- 下一步：真机测试看图问题、语音看图意图、历史继续追问。
- 负责人：Codex

## 2026-05-02 22:20 产品命名统一

- 将项目最终名称统一为：天禄 G2 运维助手。
- README、SOFTWARE_ROADMAP、CURRENT_STATUS、app.json 已同步产品定位。
- 当前进度口径调整为：代码功能约 45%，真机稳定可审核约 35-40%。
- 下一步仍按模块推进：呼叫天禄语音闭环 -> 交易状态准确展示 -> G2 眼镜端 UI 收敛。

## 2026-05-02 22:35 生成明日全天完工计划

- 新增根目录计划文件：`20260503_天禄G2运维助手全天完工计划.md`。
- 明天目标：把当前 45% 代码完成度推进到自用 MVP，优先完成呼叫天禄语音闭环、交易状态准确展示、G2 四书签 UI 收敛和最终打包验收。
- 明天原则：每个时间段只处理一个模块；不再混修；所有结果写入 GPT Advisor 与定时日志。

## 2026-05-02 22:45 Glass HUD UI 重塑

- 根据 `tianlu_g2_all_glass手机端UI重塑/tianlu_g2_all_glass_text_previews.md` 重写眼镜端 HUD 文案。
- 主页、视觉识别、呼叫天禄、交易状态、设置诊断、错误页已统一为 TL-OS / TL-CAM / TL-AI / TL-BOT / TL-SYS 风格。
- 保持单 TextContainer 技术路线，不依赖网页 CSS。
- 验证：`npm run typecheck`、`npm run build`、`npm run pack:g2` 均通过。
- EHPK：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`。
- SHA256：`bcf480227b764ab8db03c401472a8426207ba361ed75e9e032851e0b0d92d2d8`。

## 2026-05-02 23:09 G2 首页三模块收敛

- 按用户最新要求，G2 眼镜首页只保留三个主版块：视觉识别、呼叫天禄、交易状态。
- 设置、诊断、OpenCLAW 调试继续保留在手机插件页面；手机端触发时仍可同步显示到眼镜，但不再作为 G2 首页第 4 书签。
- 修改文件：`apps/evenhub-plugin/src/main.ts`、`apps/evenhub-plugin/src/glass/glassScreens.ts`、`apps/evenhub-plugin/app.json`、`apps/evenhub-plugin/package.json`、`package-lock.json`。
- 验证：`npm run typecheck`、`npm run build`、`npm run pack:g2` 均通过。
- EHPK：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`。
- SHA256：`729d91392bd52d9039b863c344bc9ded4bef221fb57a03b21c3dc20a81c3fef4`。

## 2026-05-02 23:20 G2 子模块居中 HUD 统一

- 按用户提供的 GPT PNG 风格，继续重塑眼镜端所有主要 Glass 页面。
- 首页去掉 G2/R1/LINK 等工程状态，只保留视觉识别、呼叫天禄、交易状态三大核心入口。
- 视觉、语音、交易、回复、错误、诊断、设置页面主体文案统一居中，减少测试界面感。
- 修复交易状态 R1 单触确认不可用：现在确认“交易状态”会直接执行 `runTradingOverview()`。
- 验证：`npm run typecheck`、`npm run build`、`npm run pack:g2` 均通过。
- EHPK：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`。
- SHA256：`8fefbe9216b5cf0d4dc10eec9cad50e372f2fccb2a39527f532bd8a9f3d6d807`。

## 2026-05-02 23:31 G2 首页横向三入口与去拉伸空档

- 按用户反馈修正“只是居中但仍像缩在左下角”的问题。
- 首页删除 `TL-OS // TIANLU` 工程头标、删除上下多余空行。
- 首页改为三大入口横向并排 HUD 卡片：视觉识别、呼叫天禄、交易状态。
- 手机插件 WebView 关闭 body 级 overscroll，滚动限定在 `#app` 内，避免 R1/触摸操作产生上下拉伸空档。
- 增加全局 `box-sizing: border-box`，修复 `100dvh + padding` 造成的额外可滚动空白。
- 验证：`npm run typecheck`、`npm run build`、`npm run pack:g2` 均通过。
- EHPK：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`。
- SHA256：`eb64b0948e255b6563a5d2473f506bc8e91663555291e98411fcd1eb0b405341`。

## 2026-05-04 16:00 P0 核心真机冒烟通过

- 阶段：P0 CORE TRUE_DEVICE PASSED
- 目标：Day2-4 合并冲刺代码修复 + 真机冒烟验收
- 修改文件：
  - `apps/evenhub-plugin/src/main.ts`（视觉取消 bug、语音正则、交易 R1 控制）
  - `docs/gpt-advisor/test-reports/20260504_1600_day2_4_merge_sprint_report.md`
  - `docs/gpt-advisor/test-reports/20260504_1630_voice_regex_hotfix_report.md`
- 验证命令：`npm run typecheck`、`npm run build`、`npm run pack:g2`
- 结果：全部通过
- EHPK 版本：0.5.5
- EHPK SHA256：`c36813e7669c7bb2ff3d380450fed35550ccf63f697ed339bab1acc79364ccbf`
- 真机冒烟验收：6/6 项全部通过
  1. 首页 4 菜单 + R1 切换 ✓
  2. 手机取消拍照/选图 → G2 返回首页 ✓
  3. "帮我看一看这是什么" → 触发视觉 ✓
  4. "这是啥" → 触发视觉 ✓
  5. "瞧一瞧" → 触发视觉 ✓
  6. 交易 R1 next/previous 切标签，click 进详情 ✓
- 阻塞：无
- 下一步：P1-STABILIZE-001 稳定性整理，不再随机修改 P0 已通过功能
- 负责人：Claude / 用户
