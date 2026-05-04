# 当前状态

更新时间：2026-05-02

## 项目定位

项目名称：天禄 G2 运维助手

目标设备：

- Even Realities G2 智能眼镜
- R1 戒指
- iPhone 16 Pro Max

当前目标：

```text
视觉识别基础链路已可用
当前进入“呼叫天禄”按住说话 / G2 PCM / 本地 Whisper ASR / 意图路由验收
本地 ASR 已通过 /transcribe 验证，下一步验证真机音频采集是否能上传
交易状态已切换到公网 9099 控制台实时只读源
已读取 tianlu_g2_module_plans_codex_prompts，后续按 MODULE_UPGRADE_WORKFLOW.md 分模块升级
G2 眼镜首页已收敛为三大主版块：视觉识别、呼叫天禄、交易状态；设置/诊断仅保留在手机插件页并可按需同步到眼镜
G2 眼镜端主要子模块已按 GPT PNG 参考改为居中 HUD 风格，交易状态 R1 单触确认已修复为直接刷新交易只读概览
```

## 当前完成度

整体估算：约 45%

已具备：

- 工程骨架。
- 前端插件工程。
- 后端接口雏形。
- MiniMax / OpenCLAW / Trading adapter 结构。
- EHPK 打包能力。
- GPT 交接文件。
- 软件路线图。
- 定时进度日志。

关键未完成：

- 网页视觉识别闭环已通过用户真机反馈。
- R1 控制视觉页已调整为单触两步：第一次单触拍照/暂存，第二次单触确认上传，待真机确认。
- 设置书签诊断已从占位改为一键扫描/一键修复/权限自检。
- G2 眼镜端 UI 真机显示仍需继续稳定。
- R1 事件未形成真机日志表。
- 呼叫天禄已新增按住说话 / R1 单触开始结束 / 120 秒上限 / G2 PCM 会话。
- `/audio` 已支持 `end_of_speech` 与 `mock-asr`，且 mock 需要收到真实 PCM 后才返回 transcript。
- `final_transcript` 已进入 `handleTranscript -> routeVoiceIntent`，支持视觉意图、交易意图、普通问答分流。
- G2 麦克风 PCM bytes/chunks 仍需真机验收。
- 本地 Whisper ASR 已接入，`/transcribe` 可返回真实转写文本。
- OpenCLAW 问答可能超时。
- 交易状态问答和交易页已切换为公网控制台 `https://console.tianlu2026.org` 实时只读源，不再用旧 mock 持仓或备份报告回答交易问题。
- 已新增 `/glasses/api/summary`、`/glasses/api/prices`、`/glasses/api/positions`、`/glasses/api/l5`、`/glasses/api/pair/:pair`、`/glasses/api/alerts` 只读聚合接口。
- 白名单实时价格已修复为只读 `TRADING_ALLOWED_SYMBOLS=BTC,ETH,SOL,BNB,DOGE`，优先公网控制台 `/api/prices/realtime`，不再混入持仓交易对或备份报告。
- 交易页新增交易数据源、白名单价格、机器人在线、整体持仓评测、真实持仓交易对、M1-M5/L5 资金流、真实订单归因等分区。
- 交易概览新增 6 项以上摘要与 AI 评测；本地验证 `/trading/overview` 和 `/glasses/api/summary` 均返回 7 项摘要，且 MiniMax-M2.7 成功生成实时持仓评测。
- 新增 `docs/gpt-advisor/MODULE_UPGRADE_WORKFLOW.md`，把后续升级重新排序为：呼叫天禄语音闭环 -> 语音视觉意图 -> 拍照结果朗读/G2显示 -> 交易告警 -> 设备诊断 -> Glass UI -> 实时/视频/场景记忆。

## 当前关键文件

- `SOFTWARE_ROADMAP.md`
- `TIMED_PROGRESS_LOG.md`
- `GPT_DESKTOP_HANDOFF.md`
- `docs/architecture.md`
- `docs/current-state.md`
- `docs/codex-execution-plan-v1.md`
- `docs/acceptance-checklist.md`
- `docs/glass-ui-design.md`
- `docs/tianlu-g2-assistant-latest-shape.md`

## 最近打包信息

最近已知 EHPK：

- `apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- `apps/evenhub-plugin/g2-视觉-语音助手.ehpk`

最近已知 SHA256：

```text
cd037732f28db27c096bcffc326b7435ee38d59331df5a8132d763dc201da236
e41804b4f054a13f7cd72cdc64ebcd59370f2a3afd940edd321c74951a70dba2
39f48b4e6aa76712c09dbab5a48ea99e9a8db2ce499ab2c38df35ac79d9aa47c
```

## 2026-05-02 21:14 追加状态

- 已修复“呼叫天禄”交易类语音问答路由：交易问题现在直接调用 `/trading/overview` 公网实时只读概览，并复用 MiniMax-M2.7 交易评测。
- 已增强占位回答过滤，拦截“我已收到问题 / 会显示在这里 / Telegram”等无效回答。
- 已增强手机网页圆形语音按钮按压稳定性，`pointercancel` 不再自动停止录音，增加上限计时器清理。
- 最新 EHPK SHA256：`cd037732f28db27c096bcffc326b7435ee38d59331df5a8132d763dc201da236`。

## 2026-05-02 21:25 追加状态

- 已修复 R1 电量读取的误归类与字段解析问题：优先通过已知 G2 SN 反推 R1，并扩展 `r1Battery`、`ringBatteryLevel`、`controllerBattery`、`r1Power` 等字段解析。
- 已支持 `"58%"` 这类字符串百分比。
- 已新增日志 `kindSpecific`，便于真机确认 Even App 实际上报的 R1 电量字段。
- 最新 EHPK SHA256：`9c556cc213500b4d7368a2dc7c67a4c179e35765141fb63f0a2f77e6de4772a4`。
- 若真机仍显示“未上报”，说明 Even App 当前事件可能没有上报 R1 电量，需要抓 `[G2 device status]` 原始日志继续对字段。

## 2026-05-02 21:46 追加状态

- 已修复呼叫天禄普通问答占位回答：MiniMax 首次返回无效空话时会严格二次追问，仍无效时返回本地可用 fallback。
- 已修复呼叫天禄网页面板飘回首页/其他书签的问题：语音状态更新时保持 `voice` 书签激活。
- Voice Debug 默认强制隐藏，不再挤在用户回答区域下方。
- `/ask` 本地测试“附近有什么好吃好玩”已返回直接可用回答。
- 最新 EHPK SHA256：`5c79bc5fc0a3b527563d9e45ff7f6cbc3c4d2afaee43a33d4280572c92e5b284`。

## 2026-05-02 21:58 追加状态

- 已修复手机/网页端语音录音结束前未强制 flush 音频 chunk 的问题：`MediaRecorder.stop()` 前调用 `requestData()`。
- 已把呼叫天禄录音上限统一恢复为 120 秒，避免旧 localStorage 配置仍显示 30 秒。
- ASR 空文本提示现在包含录音大小和录音时长，便于定位是“没录全”还是“ASR 没识别出字”。
- 前端新增普通问答兜底，公网后端若仍返回旧占位话术，也会被前端拦截成可用回答。
- 最新 EHPK SHA256：`41cab673e06cbc3d0daa8a0e2b09c6d7fff47475a082ceca13ffc1a28a8b94c7`。

## 2026-05-02 22:10 追加状态

- 已给视觉识别模块新增“看图问题”输入框；拍照/相册选图时会把问题作为 `/vision` prompt 一起发送。
- 呼叫天禄识别到“帮我看一下这是什么”后，语音文本会继续传入视觉识别 prompt，不再只上传图片。
- 视觉结果支持二次追问：最近视觉描述、上次问题和上次回答会作为上下文进入 `askAssistant()`。
- 历史记录新增“继续追问”按钮：视觉历史回到视觉追问框，语音/交易历史回到呼叫天禄手动输入框。
- 最新 EHPK SHA256：`13ba88bba0d344a6fb07918168053dfa8235ee872d1cf800399842e9d3c96d26`。

## 2026-05-02 23:09 追加状态

- 已按最新产品结构把 G2 眼镜首页主书签收敛为 3 个：视觉识别、呼叫天禄、交易状态。
- “设置/连接诊断/OpenCLAW 调试”不再作为 G2 首页主书签；手机插件页仍保留这些入口，触发时仍可同步诊断页面到眼镜。
- 已将插件版本提升到 `0.3.9`。
- 最新 EHPK SHA256：`729d91392bd52d9039b863c344bc9ded4bef221fb57a03b21c3dc20a81c3fef4`。

## 2026-05-02 23:20 追加状态

- 已按用户提供的 GPT PNG 参考，将眼镜端主要子模块统一为居中 HUD 风格。
- 首页去掉 G2/R1/LINK 等工程状态，只保留三大核心入口。
- 视觉、呼叫天禄、交易状态、回复、错误、诊断、设置等页面主体文案已居中。
- 已修复交易状态入口 R1 单触不可用：现在会直接执行交易只读刷新。
- 已将插件版本提升到 `0.4.0`。
- 最新 EHPK SHA256：`8fefbe9216b5cf0d4dc10eec9cad50e372f2fccb2a39527f532bd8a9f3d6d807`。

## 2026-05-02 23:31 追加状态

- 已按用户反馈继续修正 G2 首页：去掉 `TL-OS` 头标和上下大空行。
- 首页改为三大入口横向并排卡片：视觉识别、呼叫天禄、交易状态。
- 手机插件 WebView 关闭 body 级橡皮筋 overscroll，滚动限定在 `#app` 容器内，避免 R1/触摸操作产生上下拉伸空档。
- 已修复 `100dvh + padding` 撑高页面的问题，增加全局 `box-sizing: border-box`。
- 最新 EHPK SHA256：`eb64b0948e255b6563a5d2473f506bc8e91663555291e98411fcd1eb0b405341`。

## 2026-05-03 00:35 追加状态（P0-PHONE-UI-RECOVER-002）

- **核心问题**：`g2Bookmarks`（3项）同时驱动手机网页和 G2 眼镜端，导致 openclaw（手机第4项书签）无法被 `selectG2Bookmark()` 正确处理。点击"设置"后 `updateActiveBookmarkLayout()` 会用旧的 `g2BookmarkIndex` 覆盖 `app.dataset.activeBookmark = 'openclaw'`。
- **修复方案**：
  - 新增 `src/ui/phoneNavigation.ts`：独立手机网页导航配置（vision/voice/trading/openclaw，4项）
  - 新增 `src/glass/glassNavigation.ts`：独立 G2 眼镜端导航配置（vision/voice/trading，3项）
  - 引入 `phoneActiveBookmarkId` 状态变量，与 `g2BookmarkIndex`（ring 导航）独立
  - `updateActiveBookmarkLayout()` 只在当前是 g2Ids（vision/voice/trading）之一时同步 ring 导航结果，不覆盖 'openclaw'
  - `renderBookmarkChrome()` 改用 `phoneBookmarks` 计算书签编号（4/4 而非 3/3）
  - `getBookmarkCardDescription()` 扩展支持 `PhoneBookmarkId`
- **测试结果**：typecheck ✓ / build ✓ / pack ✓（25 modules，179.10 kB）
- 最新 EHPK SHA256：`2dab644238737685fb2ae019a5ec990b6eb91d5983beba6d334586a1c21a700e`

## 2026-05-03 09:31 追加状态（P0-UI-LOCKDOWN-001）

- **核心问题**：手机网页和 G2 眼镜端状态深度耦合，tab 点击时触发 G2 业务逻辑，导致页面龟缩/串页
- **修复方案**：
  - 新增 `src/ui/phoneUiState.ts`（单一真相源）：`setPhoneActiveBookmark()` 是唯一合法修改 `dataset.activeBookmark` 的途径
  - 新增 `src/ui/phonePageRegistry.ts`（页面锁页）：每个书签只允许显示规定的区块
  - 重构 `selectG2Bookmark()`：只更新 G2 ring 导航，不再触碰手机状态
  - 重构 `renderBookmarkChrome()`：只更新 G2 连接 footer，不再管理手机书签状态
  - 书签 tab 点击处理器：只调用 `setPhoneActiveBookmark()`，不触发任何 G2 业务逻辑
  - CSS 新增 `.is-visible` 类机制：通过 `phonePageRegistry` 统一控制页面区块显示/隐藏
  - HTML 新增 `data-phone-section` 属性：标记所有页面区块
  - 布局稳定性：`body` 改 `overflow-y:auto`，`#app` 改 `height:auto`
- **测试结果**：build ✓（27 modules，178.93 kB）/ pack ✓（75591 bytes）
- **修改文件**：`main.ts`、`style.css`、`index.html`（源+dist）、`phoneUiState.ts`、`phonePageRegistry.ts`
- 最新 EHPK SHA256：`1d474484bff21236e42a47b7605ec39caceb51a88652c543566f127f2e3d110d`

## 2026-05-03 09:43 追加状态（P0-BATTERY-001）

- **核心问题**：手机网页顶部 G2/R1 电量长期显示 `--%`，无缓存机制，设置页无电量调试区
- **修复方案**：
  - 新增 `src/device/batteryCache.ts`：localStorage 电量缓存，页面刷新后优先恢复缓存值
  - 新增 `src/device/extractBatterySnapshot.ts`：多来源电量解析，支持所有已知字段名称和嵌套结构
  - `initBatteryDisplay()`：启动时从缓存恢复电量，避免刷新后长期显示 `--%`
  - `updateDeviceBatteryFromInfo/Status()`：每次拿到有效电量时写入缓存
  - 设置页新增"设备电量"调试面板：`#battery-debug-info` + `#refresh-battery-button`
  - 顶部初始文案从 `G2 --%` 改为 `G2 加载中`，JS 运行后立即更新
- **测试结果**：build ✓（29 modules，182.52 kB）/ pack ✓（76461 bytes）
- **修改文件**：`main.ts`、`style.css`、`index.html`（源+dist）、`device/batteryCache.ts`、`device/extractBatterySnapshot.ts`
- 最新 EHPK SHA256：`2d6b2f0d08642ebfc97e9254e842ce0859ac8f9d8a0810564b4a004d01f12987`

## 2026-05-03 10:45 追加状态（TRADING-SIX-CATEGORIES）

- **交易状态 6 类数据播报**：
  - 手机网页：6 个预设快捷按钮（运行状态/白名单价格/持仓盈亏/风控状态/资金分布/订单归因）
  - 眼镜端：6 个 R1 可触子页面（trading_status / trading_prices / trading_positions / trading_distribution / trading_attribution / trading_alerts）
  - R1 单击循环切换 6 个眼镜页面
  - 数据来自 `/trading/overview` 单次获取后缓存，无需重复请求
- **测试结果**：build ✓（29 modules，188.02 kB）/ pack ✓（77941 bytes）
- **修改文件**：`index.html`、`style.css`、`main.ts`、`glass/glassScreens.ts`
- 最新 EHPK SHA256：`98a4687b08023cb3af86048827d84f457750fec636fad04e3c9f014d3ecefb5a`

## 2026-05-03 10:15 追加状态（GLASS-UI-DIRECT-REPLACE）

- **眼镜端 UI 直接替换**：GPT 生成的 `glassScreens.ts` 和 `glassLayout.ts` 已替换
- **phonePageRegistry.ts** 补全缺失的 `diagnostics/history/debug` 书签类型
- **测试结果**：build ✓（29 modules，182.93 kB）/ pack ✓（76377 bytes）
- 最新 EHPK SHA256：`9adbe30a41a32fd7d4a9b0b13f60ed2d76908a0bd8de519cbe84d22affe737f2`

## 2026-05-04 10:40 追加状态（P0-CLOUD-001）

- **GPT 云盘审批闭环配置完成**：
  - iCloud 目录：outbox / inbox-from-gpt / archive / latest / logs
  - Claude 命令：g2-make-review-bundle / g2-apply-gpt-review / g2-check-cloud
  - 脚本：cloud_config.sh / prepare_review_bundle.sh / check_gpt_inbox.sh
  - 模板：GPT_REVIEW_TEMPLATE.md
- **测试 Bundle**：`docs/gpt-advisor/bundles/20260504_1040_cloud_setup_test.zip`
- **iCloud outbox**：`20260504_1040_cloud_setup_test.zip`
- **SHA256**：`2b8de039f19267565e417a5dba04d89994651704034446cfd62d1775ab7fd172`
- **typecheck**：✓ PASSED

最近版本号：

```text
0.5.0
```

后续每次打包必须写入 `test-reports/`。

## 2026-05-04 11:45 Day 0 完成（工作流闭环 + UI 锁页冻结）

### 天禄 G2 进化日程启动

来源计划包：`/Users/luxiangnan/Desktop/GPT协作解决方案/1、天禄 G2 进化日程 + Claude:GPT 闭环工作流包.zip`

已读取：
- `PROJECT_EVOLUTION_ROADMAP_20260504.md` — 完整 18 天计划
- `CLOSED_LOOP_WORKFLOW_GPT_CLAUDE.md` — Claude ↔ GPT 闭环工作流
- `CLAUDE_REPORTING_RULES.md` — 固定报告规则

### Day 0 验收清单

| 验收项 | 状态 |
|---|---|
| `/g2-status` 命令 | ✓ 当前项目有完整状态文件 |
| `/g2-pack` 命令 | ✓ npm run typecheck/build/pack 正常工作 |
| 每次任务有 report | ✓ test-reports/ 目录已建立 |
| 每次任务有 EHPK + SHA256 | ✓ 本次已生成 |
| Phone/Glass UI 隔离 | ✓ phoneUiState.ts / phonePageRegistry.ts 已建立 |
| Claude → GPT → Claude 闭环 | ✓ iCloud outbox/inbox-from-gpt 已配置 |

### 当前 EHPK 状态

- **版本**：`0.5.0`
- **SHA256**：`b6aaaaa934556671de3dce29571ee96ccb6b86a2c47a2f621d2d626dd65e3394`
- **大小**：79471 bytes
- **路径**：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- **typecheck**：✓ PASSED
- **build**：✓ PASSED（30 modules）

### P0 问题冻结清单（Day 0 截止）

以下问题必须在 Day 1-5 (05-05 ~ 05-08) 完成：

1. **P0-R1-ACCURACY**：R1 选择视觉识别后，手机取消拍照，眼镜仍显示拍照采集
2. **P0-GLASS-HOME-4MENU**：首页必须按用户最终模板显示 4 项一行
3. **P0-GLASS-SYSTEM-SETTINGS**：系统设置菜单看不见但能误选
4. **P0-VISION-CANCEL**：手机取消拍照/选图后眼镜卡死
5. **P0-VOICE-LINKAGE**：G2 麦克风 PCM 语音链路未真机验收
6. **P0-SPEECH-INTENT**：语音意图触发视觉未稳定

### Day 1 计划（2026-05-05）

```
1. 首页改成用户最终模板（4 项一行）
2. 系统设置可见可进入
3. R1 焦点与眼镜菜单完全一致
4. 所有眼镜页面去掉横线和框线
5. 给所有眼镜端异步流程加 activeGlassSessionId
```

### 闭环状态

```
CLAUDE_DONE: Day 0 工作流闭环建立
CLAUDE_DONE: Day 1 R1准确度+首页4菜单 代码完成
GPT_REVIEWING: 待 GPT 审核 Day1 完成报告
```

### Day 1 完成项

| 模块 | 状态 |
|------|------|
| R1 取消返回机制 | ✓ 代码完成 |
| 首页 4 菜单一行 | ✓ 代码完成 |
| 系统设置可见可进入 | ✓ 代码完成 |
| 语音意图触发视觉 | ✓ 代码完成 |
| 交易标签分类 | ✓ 代码完成 |
| G2 页面去横线框线 | ✓ 代码完成 |

### 当前版本

- **版本**：0.5.2
- **SHA256**：`a3ce89051b8fd8304b467823504de7ef7379420130911db31eba196b5d36f83a`
- **EHPK**：apps/evenhub-plugin/g2-vision-voice-assistant.ehpk
