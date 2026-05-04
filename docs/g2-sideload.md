# G2 真机加载方式

## 关键结论

G2 不是直接安装网页。Even Hub 插件逻辑运行在手机 Even App WebView 里，插件通过 Even Hub SDK 把内容发到眼镜显示。

所以测试方式有两种：

## 方式 A：开发调试二维码

电脑端保持服务运行：

```bash
npm run dev:api
npm run dev:plugin
```

在 Even Realities App 中进入 Even Hub / Plugins，选择 Scan QR，扫描下面这个地址生成的二维码：

```text
https://g2-vision.tianlu2026.org
```

当前 CLI 生成二维码命令：

```bash
npx evenhub qr --url https://g2-vision.tianlu2026.org
```

加载成功后，点击 G2 或手机页面按钮，镜片应显示：

- 正在识别
- 识别结果
- 识别失败

## 方式 B：上传 .ehpk 到 Even Hub

最新安装包：

```text
apps/evenhub-plugin/g2-vision-voice-assistant.ehpk
```

上传地址：

```text
https://hub.evenrealities.com/hub
```

上传后在手机 Even App 内安装/打开该插件。

## 声音说明

G2 本体没有扬声器。朗读声音会从手机扬声器或已连接的蓝牙耳机输出。
