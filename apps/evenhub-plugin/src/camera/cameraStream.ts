export interface StreamCapturedImage {
  imageBase64: string
  mimeType: 'image/jpeg'
  dataUrl: string
  width: number
  height: number
}

export interface CameraStreamStatus {
  active: boolean
  hasVideoElement: boolean
  videoWidth: number
  videoHeight: number
  ready: boolean
}

const MAX_IMAGE_EDGE = 1280

let cameraStream: MediaStream | null = null
let video: HTMLVideoElement | null = null

export async function ensureCameraReady(): Promise<void> {
  if (cameraStream && video && isStreamLive(cameraStream)) return

  if (!window.isSecureContext || typeof navigator.mediaDevices?.getUserMedia !== 'function') {
    throw new Error(
      window.isSecureContext
        ? '当前 WebView 不支持 mediaDevices.getUserMedia，无法打开手机相机'
        : '当前页面不是安全上下文，无法打开手机相机',
    )
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
    const detail = error instanceof Error ? `${error.name}: ${error.message}` : String(error)
    throw new Error(`相机启动失败：${detail}`)
  }
}

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

function fitSize(width: number, height: number): { width: number; height: number } {
  const longest = Math.max(width, height)
  if (longest <= MAX_IMAGE_EDGE) return { width, height }
  const ratio = MAX_IMAGE_EDGE / longest
  return {
    width: Math.round(width * ratio),
    height: Math.round(height * ratio),
  }
}

export function getCameraStreamStatus(): CameraStreamStatus {
  const active = Boolean(cameraStream && isStreamLive(cameraStream))
  const videoWidth = video?.videoWidth ?? 0
  const videoHeight = video?.videoHeight ?? 0
  return {
    active,
    hasVideoElement: Boolean(video),
    videoWidth,
    videoHeight,
    ready: active && Boolean(video) && videoWidth > 0 && videoHeight > 0,
  }
}

export function stopCamera(): void {
  if (cameraStream) {
    for (const track of cameraStream.getTracks()) track.stop()
  }
  cameraStream = null
  if (video) {
    video.srcObject = null
    video.remove()
  }
  video = null
}

function isStreamLive(stream: MediaStream): boolean {
  return stream.getVideoTracks().some((track) => track.readyState === 'live')
}

function waitForVideo(target: HTMLVideoElement): Promise<void> {
  if (target.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && target.videoWidth > 0) {
    return Promise.resolve()
  }

  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(() => reject(new Error('Camera preview timeout')), 6000)
    target.onloadeddata = () => {
      window.clearTimeout(timeout)
      resolve()
    }
  })
}
