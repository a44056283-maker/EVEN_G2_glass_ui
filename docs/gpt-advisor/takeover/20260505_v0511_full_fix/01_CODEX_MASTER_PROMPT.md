# Codex Master Prompt｜接管天禄 G2 助手 v0.5.11 修复任务

请进入项目目录：

```text
/Users/luxiangnan/Desktop/EVEN G2视觉和语音对讲系统/g2-vision-voice-assistant
```

GitHub 仓库：

```text
https://github.com/a44056283-maker/EVEN_G2_glass_ui
```

## 0. 身份

你现在接替 Claude，成为“天禄 G2 助手”项目的主控工程代理。  
你必须像 Codex 工程代理一样工作：

```text
先读历史
再审计
再分工
再最小补丁
再多轮测试
再真机验收
再打包上架
```

不要直接乱改代码。  
不要只写报告不修复。  
不要绕开用户提出的问题。  
不要再输出半成品。

## 1. 必须先读取的历史和记忆

请先读取：

```text
CLAUDE.md
docs/gpt-advisor/CURRENT_STATUS.md
docs/gpt-advisor/NEXT_ACTIONS.md
docs/gpt-advisor/ISSUE_REGISTER.md
docs/gpt-advisor/MODULE_MAP.md
TIMED_PROGRESS_LOG.md
docs/gpt-advisor/test-reports/
04_GPT_REVIEW_RESPONSES/
```

重点读取最近这些状态：

```text
P0 CORE TRUE_DEVICE PASSED
P1-STABILIZE-001
v0.5.11 当前测试版问题
OpenCLAW / 历史记录 / 交易白名单价格页相关报告
```

如果文件不存在，先用 `rg` 搜索相关关键词：

```bash
rg -n "P0 CORE TRUE_DEVICE|v0.5.11|OpenCLAW|history|localStorage|白名单|trading_prices|renderTradingPrices|cancelCurrentGlassOperation|isVisionVoiceIntent" .
```

## 2. 当前 v0.5.11 真实问题

用户真机测试 v0.5.11 后反馈 7 个问题：

### 问题 1：闪退

```text
使用眼镜端时存在闪退情况。
需要审计本地服务端日志、前端日志、Even WebView 控制台日志、API server 日志。
```

### 问题 2：缺少定位获取能力

```text
识别图片后不能根据所在位置判断所在场景、具体场所和正确答案。
需要获取手机定位，并将定位上下文加入视觉识别 prompt。
```

### 问题 3：拍照后 G2 没有短暂预览 / 没有明确拍摄成功提示 / 不能保存历史

```text
拍照后眼镜端应短暂显示“照片已拍摄/正在识别”，最好能显示图片预览；若 G2 当前只支持 TextContainer，则必须显示文本预览确认。
手机端必须保存视觉历史，包括缩略图/摘要/时间/问题/回答。
```

### 问题 4：手机端运行历史和全部历史记录没有信息

```text
历史记录体系不可靠。localStorage 可能失败，必须改成 IndexedDB 优先，localStorage fallback，memory fallback，并显示错误提示。
```

### 问题 5：识图能力不准

```text
需要增强视觉识别：
- 图片 + 定位上下文
- OCR/场景关键词
- 本地知识库 / OpenCLAW 天禄记忆
- 可选线上搜索权限
- 低置信度时二阶段复核
- 不要自动学习错误内容，必须可审计写入知识库
```

### 问题 6：交易状态子菜单确认不准、数据载入延时过大

```text
进入交易状态后有点飘，数据加载慢。
需要增加缓存、等待话术、加载状态、防抖、stale-while-revalidate。
```

### 问题 7：交易状态 R1 选择子菜单后，焦点/图标没有移到子菜单项上

```text
这可能导致子菜单数据不能准确加载。
需要修复 trading menu 的 focus state，让 R1 焦点真正属于 trading submenu，而不是首页或手机 DOM。
```

## 3. 不允许做的事

禁止：

```text
1. 不要改交易写接口。
2. 不要实现自动交易。
3. 不要把 Phone UI 和 Glass UI 再次混用。
4. 不要把 token / .env / API key / 交易密钥写入 GitHub。
5. 不要继续推进 liveVisionSampler、视频片段、场景记忆，除非本轮 7 个问题全部修复并通过验收。
6. 不要宣称真机通过，除非用户明确反馈通过。
7. 不要只给报告不改代码。
8. 不要再做“代码完成但不能用”的半成品。
```

## 4. 子智能体分工

请创建/调用以下子任务。可以用项目内 `.claude/agents` 方式，也可以由 Codex 主控模拟这些代理并串行合并补丁。

### Agent A：crash-log-agent

职责：

```text
1. 审计服务端日志、前端日志、WebView 可能 crash 点。
2. 增加全局错误捕获：
   - window.onerror
   - unhandledrejection
   - API error trace
3. 增加 crash report 写入 docs/gpt-advisor/logs/ 或 debug panel。
4. 排查 G2 TextContainer 文本过长、异步回写、R1 高频事件导致的闪退。
5. 生成 crash_audit_report。
```

### Agent B：location-vision-agent

职责：

```text
1. 增加手机定位获取能力。
2. 不强制定位，用户授权后使用。
3. 将经纬度、时间、粗略位置、可选 reverse geocode 加入视觉 prompt。
4. 定位失败时不影响识图。
5. 不把精确定位写入公开日志。
```

### Agent C：photo-preview-history-agent

职责：

```text
1. 拍照后 G2 显示短暂确认：
   “照片已拍摄”
   “正在识别”
2. 如果 Even G2 SDK 支持图片/图像容器，审计并尝试极小预览；如果不支持，必须明确使用文字确认。
3. 保存视觉历史：
   - 时间
   - 问题
   - 回答
   - 摘要
   - 低分辨率缩略图
4. 历史用 IndexedDB 优先，localStorage fallback，memory fallback。
5. 历史写入失败必须提示。
```

### Agent D：vision-accuracy-agent

职责：

```text
1. 优化视觉 prompt。
2. 加入定位上下文。
3. 加入历史上下文。
4. 加入 OpenCLAW 天禄记忆上下文。
5. 可选线上搜索权限接口，但默认关闭，由设置页开关控制。
6. 低置信度时二阶段复核：
   - 第一次 VLM 识别
   - 提取关键词/OCR/场景
   - 使用知识库或在线搜索补充
   - 再输出结论
7. 不自动把错误识别写入知识库。
```

### Agent E：trading-cache-focus-agent

职责：

```text
1. 修复交易子菜单焦点。
2. R1 进入交易后，焦点必须移到子菜单项。
3. next/previous 只在交易标签内切换。
4. click 进入当前标签详情。
5. 详情页 click 刷新当前标签。
6. 加交易缓存：
   - lastTradingOverview
   - lastTradingFetchedAt
   - TTL 15 秒
   - stale data 可显示
   - 后台刷新
7. 加载慢时 G2 显示：
   “正在载入交易数据”
   “显示上次缓存”
   “刷新中”
```

### Agent F：qa-release-agent

职责：

```text
1. 多轮测试。
2. typecheck/build/pack:g2。
3. EHPK SHA256。
4. 真机验收矩阵。
5. 不通过不允许上架。
```

## 5. 执行顺序

请严格按顺序：

```text
Step 1：只读审计 7 个问题，输出根因表。
Step 2：按照 Agent A-E 分工生成补丁方案。
Step 3：先修 crash 和日志，不然无法定位闪退。
Step 4：修历史保存，因为视觉、语音、交易都依赖历史。
Step 5：修定位 + 视觉 prompt。
Step 6：修拍照确认/历史缩略图。
Step 7：修交易缓存和焦点。
Step 8：修视觉准确性增强。
Step 9：跑 typecheck/build/pack:g2。
Step 10：生成测试版 EHPK。
Step 11：用户真机多轮测试。
Step 12：只在真机通过后生成 Release Candidate。
```

## 6. 具体代码任务

### 6.1 闪退日志

新增或增强：

```text
apps/evenhub-plugin/src/diagnostics/runtimeErrorReporter.ts
services/api-server/src/logger.ts
docs/gpt-advisor/logs/
```

要求：

```text
1. window.onerror -> 写入 debug panel + history diagnostic
2. window.onunhandledrejection -> 写入 debug panel
3. API server 增加 requestId / error stack
4. G2 渲染失败 safeGlassShow 必须 catch 并记录
5. R1 事件防抖：100-200ms 内重复事件忽略
```

### 6.2 定位

新增：

```text
apps/evenhub-plugin/src/location/locationContext.ts
```

能力：

```ts
export type LocationContext = {
  latitude?: number
  longitude?: number
  accuracy?: number
  city?: string
  addressHint?: string
  capturedAt?: string
  error?: string
}

export async function getLocationContextForVision(): Promise<LocationContext>
```

规则：

```text
1. 使用 navigator.geolocation.getCurrentPosition。
2. 超时 5 秒。
3. 成功后缓存 5 分钟。
4. 设置页增加定位开关。
5. 失败时返回 error，不阻塞视觉识别。
6. 不在公开报告中输出精确坐标。
```

### 6.3 视觉 prompt

修改视觉请求前的 prompt 构建：

```text
请把以下上下文加入视觉识别：
- 用户问题
- 拍摄时间
- 粗略位置/场景
- 最近视觉历史摘要
- OpenCLAW 天禄记忆摘要（如果可用）
```

### 6.4 拍照预览

拍照成功后立即：

```text
G2:
照片已拍摄
正在识别...
```

如果有尺寸信息：

```text
照片已拍摄 1280x720
正在识别...
```

手机端显示缩略图。

### 6.5 历史记录

新增：

```text
apps/evenhub-plugin/src/history/historyStore.ts
```

要求：

```text
IndexedDB primary
localStorage fallback
memory fallback
错误提示
写入结果返回 boolean / error
```

保存类型：

```text
vision
voice
trading
openclaw
settings
diagnostic
```

### 6.6 视觉准确性

增加：

```text
apps/evenhub-plugin/src/vision/visionPromptBuilder.ts
services/api-server/src/visionKnowledge.ts
services/api-server/src/webSearchAdapter.ts
```

webSearch 默认关闭：

```env
VISION_WEB_SEARCH_ENABLED=false
```

只有设置页打开才使用。

OpenCLAW 记忆可作为知识库：

```text
先问 OpenCLAW 相关记忆摘要
再辅助视觉回答
```

但不要无限等待，timeout 5 秒。

### 6.7 交易白名单价格和子菜单焦点

修：

```text
apps/evenhub-plugin/src/main.ts
apps/evenhub-plugin/src/glass/glassScreens.ts
```

规则：

```text
1. entering trading -> tradingMenuMode='menu'
2. tradingSubPageIndex 控制焦点
3. renderer.show('trading_menu', { activeIndex })
4. next/previous 只改变 activeIndex
5. click 进入 detail
6. detail click 刷新当前 detail
7. 数据未到时显示“正在载入...”
8. 有缓存时先显示缓存，再后台刷新
```

白名单价格页只显示：

```text
BTC
ETH
SOL
BNB
DOGE
```

示例：

```text
BTC  68321.45      ETH  3520.18
SOL  172.31        BNB  597.20
DOGE 0.1534
```

## 7. 测试

必须执行：

```bash
npm run typecheck
npm run build
npm run pack:g2
```

并生成：

```text
docs/gpt-advisor/test-reports/YYYYMMDD_HHMM_v0511_full_fix_report.md
```

## 8. 真机验收

真机至少跑 3 轮，每轮包括：

```text
1. 启动眼镜端 5 分钟不闪退
2. 视觉识别 5 次
3. 取消拍照 2 次
4. 定位识图 3 次
5. 照片历史保存 3 次
6. 语音触发视觉 3 次
7. 交易白名单价格 3 次
8. 交易标签切换 3 次
9. OpenCLAW 记忆问答 2 次
10. 历史记录刷新 2 次
```

不通过则继续修，不准上架。

## 9. 输出

完成后输出：

```text
1. 7 个问题逐项修复状态
2. 修改文件列表
3. 测试结果
4. 真机验收结果
5. EHPK 路径
6. SHA256
7. 未解决问题
8. 是否允许上架
```

## 10. 版本

本轮修复完成后，版本号建议为：

```text
0.5.12 或 0.6.0-rc1
```

如果仍需真机测试，不要叫正式版，只叫：

```text
0.5.12-test
```
