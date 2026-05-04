export interface CapturedImage {
  imageBase64: string
  mimeType: 'image/jpeg'
}

const MAX_IMAGE_EDGE = 1280
const JPEG_QUALITY = 0.72
const PREPARED_CAMERA_TTL_MS = 75_000

let preparedStream: MediaStream | undefined
let preparedAt = 0
let preparedStopTimer: number | undefined
let fileInputRequestActive = false

export function isFileInputRequestActive(): boolean {
  return fileInputRequestActive
}

export async function capturePhoto(): Promise<CapturedImage> {
  if (shouldUseFileCapture()) {
    return captureCameraPhoto()
  }

  const prepared = await capturePreparedPhoto()
  if (prepared) return prepared

  if (window.isSecureContext && typeof navigator.mediaDevices?.getUserMedia === 'function') {
    try {
      return await captureWithMediaDevices()
    } catch (error) {
      console.warn('getUserMedia failed; falling back to file input.', error)
    }
  }

  return captureCameraPhoto()
}

export function captureCameraPhoto(): Promise<CapturedImage> {
  return captureWithFileInput('file-fallback', '未拍照或相机权限被浏览器拦截')
}

export function selectPhotoFromAlbum(): Promise<CapturedImage> {
  return captureWithFileInput('album-fallback', '未选择相册照片')
}

export async function prepareCameraSession(): Promise<boolean> {
  if (!window.isSecureContext || typeof navigator.mediaDevices?.getUserMedia !== 'function') return false
  if (preparedStream && isStreamActive(preparedStream)) return true

  const video = document.querySelector<HTMLVideoElement>('#camera-preview')
  if (!video) return false

  try {
    stopPreparedCamera()
    preparedStream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: 'environment' },
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
      audio: false,
    })
    preparedAt = Date.now()
    video.srcObject = preparedStream
    await video.play()
    await waitForVideo(video)
    window.clearTimeout(preparedStopTimer)
    preparedStopTimer = window.setTimeout(stopPreparedCamera, PREPARED_CAMERA_TTL_MS)
    return true
  } catch (error) {
    console.warn('prepareCameraSession failed.', error)
    stopPreparedCamera()
    return false
  }
}

export async function capturePreparedPhoto(): Promise<CapturedImage | undefined> {
  const video = document.querySelector<HTMLVideoElement>('#camera-preview')
  const canvas = document.querySelector<HTMLCanvasElement>('#capture-canvas')
  if (!video || !canvas || !preparedStream || !isStreamActive(preparedStream)) return undefined
  if (Date.now() - preparedAt > PREPARED_CAMERA_TTL_MS) {
    stopPreparedCamera()
    return undefined
  }

  await waitForVideo(video)
  const size = fitSize(video.videoWidth || 1280, video.videoHeight || 720)
  canvas.width = size.width
  canvas.height = size.height
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Canvas 2D context unavailable')
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
  const image = canvasToCapturedImage(canvas)
  stopPreparedCamera()
  return image
}

export function stopPreparedCamera(): void {
  window.clearTimeout(preparedStopTimer)
  preparedStopTimer = undefined
  if (preparedStream) {
    for (const track of preparedStream.getTracks()) track.stop()
  }
  preparedStream = undefined
  preparedAt = 0
  const video = document.querySelector<HTMLVideoElement>('#camera-preview')
  if (video) video.srcObject = null
}

function shouldUseFileCapture(): boolean {
  const ua = navigator.userAgent
  const isIos = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  const isEmbeddedBrowser = /MicroMessenger|FBAN|FBAV|Line|Even/i.test(ua)
  return isIos || isEmbeddedBrowser
}

function isStreamActive(stream: MediaStream): boolean {
  return stream.getVideoTracks().some((track) => track.readyState === 'live')
}

async function captureWithMediaDevices(): Promise<CapturedImage> {
  const video = document.querySelector<HTMLVideoElement>('#camera-preview')
  const canvas = document.querySelector<HTMLCanvasElement>('#capture-canvas')
  if (!video || !canvas) throw new Error('Missing camera DOM nodes')

  const stream = await navigator.mediaDevices.getUserMedia({
    video: {
      facingMode: { ideal: 'environment' },
      width: { ideal: 1280 },
      height: { ideal: 720 },
    },
    audio: false,
  })

  try {
    video.srcObject = stream
    await video.play()
    await waitForVideo(video)

    const size = fitSize(video.videoWidth || 1280, video.videoHeight || 720)
    canvas.width = size.width
    canvas.height = size.height
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Canvas 2D context unavailable')
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

    return canvasToCapturedImage(canvas)
  } finally {
    for (const track of stream.getTracks()) track.stop()
    video.srcObject = null
  }
}

function waitForVideo(video: HTMLVideoElement): Promise<void> {
  if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && video.videoWidth > 0) {
    return Promise.resolve()
  }

  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(() => reject(new Error('Camera preview timeout')), 6000)
    video.onloadeddata = () => {
      window.clearTimeout(timeout)
      resolve()
    }
  })
}

function captureWithFileInput(inputId: string, emptyMessage: string): Promise<CapturedImage> {
  const input = document.querySelector<HTMLInputElement>(`#${inputId}`)
  if (!input) throw new Error(`Missing file fallback input: ${inputId}`)
  input.value = ''
  fileInputRequestActive = true

  return new Promise((resolve, reject) => {
    input.onchange = () => {
      const file = input.files?.[0]
      if (!file) {
        fileInputRequestActive = false
        reject(new Error(emptyMessage))
        return
      }

      imageFileToCapturedImage(file).then(resolve, reject).finally(() => {
        fileInputRequestActive = false
      })
    }
    input.click()
  })
}

export function imageFileToCapturedImage(file: File): Promise<CapturedImage> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = async () => {
      try {
        resolve(await compressDataUrl(String(reader.result)))
      } catch (error) {
        reject(error instanceof Error ? error : new Error(String(error)))
      }
    }
    reader.onerror = () => reject(reader.error ?? new Error('读取照片失败'))
    reader.readAsDataURL(file)
  })
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

async function compressDataUrl(dataUrl: string): Promise<CapturedImage> {
  const image = await loadImage(dataUrl)
  const canvas = document.querySelector<HTMLCanvasElement>('#capture-canvas')
  if (!canvas) throw new Error('Missing capture canvas')

  const size = fitSize(image.naturalWidth || image.width, image.naturalHeight || image.height)
  canvas.width = size.width
  canvas.height = size.height

  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Canvas 2D context unavailable')
  ctx.drawImage(image, 0, 0, size.width, size.height)

  return canvasToCapturedImage(canvas)
}

function loadImage(dataUrl: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error('照片压缩失败，请换一张 JPEG 照片重试'))
    image.src = dataUrl
  })
}

function canvasToCapturedImage(canvas: HTMLCanvasElement): CapturedImage {
  return {
    imageBase64: canvas.toDataURL('image/jpeg', JPEG_QUALITY).split(',')[1] ?? '',
    mimeType: 'image/jpeg',
  }
}
