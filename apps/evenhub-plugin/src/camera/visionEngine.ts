import {
  captureFrameFromCameraStream,
  ensureCameraReady,
  getCameraStreamStatus,
  stopCamera,
  type StreamCapturedImage,
} from './cameraStream'

export type VisionEngineStatus = 'idle' | 'starting' | 'ready' | 'failed' | 'stream_lost'

export interface VisionEngineState {
  status: VisionEngineStatus
  error?: string
  startedAt?: string
  videoWidth: number
  videoHeight: number
}

let status: VisionEngineStatus = 'idle'
let lastError = ''
let startedAt = ''

export function getVisionEngineState(): VisionEngineState {
  const camera = getCameraStreamStatus()
  if (status === 'ready' && !camera.ready) status = camera.active ? 'stream_lost' : 'idle'
  return {
    status,
    error: lastError || undefined,
    startedAt: startedAt || undefined,
    videoWidth: camera.videoWidth,
    videoHeight: camera.videoHeight,
  }
}

export function isVisionEngineReady(): boolean {
  return getVisionEngineState().status === 'ready' && getCameraStreamStatus().ready
}

export async function startVisionEngineFromPhoneGesture(): Promise<VisionEngineState> {
  status = 'starting'
  lastError = ''
  try {
    await ensureCameraReady()
    const camera = getCameraStreamStatus()
    status = camera.ready ? 'ready' : 'stream_lost'
    startedAt = new Date().toLocaleTimeString('zh-CN')
    if (!camera.ready) {
      lastError = '视频流已启动但画面尚未就绪'
      throw new Error(lastError)
    }
    return getVisionEngineState()
  } catch (error) {
    status = 'failed'
    lastError = error instanceof Error ? error.message : String(error)
    throw error
  }
}

export async function captureFrameFromVisionEngine(): Promise<StreamCapturedImage> {
  if (!isVisionEngineReady()) {
    throw new Error('相机未就绪，请先进入视觉识别打开手机拍照。')
  }
  return captureFrameFromCameraStream()
}

export function stopVisionEngine(): void {
  stopCamera()
  status = 'idle'
  lastError = ''
  startedAt = ''
}
