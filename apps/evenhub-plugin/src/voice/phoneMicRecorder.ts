export interface PhoneMicRecording {
  audioBase64: string
  mimeType: string
  format: string
  sampleRate?: number
  channels?: number
  durationMs: number
  sizeBytes: number
  inputLabel: string
}

export interface ActivePhoneMicRecorder {
  stop(): Promise<PhoneMicRecording>
  cancel(): void
}

export async function startPhoneMicRecorder(): Promise<ActivePhoneMicRecorder> {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('当前容器不支持手机/耳机麦克风采集。')
  }

  if (typeof MediaRecorder === 'undefined') {
    throw new Error('当前容器不支持 MediaRecorder 录音。')
  }

  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
    video: false,
  })

  const inputLabel = stream.getAudioTracks()[0]?.label || '手机/耳机麦克风'
  const mimeType = chooseMimeType()
  const chunks: BlobPart[] = []
  const startedAt = performance.now()
  const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream)

  recorder.addEventListener('dataavailable', (event) => {
    if (event.data.size > 0) chunks.push(event.data)
  })

  recorder.start(250)

  let stopped = false

  return {
    async stop() {
      if (stopped) throw new Error('录音已经结束。')
      stopped = true
      const blob = await stopRecorder(recorder, chunks, stream)
      const buffer = await blob.arrayBuffer()
      return {
        audioBase64: arrayBufferToBase64(buffer),
        mimeType: blob.type || mimeType || 'audio/webm',
        format: blob.type || mimeType || 'audio/webm',
        durationMs: Math.round(performance.now() - startedAt),
        sizeBytes: blob.size,
        inputLabel,
      }
    },
    cancel() {
      stopped = true
      try {
        if (recorder.state !== 'inactive') recorder.stop()
      } catch {}
      stopStream(stream)
    },
  }
}

function chooseMimeType(): string {
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/mp4',
    'audio/aac',
  ]

  for (const candidate of candidates) {
    if (MediaRecorder.isTypeSupported(candidate)) return candidate
  }

  return ''
}

function stopRecorder(recorder: MediaRecorder, chunks: BlobPart[], stream: MediaStream): Promise<Blob> {
  return new Promise((resolve, reject) => {
    const finish = () => {
      stopStream(stream)
      resolve(new Blob(chunks, { type: recorder.mimeType || 'audio/webm' }))
    }

    recorder.addEventListener('stop', finish, { once: true })
    recorder.addEventListener(
      'error',
      (event) => {
        stopStream(stream)
        reject(new Error(event.error?.message || '录音失败。'))
      },
      { once: true },
    )

    try {
      if (recorder.state === 'inactive') finish()
      else {
        try {
          recorder.requestData()
        } catch {}
        recorder.stop()
      }
    } catch (error) {
      stopStream(stream)
      reject(error)
    }
  })
}

function stopStream(stream: MediaStream): void {
  for (const track of stream.getTracks()) track.stop()
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  const chunkSize = 0x8000
  let binary = ''
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize))
  }
  return btoa(binary)
}
