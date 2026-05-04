# 问题登记表

更新时间：2026-05-02

| ID | 严重度 | 模块 | 问题 | 当前状态 | 下一步 |
| --- | --- | --- | --- | --- | --- |
| G2-001 | P0 | 网页视觉识别 | 点击视觉识别后相机/识别链路不稳定 | 已通过用户真机反馈 | 后续只做回归，不在 P0-002 中重改 |
| G2-002 | P0 | 图片上传 | 图片过大时后端报 `Request body is too large` | 已知 | 前端压缩图片，后端确认 body limit |
| G2-003 | P0 | G2 UI | 眼镜端曾出现显示混乱或空白 | 进行中 | 保持单容器 GlassRenderer，逐屏真机验收 |
| G2-004 | P0 | R1 输入 | R1 无法稳定进入视觉/确认拍照 | 已改为 R1 单触两步流程，待真机确认 | 测试 R1 首次单触拍照/暂存、600ms 后再次单触上传、上滑重拍、下滑取消 |
| G2-005 | P1 | G2 麦克风 | 语音链路提示麦克风权限或收不到 PCM | R0-003 已实现按住说话、G2 PCM 会话、`end_of_speech` 和 mock-asr 路由，待真机看 bytes/chunks | 安装新 EHPK，点“呼叫天禄/语音对话”，确认 `audioControlCalled=true`、`wsStatus=open`、`totalBytes/chunks` 增长，并返回 `final_transcript` |
| G2-006 | P1 | ASR | `MINIMAX_ASR_ENDPOINT` 为空，MiniMax ASR 不确定 | 已改走本地 Whisper ASR，`/transcribe` 已通过 | 真机验证手机/G2 音频能否上传到本地 ASR |
| G2-007 | P1 | OpenCLAW | 真实问答可能 Gateway timeout | 已知 | `/ask` 必须 fallback |
| G2-008 | P1 | 交易状态 | 语音问答曾返回 mock-momentum / 持仓 2 个，且前端曾读取局域网 192.168.13.48:9099 | 已切换为 https://console.tianlu2026.org 公网实时只读源，并新增 `/glasses/api/*` 聚合接口；交易概览已增加 7 项摘要与 MiniMax-M2.7 持仓评测 | 真机刷新交易页，确认不再显示局域网 fetch failed；下一步让语音交易问答复用同一套 AI 评测 |
| G2-010 | P1 | 白名单价格 | 白名单实时价格曾混入持仓交易对，并优先显示旧缓存价 | 已修复：只读取 `TRADING_ALLOWED_SYMBOLS`，优先公网 `/api/prices/realtime`；验证返回 5 个白名单币种 | 真机刷新交易页，确认白名单价格显示 BNB/BTC/DOGE/ETH/SOL 且不再显示备份路径 |
| G2-011 | P1 | 交易历史 | 旧历史记录里残留 `edict_backup`、`real_report_*`、`MEMORY.md` 等备份路径 | 已在 `history.ts` 增加详情清洗规则 | 若真机仍显示旧路径，清空前端历史记录并重新生成 |
| G2-009 | P2 | 电量 | R1 电量读不到，长期显示 `--%` | 已完成多来源缓存：`batteryCache.ts`（localStorage）、`extractBatterySnapshot.ts`（所有已知字段）；设置页新增”设备电量”调试面板；`initBatteryDisplay()` 启动时恢复缓存 | 安装新 EHPK（SHA256：`2d6b2f0d08642ebfc97e9254e842ce0859ac8f9d8a0810564b4a004d01f12987`）后真机验证；若仍”未上报”，抓 `[G2 device info]` / `[G2 device status]` 原始日志确认字段 |
| G2-010 | P1 | 呼叫天禄 | 普通问答曾返回”收到问题/会显示在这里”占位回复，且 Voice Debug 挤在回答下方 | 已增加 MiniMax 严格二次追问、本地 fallback、语音页保持 active、Voice Debug 默认隐藏 | 上传最新 EHPK 后真机验证普通问答和语音页是否仍跳菜单 |
| G2-011 | P0 | 手机网页 UI | 修改 G2 眼镜端页面后，手机插件网页 bookmark 导航被污染：点击”设置”后书签编号显示 1/3 而非 4/4，openclaw 面板不显示 | 已完成架构级隔离：`phoneUiState.ts`（单一真相源）、`phonePageRegistry.ts`（页面锁页）；tab 点击只调用 `setPhoneActiveBookmark()`，不再触发 G2 业务逻辑 | 安装新 EHPK（SHA256：`1d474484bff21236e42a47b7605ec39caceb51a88652c543566f127f2e3d110d`）后真机验证 4 个书签切换正常 |
| G2-012 | P0 | 手机网页 UI 龟缩 | 页面布局过于脆弱，`overflow:hidden` + `100dvh` 导致页面龟缩、串页 | 已改 `body` 为 `overflow-y:auto`，`#app` 改 `height:auto` + `align-content:start`；CSS 改用 `.is-visible` 类控制显示 | 同 G2-011 |

## 严重度说明

- P0：阻塞核心使用，必须优先修。
- P1：核心链路重要问题，P0 后修。
- P2：增强或体验问题。
- P3：优化项。
