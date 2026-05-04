# 本机服务端审计报告

**审计时间**：2026-05-03 00:45
**审计人**：Claude Code

---

## 端口总览

| 端口 | 类型 | 进程 | 用途 |
|------|------|------|------|
| 3031 | TCP | Apple eppc | Apple Event Publisher（系统服务） |
| 3456 | TCP | Apple vat | Apple VideoPhone（系统服务） |
| 5000 | TCP | ControlCenter | Apple 系统控制服务 |
| **5173** | TCP | node/vite | **G2 Vision Voice Assistant 前端开发服务器** |
| 5900 | TCP | Apple rfb | VNC 远程桌面（系统服务） |
| 7000 | TCP | ControlCenter | Apple 系统控制服务 |
| 7897 | TCP | Clash Verge Meta | 代理/VPN 服务 |
| **8081** | TCP | Python | 交易机器人 V6.5 实例 1 |
| **8082** | TCP | Python | 交易机器人 V6.5 实例 2 |
| **8083** | TCP | Python | 交易机器人 V6.5 实例 3 |
| **8084** | TCP | Python | 交易机器人 V6.5 实例 4 |
| **8181** | TCP | Python | 8081 反向代理（本地） |
| **8182** | TCP | Python | 8082 反向代理（本地） |
| **8183** | TCP | Python | 8083 反向代理（本地） |
| **8184** | TCP | Python | 8084 反向代理（本地） |
| **8787** | TCP | Node.js (tsx) | **g2-vision-voice-api 后端主服务** |
| **8791** | TCP | Python | **Local Whisper ASR 本地语音识别服务** |
| 33331 | TCP | Clash | Clash 代理管理界面 |

---

## 服务详情

### 1. G2 Vision Voice Assistant 前端（端口 5173）

**进程**：`/Users/luxiangnan/Desktop/EVEN G2视觉和语音对讲系统/.tools/node-current/bin/node .../vite.js --host 0.0.0.0`

**当前状态**：Vite 开发服务器运行中，使用 `--host 0.0.0.0` 允许外部访问

**监听地址**：`*:5173`

**与 Even App 的关系**：
- Even App 访问 `http://192.168.13.104:5173/` 来加载插件页面
- 已建立 ESTABLISHED 连接：来自 `192.168.13.48`（手机或眼镜设备）

**生产环境问题**：
- `g2-vision.tianlu2026.org` 目前指向的服务器运行着 Vite 开发模式（`src="/@vite/client"`）
- 这不是生产就绪状态；Vite dev mode 不应该暴露在公网

---

### 2. g2-vision-voice-api 后端（端口 8787）

**进程**：`/Users/luxiangnan/Desktop/EVEN G2视觉和语音对讲系统/.tools/node-v22.22.2-darwin-arm64/bin/node --require .../tsx/dist/preflight.cjs --import .../tsx/dist/loader.mjs src/server.ts`

**工作目录**：`/Users/luxiangnan/Desktop/EVEN G2视觉和语音对讲系统/g2-vision-voice-assistant/services/api-server/src/`

**健康检查**：`GET /health`

```json
{
  "ok": true,
  "service": "g2-vision-voice-api",
  "time": "2026-05-02T16:42:35.027Z",
  "openclaw": {
    "enabled": true,
    "baseUrl": "https://even2026.tianlu2026.org",
    "model": "g2-bridge",
    "agent": "open law2026"
  }
}
```

**主要路由**：

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/vision` | 视觉识别（图片 → MiniMax VLM → 描述 → LLM 回答） |
| POST | `/ask` | 通用问答（MiniMax / OpenCLAW） |
| GET | `/audio` | WebSocket：G2 麦克风 PCM 语音识别 |
| GET | `/trading/overview` | 交易只读概览（enriched with AI） |
| GET | `/glasses/api/summary` | 眼镜聚合接口：概要 |
| GET | `/glasses/api/prices` | 眼镜聚合接口：白名单价格 |
| GET | `/glasses/api/positions` | 眼镜聚合接口：持仓明细 |
| GET | `/glasses/api/l5` | 眼镜聚合接口：L5 资金流 & 归因 |
| GET | `/glasses/api/pair/:pair` | 眼镜聚合接口：单交易对详情 |
| GET | `/glasses/api/alerts` | 眼镜聚合接口：告警列表 |
| POST | `/openclaw/ask` | OpenCLAW 对话 |
| GET | `/openclaw/status` | OpenCLAW 状态 |
| POST | `/tts` | TTS 语音合成（MiniMax） |
| POST | `/transcribe` | 语音转文字（Local Whisper） |
| GET | `/asr/status` | ASR 状态 |
| GET | `/memory/search` | 天禄记忆搜索 |

**安全问题**：
- CORS: `origin: true`（允许所有来源）—— 开发阶段可接受，生产应限制
- 无认证保护（`G2_BRIDGE_SESSION_TOKEN` 可选）
- `/tts`、`/transcribe`、`/memory/search` 等接口无访问控制

---

### 3. Local Whisper ASR（端口 8791）

**进程**：`/Library/Frameworks/Python.framework/Versions/3.11/Resources/Python.app/Contents/MacOS/Python .../services/local-whisper-asr/server.py`

**健康检查**：`GET /health`

```json
{
  "ok": true,
  "provider": "local-whisper:base",
  "device": "cpu",
  "computeType": "int8"
}
```

**用途**：本地 Whisper ASR 语音转文字服务，作为 G2 麦克风采集的语音识别后端

---

### 4. 交易机器人 8081-8084

**进程**：Python（PID 196/916/1227/1438）

**标题**：`🦁 天䘵 V6.5 最终黄金优化版`

**状态**：4 个独立实例，分别监听 8081/8082/8083/8084

**8181-8184 反向代理**：Python 进程（PID 46509/46512/46515/46518）监听本地 8181-8184，将请求转发到 8081-8084

```
localhost:8181 -> localhost:8081
localhost:8182 -> localhost:8082
localhost:8183 -> localhost:8083
localhost:8184 -> localhost:8084
```

**API 测试**：`GET localhost:8181/health` → `{"port":8081,"status":"ok"}`

---

### 5. Clash Verge Meta（端口 7897）

**进程**：`verge-mih`（代理软件）

**监听地址**：`localhost:7897`

**用途**：科学上网代理

---

## 安全与架构问题

### P0 - 必须修复

1. **Vite 开发服务器暴露公网**
   - `g2-vision.tianlu2026.org` 运行 Vite dev mode（`src="/@vite/client"`）
   - Vite dev server 有代码热更新、文件系统读写等能力
   - **修复**：构建生产版本 `vite build`，用 `vite preview` 或 Nginx 服务静态文件

2. **后端无认证**
   - `/ask`、`/vision`、`/tts`、`/transcribe`、`/memory/search` 等接口均无认证
   - 任何人都可以调用这些接口
   - **修复**：添加 API Key 认证或 EvenHub SDK Token 验证

3. **CORS 完全开放**
   - `origin: true` 允许所有来源
   - **修复**：限制允许的 origin 列表

### P1 - 重要

4. **本地 Whisper ASR 无认证**
   - 端口 8791 只监听 `localhost`，相对安全
   - 但 API 无认证

5. **端口 33331（Clash）监听所有接口**
   - `*:33331` 暴露在外
   - **建议**：限制为 `localhost:33331`

6. **Vite dev server 监听 `0.0.0.0:5173`**
   - 同一局域网内任何设备都可以访问开发服务器
   - 如果 `.tools` 目录有 token 或密钥，热更新可能暴露
   - **建议**：开发完成后停止 dev server

### 信息

7. **EHPK 插件加载方式**
   - Even App 插件通过 EHPK 安装，加载的是本地打包文件，不依赖 g2-vision.tianlu2026.org
   - 但 Even App WebView 似乎也加载 `http://192.168.13.104:5173/`
   - 两种模式并存：EHPK 插件模式 + WebView 远程加载模式

---

## 文件位置

| 服务 | 文件路径 |
|------|---------|
| G2 Vision 前端 | `apps/evenhub-plugin/` (Vite dev) |
| API 后端 | `services/api-server/src/server.ts` |
| Local Whisper | `services/local-whisper-asr/server.py` |
| 交易机器人 | 未在源码目录（独立运行） |
| 反向代理 8181-8184 | 未在源码目录（可能是 trading 相关） |

---

## 下一步建议

1. **停止 Vite dev server**（开发完成后）：
   ```bash
   kill $(lsof -ti:5173)
   ```
   然后使用 `vite preview` 或 Nginx 托管生产构建

2. **为 API 后端添加认证**：
   - 在 `/ask`、`/vision` 等接口添加 `X-API-Key` 验证
   - 限制 CORS origin

3. **构建生产版本**：
   ```bash
   cd apps/evenhub-plugin && npm run build
   ```
   静态文件部署到 Nginx 而非 Vite dev server

4. **Clash 端口限制**：
   - 将 33331 改为 `localhost:33331`

5. **EHPK 更新**：
   - 新的 EHPK 已构建在 `apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
   - SHA256: `2dab644238737685fb2ae019a5ec990b6eb91d5983beba6d334586a1c21a700e`
   - 需要在 Even App 中重新安装以应用最新修复
