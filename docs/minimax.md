# MiniMax 适配说明

## 角色划分

- M2.7 / M2.7-highspeed：文本理解、总结、回答组织
- Speech：TTS
- 视觉：通过 `vision-adapter` 接入，可先用 stub，后续接 VLM
- ASR：通过 `asr-adapter` 接入，V0 先 stub，后续接 Web Speech / Whisper / 其他服务

## 环境变量

```bash
MINIMAX_API_KEY=replace_with_your_key
MINIMAX_BASE_URL=https://api.minimaxi.com/v1
MINIMAX_TEXT_MODEL=MiniMax-M2.7-highspeed
MINIMAX_TTS_MODEL=speech-2.8-hd
```

## 注意

MiniMax TTS 不同账号或版本的 endpoint 和返回字段可能有差异，所以 TTS 代码被隔离在 `packages/minimax-adapter/src/index.ts`。一旦账号后台确认最终接口，只改 adapter，不动 G2 前端。

## Token Plan 使用策略

当前套餐支持 `MiniMax-M2.7-highspeed`、图像理解、联网搜索 MCP、图片/语音/音乐/视频生成。V0 只做用户点击触发的拍照识别，避免无意义消耗；视频抽帧版再加入变化检测和最小 10 秒上传间隔。

当前账号使用中文开放平台，base URL 为 `https://api.minimaxi.com/v1`。

图片理解当前接入 `VISION_PROVIDER=minimax-vlm`，调用 `/coding_plan/vlm`。前端会先把 iPhone 原图压缩到最长边 1280px 后再上传，避免请求体过大。

## 能力矩阵

| 能力 | 后端接口 | 当前状态 |
| --- | --- | --- |
| 文本生成 | `/ask`、`/vision` 二次整理 | 已接入 |
| 图片理解 | `/vision` -> `/coding_plan/vlm` | 已接入 |
| TTS HD | `/tts` | adapter 已有，待按最终接口细化 |
| 联网搜索 MCP | `/search` | 待接入 |
| ASR | `/transcribe` | stub，后续接入 |
| 图片生成 | `/generate-image` | 预留 |
| 音乐生成 | `/generate-music` | 预留 |
| 视频生成 | `/generate-video` | 预留 |

第一版眼镜体验只启用文本、图片理解、TTS。生成图片、音乐、视频消耗较大，适合做后台工具或演示，不适合作为眼镜点击识别的默认链路。
