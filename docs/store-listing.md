# G2 Vision AI 商店发布资料

更新日期：2026-05-01

## Basic Info

App name:

```text
G2 Vision AI
```

Subtitle / Chinese name:

```text
g2-视觉-语音助手
```

Plugin ID:

```text
com.luxiangnan.g2visionvoice
```

Category:

```text
Productivity / Utilities / Accessibility
```

Language:

```text
Chinese, English, Japanese
```

## Short Description

```text
使用手机摄像头、G2 显示和 MiniMax AI，为 Even G2 提供拍照识别、语音朗读、问答和个人记忆检索能力。
```

## Full Description

```text
G2 Vision AI 是为 Even G2 智能眼镜制作的视觉与语音助手。

它使用手机摄像头采集画面，通过 MiniMax AI 进行图片理解和简短问答，并把结果显示到 G2 镜片上，同时可通过手机扬声器或蓝牙耳机朗读回答。

当前版本支持：

1. 点击拍照识别
2. 图片自动压缩与上传
3. AI 视觉描述与短回答
4. G2 小屏幕结果显示
5. 手机或蓝牙耳机语音朗读
6. 呼叫“天禄”进行语音/文字问答
7. 本地历史记录查看
8. 只读检索用户授权同步的天禄记忆库

注意：
G2 眼镜本体没有摄像头和扬声器，因此视觉采集由手机摄像头完成，声音由手机或蓝牙耳机播放。G2 麦克风采集能力已接入测试流程，语音转文字能力会持续增强。
```

## Permissions

Camera:

```text
用于调用手机摄像头拍摄照片，提供视觉识别输入。照片仅在用户点击识别或确认打开摄像头后采集。
```

Album:

```text
当摄像头不可用时，允许用户从相册选择图片作为识别输入。
```

G2-microphone:

```text
用于在插件环境中采集 G2 眼镜麦克风音频，以实现 push-to-talk 语音问答。当前仅在用户点击“呼叫天禄”后短时录音。
```

Phone-microphone:

```text
用于在浏览器或 Even App WebView 中作为语音识别备用输入。仅在用户主动点击语音按钮后请求权限。
```

Network:

```text
用于连接后端服务、MiniMax AI 接口、视觉识别接口、语音合成接口和用户授权的只读记忆检索服务。
```

## Privacy Agreement

```text
G2 Vision AI 尊重用户隐私。本应用只在用户主动点击识别、选择图片、确认打开摄像头或点击语音按钮后采集相关数据。

本应用可能处理以下数据：

1. 用户拍摄或选择的图片
2. 用户主动输入或说出的语音/文字问题
3. AI 返回的识别结果和问答结果
4. 本地历史记录
5. 用户授权同步到本机的只读记忆库内容

图片、语音和文字会发送到开发者配置的后端服务，并可能调用 MiniMax 等 AI 服务进行识别、问答和语音合成。本应用不会在前端代码中暴露 API Key。

历史记录默认保存在用户设备的本地浏览器存储中，用户可以在应用内清空。

只读记忆检索仅用于回答用户问题，不用于自动交易、下单、改仓、平仓或其他高风险自动操作。

本应用不会主动采集后台摄像头、后台麦克风或持续定位信息。
```

## Terms And Conditions

```text
使用 G2 Vision AI 即表示用户理解并同意：

1. 本应用提供 AI 辅助识别和问答，结果可能存在误差，仅供参考。
2. 本应用不应替代专业医疗、法律、金融、交通安全或工程安全判断。
3. 涉及交易系统、策略、仓位或风险判断时，本应用仅提供只读分析和提示，不执行自动交易行为。
4. 用户应自行确认拍摄、上传或识别内容不侵犯他人隐私或法律权益。
5. 因网络、第三方 AI 服务、设备权限或 Even App WebView 限制，部分功能可能出现延迟、失败或降级。
6. 开发者会持续改进功能，但不保证 AI 输出完全准确或适用于所有场景。
```

## Review Notes

```text
This app is an Even G2 visual and voice assistant.

The G2 glasses are used for display, touch input, and microphone input. The phone camera is used for image capture because G2 does not have a built-in camera. Audio output is played through the phone speaker or Bluetooth earphones.

The app requires camera, album, G2 microphone, phone microphone, and network access. All capture actions are user-triggered.

Trading-related memory lookup is read-only. The app does not place orders, close positions, or modify trading accounts.
```

## Screenshots To Upload

建议上传 4 张：

1. 首页待命状态：显示“点击开始识别”和“呼叫天禄”
2. 识别过程状态：显示拍照采集、压缩图片、上传后端、AI 识别、语音朗读
3. 识别结果状态：显示 AI 返回的画面描述
4. 语音对话和历史记录：显示“语音对话”和“历史记录”模块

## App Icon Concept

建议图标：

```text
深色圆角背景，中间为简化 G2 眼镜轮廓，叠加蓝绿色视觉光点，右下角加入小型 AI 星点。
```
