# Even G2 接入说明

## 当前定位

G2 本体负责显示、触控、后续麦克风输入；手机 Even App 的 WebView 负责运行插件逻辑。V0 不假设 G2 本体有摄像头或扬声器。

## V0 交互

- G2 显示：`点击开始识别`
- 点击：调用手机摄像头拍照
- 后端返回：短中文结果
- G2 显示：最多几行重点信息
- 手机/蓝牙耳机：播放 TTS 或浏览器朗读 fallback

## 显示规格

当前按 576x288 文本容器设计，内容会控制在短文本范围内，避免小屏幕溢出。

## 权限

`app.json` 已声明：

- `camera`
- `album`
- `g2-microphone`
- `phone-microphone`
- `network.whitelist`

实际上架或真机 sideload 时，需要再以 Even Hub 当前文档校验权限名和网络白名单格式。
