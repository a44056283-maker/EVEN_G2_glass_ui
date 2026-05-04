# P0-001 网页视觉识别闭环测试报告

生成时间：2026-05-02 10:11

## 1. 本轮范围

本轮只修复网页视觉识别闭环。

未修改：

- R1 相机控制状态机
- G2 麦克风
- ASR
- OpenCLAW
- 交易机器人接口
- Glass UI 大改
- 手机网页视觉美化

## 2. 审计结论

1. 当前首页“视觉识别”一级入口绑定：
   - `#capture-button` -> `selectG2Bookmark('vision')` -> `renderG2Bookmark()`
   - 一级入口本身不直接拍照。

2. 点击“视觉识别”是否直接触发拍照：
   - 否。
   - 真正问题是二级动态按钮 `quick-action-0 / vision-capture` 原来调用 `runR1CaptureFlow()`，导致网页拍照按钮走了 R1 视觉状态机。

3. 视觉识别子版块是否存在：
   - 存在，使用 `.quick-panel` + `.status-panel`。
   - 本轮新增 `.vision-result-panel` 用于稳定显示结果。

4. “拍照识别 / 直接拍照 / 从相册选择”按钮：
   - 动态按钮：`quick-action-0`，文本为“拍照识别”。
   - 文件/相机 fallback：`#direct-camera-label` -> `#file-fallback`。

5. 当前获取图片路径：
   - 网页普通拍照：`capturePhoto()`。
   - iOS / embedded browser 默认走 `file input` fallback。
   - 非嵌入安全上下文可走 `getUserMedia({ video, audio:false })`。
   - R1 相关隐藏 video stream 在 `cameraStream.ts`，本轮未改。

6. POST /vision 前端调用：
   - `apps/evenhub-plugin/src/api.ts` 的 `recognizeImage()`。

7. /vision 后端路由：
   - 实际路径为 `services/api-server/src/server.ts`，不是 `services/g2-bridge/src/server.ts`。
   - 不存在 `services/g2-bridge/src/routes/vision.ts`。

8. /vision 成功后结果显示：
   - 手机网页：本轮新增 `#vision-result-answer`。
   - G2 Glass UI：`GlassRenderer.show('reply', { answer })`。

9. TTS 是否阻塞结果显示：
   - 本轮确保文字结果和 G2 显示先执行。
   - TTS 失败只更新状态，不影响文字结果。

10. 失败提示是否清晰：
   - 本轮新增 `formatVisionError()`，处理相机权限、空图片、网络失败、后端视觉接口失败。

## 3. 修改文件

- `apps/evenhub-plugin/index.html`
- `apps/evenhub-plugin/src/style.css`
- `apps/evenhub-plugin/src/main.ts`
- `packages/shared/src/index.ts`
- `services/api-server/src/server.ts`
- `docs/gpt-advisor/patch-requests/20260502_1004_p0_web_vision_loop_patch_request.md`

## 4. 当前按钮绑定关系

一级入口：

```text
#capture-button
-> selectG2Bookmark('vision')
-> renderG2Bookmark()
```

不拍照、不上传、不 TTS。

网页二级“拍照识别”：

```text
quick-action-0 / vision-capture
-> runCaptureFlow()
-> capturePhoto()
-> recognizeImage()
```

本轮没有改 R1 状态机里的 `handleVisionR1Intent()`。

## 5. 图片获取路径

当前网页路径：

```text
capturePhoto()
-> iOS / embedded browser: file input fallback
-> otherwise: prepared photo or getUserMedia video
-> imageFileToCapturedImage()
-> compressDataUrl()
```

图片压缩参数：

```text
MAX_IMAGE_EDGE = 1280
JPEG_QUALITY = 0.72
```

## 6. /vision 请求日志摘要

前端已新增 console 日志：

```text
[P0 vision] image ready
[P0 vision] upload start
[P0 vision] upload success
```

记录内容：

- imageBase64 length
- estimated bytes
- API URL
- request start time
- elapsed ms
- answer length
- description length
- provider

## 7. 手机网页结果显示

新增页面区域：

```text
.vision-result-panel
#vision-result-meta
#vision-image-info
#vision-result-answer
```

显示：

- 结果状态
- 图片大小
- data length
- 耗时
- 来源
- 识别回答

## 8. G2 结果显示文案

成功：

```text
TL-REPLY     AI
----------------------
{识别结果摘要}

R1 单击返回
```

失败：

```text
TL-ERROR     SYS
----------------------
{错误摘要}

R1 单击重试
下滑返回
```

G2 显示失败时：

```text
G2 显示失败，但网页结果已生成。
```

网页结果仍保留。

## 9. 后端 /vision 状态

本轮仅小改返回结构：

```json
{
  "answer": "...",
  "description": "...",
  "provider": "...",
  "source": "vision-api",
  "elapsedMs": 1234,
  "createdAt": "..."
}
```

注意：

- 线上公网后端当前仍返回旧字段，需要后端重新部署后才会出现 `source/elapsedMs`。
- 前端闭环不依赖这两个新增字段。

## 10. 实测结果

### typecheck

命令：

```bash
npm run typecheck
```

结果：通过。

### build

命令：

```bash
npm run build
```

结果：通过。

### pack

命令：

```bash
npm run pack:g2
```

结果：通过。

### 公网 /health

命令：

```bash
curl https://g2-vision.tianlu2026.org/health
```

结果：HTTP 200，`ok: true`。

### 公网 /vision

测试图片：

```text
store-assets/g2-vision-ai-cover-576x288.png
```

结果：HTTP 200。

摘要：

```text
G2 Vision AI视觉助手。
拍照识别→镜片显示，语音朗读回答。
集成MiniMax AI问答与记忆检索。
眼镜+手机联动使用。
```

耗时：约 12.3 秒。

## 11. EHPK

路径：

```text
apps/evenhub-plugin/g2-vision-voice-assistant.ehpk
apps/evenhub-plugin/g2-视觉-语音助手.ehpk
```

SHA256：

```text
530c9cfa2f35c9cfa3fbd41a66eed20d64bf1aa9fcb1b39b1596018e4589e6ca
```

## 12. 仍未解决的问题

- 还未做真机手机网页点击拍照验证。
- 还未验证 iPhone Even App WebView 是否会弹出系统相机/相册。
- 线上后端未重新部署，`source/elapsedMs` 暂未出现在公网返回体。
- R1 相机控制未在本轮修改。
- G2 真机显示结果仍需用户实测。

## 13. 下一步建议

先让用户用手机网页测试 P0：

```text
点击视觉识别
-> 点击拍照识别
-> 拍照/选图
-> 查看视觉结果面板
```

如果网页 P0 真机通过，再进入：

```text
P0-002：R1 相机控制
```

