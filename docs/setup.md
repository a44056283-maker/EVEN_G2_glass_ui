# 安装与运行

## 1. 安装依赖

本项目需要 Node.js 22+。

当前这台电脑已在 EVEN G2 工程本地安装 Node.js：

```bash
export PATH="/Users/luxiangnan/Desktop/EVEN G2视觉和语音对讲系统/.tools/node-current/bin:$PATH"
node -v
npm -v
```

```bash
cd /Users/luxiangnan/Desktop/EVEN\ G2视觉和语音对讲系统/g2-vision-voice-assistant
npm install
```

## 2. 配置后端

```bash
cp .env.example .env
```

把 `.env` 里的 `MINIMAX_API_KEY` 改成你们自己的 MiniMax API key。

V0 阶段可以先用 `VISION_PROVIDER=stub` 跑通流程；接入真实视觉模型后再改为 `http-vlm` 并配置 `VISION_HTTP_ENDPOINT`。

注意：不要把 API key 写入前端、README、截图或公开仓库。

## 3. 启动后端

```bash
npm run dev:api
```

默认地址：`http://localhost:8787`

当前局域网地址：`http://192.168.13.104:8787`

## 4. 启动 Even Hub 插件前端

```bash
npm run dev:plugin
```

默认地址：`http://localhost:5173`

当前局域网地址：`http://192.168.13.104:5173`

公网调试地址：`https://g2-vision.tianlu2026.org`

前端默认使用同域 API 路径，例如 `/vision` 和 `/tts`。Vite dev server 会代理到本机后端 `http://127.0.0.1:8787`，所以 Cloudflare 只转发 5173 也可以正常调用后端。

## 5. 打包 .ehpk

```bash
npm run pack:g2
```

输出文件在 `apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`。

## 6. Even Terminal

开发者模式里的“主机设置”页面使用 Even Terminal。当前连接记录见：

```text
docs/even-terminal.md
```
