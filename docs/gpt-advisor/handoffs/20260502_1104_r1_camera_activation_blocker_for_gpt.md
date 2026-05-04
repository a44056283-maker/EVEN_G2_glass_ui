# R1 相机启动失败阻塞交接 - 请 GPT 审核根因与脚本方案

生成时间：2026-05-02 11:04
项目：天禄 G2 运维助手 / g2-vision-voice-assistant
路径：`/Users/luxiangnan/Desktop/EVEN G2视觉和语音对讲系统/g2-vision-voice-assistant`
当前插件版本：`0.2.2`
当前 EHPK：`apps/evenhub-plugin/g2-视觉-语音助手.ehpk`
当前 SHA256：`28d176bcff109b0151eb159ecd3600884807aa7ea6787deff439aca0e0bcee23`

## 1. 用户要求

用户要求非常明确：

```text
首页选择视觉识别
R1 单击确认进入视觉扫描
进入后自动调用手机相机
R1 单击拍照
R1 双击确认发送给 AI 识别
```

用户明确不接受：

```text
网页端出现“启用R1相机”按钮
眼镜端提示“请到网页启用相机”
R1 只能进菜单但不能直接进入相机拍照流程
```

## 2. 当前真实现象

已经确认：

1. 手机网页 UI 中点击“直接拍照 / 拍照识别”可以打开相机，可以上传图片，可以 AI 识别。
2. Even G2 眼镜中通过 R1 选择“视觉识别”后，代码会调用 `ensureCameraReady()`。
3. 但真机眼镜端显示“相机启动失败”。
4. 用户确认 Even App 相机权限已经开启。

因此当前断点不是 `/vision` 后端，也不是 MiniMax 识图；断点是：

```text
R1 / Even Hub input event 触发 navigator.mediaDevices.getUserMedia({ video }) 时失败
```

而手机网页按钮触发同样相机能力时可以成功。

## 3. 高概率根因判断

高概率是 iOS / Even App WebView 的 user activation 限制：

- 手机网页按钮点击是 DOM trusted user activation。
- R1 戒指事件来自 Even Hub SDK 的 `bridge.onEvenHubEvent`。
- 即使用户物理点击 R1，WebView/浏览器内核可能不把这个事件当成允许打开相机的 DOM 用户手势。
- 所以 `navigator.mediaDevices.getUserMedia({ video })` 在网页按钮内成功，在 R1 事件链内失败。

需要 GPT 审核这个判断是否成立，并查找 Even Hub SDK 是否提供原生相机 API 或允许 R1 input event 作为 user activation 的官方方式。

## 4. 当前相关代码

### 4.1 视觉入口

文件：`apps/evenhub-plugin/src/main.ts`

```ts
async function enterVisionPage(): Promise<void> {
  const bridge = getBridge()
  const renderer = createGlassRenderer(bridge)
  try {
    stopAutoVoiceDetection()
    await stopActiveGlassMicProbe?.()
    stopActiveGlassMicProbe = undefined
    voicePageState = 'idle'
    activeGlassPage = 'vision'
    visionState = 'preparing'
    pendingCapturedImage = undefined
    lastVisionError = ''
    setVoiceStatus('R1 已进入视觉识别，正在自动启动手机后置摄像头。')
    await renderer.show('vision_preparing')
    await ensureCameraReady()
    visionState = 'camera_ready'
    setVoiceStatus('相机已自动启动。R1 单击拍照，下滑返回首页。')
    await renderer.show('vision_ready')
    renderR1CameraDebug()
  } catch (error) {
    visionState = 'error'
    const message = error instanceof Error ? error.message : String(error)
    lastVisionError = message
    setVoiceStatus(`相机启动失败：${message}。R1 单击重试，下滑返回首页。`)
    await renderer.show('error', { body: `相机启动失败\n${message}\n\nR1 单击重试\n下滑返回首页` })
    renderR1CameraDebug()
  }
}
```

### 4.2 R1 视觉状态机

文件：`apps/evenhub-plugin/src/main.ts`

```ts
async function handleVisionR1Intent(intent: 'click' | 'double_click' | 'next' | 'previous'): Promise<void> {
  const bridge = getBridge()
  const renderer = createGlassRenderer(bridge)

  if (visionState === 'preparing' || visionState === 'uploading') return

  if (intent === 'previous') {
    if (visionState === 'captured') await captureVisionFrame(renderer, 'R1 上滑已重新拍照。单击或双击发送，下滑取消。')
    else if (visionState === 'camera_ready') await renderer.show('vision_ready')
    return
  }

  if (intent === 'next') {
    if (visionState === 'captured') {
      pendingCapturedImage = undefined
      lastCapturedAt = 0
      visionState = 'camera_ready'
      await renderer.show('vision_ready')
    } else if (visionState === 'camera_ready' || visionState === 'result' || visionState === 'error') {
      await returnFromVisionToHome()
    }
    return
  }

  if (intent === 'double_click') {
    if (visionState === 'captured' && pendingCapturedImage) {
      visionState = 'uploading'
      await renderer.show('vision_uploading')
      await runCaptureFlow(undefined, pendingCapturedImage)
      pendingCapturedImage = undefined
      visionState = 'result'
      return
    }

    if (visionState === 'result' || visionState === 'error' || visionState === 'camera_ready') {
      await returnFromVisionToHome()
      return
    }
    return
  }

  if (visionState === 'idle' || visionState === 'result' || visionState === 'error') {
    await enterVisionPage()
    return
  }

  if (visionState === 'captured' && pendingCapturedImage) {
    await renderer.show('vision_captured')
    return
  }

  if (visionState === 'camera_ready') {
    await captureVisionFrame(renderer, '已拍照。请 R1 双击发送；上滑重拍，下滑取消。')
    return
  }
}
```

### 4.3 相机启动

文件：`apps/evenhub-plugin/src/camera/cameraStream.ts`

```ts
export async function ensureCameraReady(): Promise<void> {
  if (cameraStream && video && isStreamLive(cameraStream)) return

  if (!window.isSecureContext || typeof navigator.mediaDevices?.getUserMedia !== 'function') {
    throw new Error('请在手机 Even App 中允许相机权限')
  }

  stopCamera()

  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: 'environment' },
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
      audio: false,
    })

    video = document.createElement('video')
    video.srcObject = cameraStream
    video.playsInline = true
    video.muted = true
    video.style.position = 'fixed'
    video.style.left = '-9999px'
    video.style.top = '-9999px'
    video.style.width = '1px'
    video.style.height = '1px'
    document.body.appendChild(video)

    await video.play()
    await waitForVideo(video)
  } catch (error) {
    stopCamera()
    throw new Error(error instanceof Error ? `请在手机 Even App 中允许相机权限：${error.message}` : '请在手机 Even App 中允许相机权限')
  }
}
```

### 4.4 截帧拍照

```ts
export async function captureFrameFromCameraStream(): Promise<StreamCapturedImage> {
  if (!video || !cameraStream || !isStreamLive(cameraStream)) throw new Error('相机尚未准备好')
  await waitForVideo(video)

  const sourceWidth = video.videoWidth || 1280
  const sourceHeight = video.videoHeight || 720
  const { width, height } = fitSize(sourceWidth, sourceHeight)
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height

  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('无法创建截图画布')

  ctx.drawImage(video, 0, 0, width, height)
  const dataUrl = canvas.toDataURL('image/jpeg', 0.72)

  return {
    imageBase64: dataUrl.split(',')[1] ?? '',
    mimeType: 'image/jpeg',
    dataUrl,
    width,
    height,
  }
}
```

## 5. 已删除的错误路径

当前已经删除这些错误产品路径：

```text
启用R1相机
启用 R1 相机
相机已启用
vision-enable-camera
needs_phone_activation
vision_needs_phone_activation
prepareR1CameraFromPhoneAction
```

`rg` 搜索无结果。

## 6. 需要 GPT 审核的问题

请 GPT 判断以下问题：

### 问题 A：R1 事件是否可能打开手机相机？

请确认 Even Hub SDK 的 `bridge.onEvenHubEvent` 回调内调用 `navigator.mediaDevices.getUserMedia({ video })` 是否会被 iOS WebView 认为是非用户手势，从而失败。

如果失败是平台限制，请不要再建议“继续在 R1 事件里直接 getUserMedia”。

### 问题 B：Even Hub SDK 是否有原生手机相机 API？

请查 Even Hub SDK 是否有类似：

```ts
bridge.camera
bridge.openCamera
bridge.takePhoto
bridge.requestPermission
bridge.phoneCamera
```

如果存在，请给出准确调用方式。

### 问题 C：是否可以在插件启动时预热相机？

方案：插件加载后，在手机 WebView 第一次 DOM 触摸/点击时预热相机流，并持续保持隐藏 video stream。之后 R1 只做 canvas 截帧。

但用户希望“眼镜内 R1 直接触发”，不想手机点启用按钮。请判断是否有无需手机触摸的一次性相机预热方案。

### 问题 D：能否用 Even App 权限绕过 DOM user activation？

`app.json` 已声明：

```json
{ "name": "camera", "desc": "Use the phone camera to capture images for visual assistance." }
```

请确认这个权限是否只是允许 WebView 请求相机，而不是免除 iOS user activation。

## 7. 如果平台限制成立，建议可接受方案

如果 GPT 判断 R1 无法直接启动 `getUserMedia`，请给出一个用户体验上最接近需求的方案，而不是继续错修。

候选方案：

### 方案 1：插件打开后自动显示手机端一次性授权遮罩

手机网页只显示一个很大的按钮：

```text
启动天禄相机
```

用户首次打开插件时点一次。点完后：

- getUserMedia 启动
- 隐藏 video 常驻
- 眼镜端进入首页
- 之后 R1 可完全控制拍照、重拍、发送

缺点：不是纯 R1 首次启动。

优点：符合 iOS user activation；后续 R1 体验满足用户要求。

### 方案 2：进入视觉识别时手机端自动弹出全屏授权页，眼镜显示“请点手机一次授权”

用户不喜欢，作为备选。

### 方案 3：如果 Even SDK 有原生拍照 API，直接替换 getUserMedia

这是最理想方案。请 GPT 优先确认。

## 8. 希望 GPT 给 Codex 的准确补丁方向

请 GPT 输出一份可直接给 Codex 执行的补丁提示词，包含：

1. 是否继续使用 `getUserMedia`。
2. 是否必须引入“一次性手机端授权/预热”。
3. 如果 Even SDK 有相机 API，准确文件和函数怎么改。
4. 如果没有 SDK 相机 API，如何让 R1 后续只控制 canvas 截帧。
5. 不要恢复“启用R1相机”这个低级按钮文案。
6. 眼镜端视觉页仍保持：R1 单击拍照，双击发送，上滑重拍，下滑取消。

## 9. 当前验收目标

最终必须达到：

```text
打开插件后完成必要相机授权/预热
眼镜首页 R1 选择视觉识别
R1 单击进入视觉页
相机流已经 ready
R1 单击立即截帧拍照
R1 双击发送 AI 识别
G2 显示识别结果
手机网页也显示识别结果
```

如果纯 R1 首次启动相机在 iOS/Even WebView 内不可能，请 GPT 明确说“不可能”，并给出最少一次手机端授权的产品方案。
