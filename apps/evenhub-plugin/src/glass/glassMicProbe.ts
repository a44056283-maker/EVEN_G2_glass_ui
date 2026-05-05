import type { EvenAppBridge, EvenHubEvent } from '@evenrealities/even_hub_sdk'
import { getG2BridgeWsUrl } from '../api/g2BridgeApi'
import { GlassRenderer } from './GlassRenderer'

export interface GlassMicProbeOptions {
  bridge: EvenAppBridge
  renderer: GlassRenderer
  mode?: 'probe' | 'asr' | 'mock-asr'
  onStatus?: (text: string) => void
  onTranscript?: (text: string) => void
  onAnswer?: (text: string) => void
  onDebug?: (state: GlassMicProbeDebugState) => void
}

export interface GlassMicProbeDebugState {
  voicePageState: 'probe'
  micSource: 'g2'
  wsStatus: 'connecting' | 'open' | 'error' | 'closed'
  audioControlCalled: boolean
  audioControlError: string
  totalBytes: number
  chunks: number
  lastChunkBytes: number
  lastChunkAt: string
  noPcmTimeout: boolean
  lastServerAudioDebug: string
  lastVoiceError: string
}

export async function startGlassMicProbe(options: GlassMicProbeOptions): Promise<() => Promise<void>> {
  const { bridge, renderer } = options
  let totalBytes = 0
  let chunks = 0
  let lastChunkBytes = 0
  let backendBytes = 0
  let wsStatus: GlassMicProbeDebugState['wsStatus'] = 'connecting'
  let audioControlCalled = false
  let audioControlError = ''
  let noPcmTimeout = false
  let lastServerAudioDebug = ''
  let lastVoiceError = ''
  let closed = false
  let firstChunkAt: number | undefined
  let lastChunkAt: number | undefined
  let unsubscribe: (() => void) | undefined
  let timer: number | undefined
  const mode = options.mode ?? 'probe'

  await safeShow(renderer, 'voice_mic_probe', {
    pcmBytes: totalBytes,
    chunks,
    lastChunkBytes,
    backendBytes,
  })

  const ws = new WebSocket(`${getG2BridgeWsUrl().replace(/\/+$/, '')}/audio?mode=${encodeURIComponent(mode)}&source=g2`)
  ws.binaryType = 'arraybuffer'
  console.log('[G2 MicProbe] connecting audio websocket', ws.url)

  const publishDebug = () => {
    options.onDebug?.({
      voicePageState: 'probe',
      micSource: 'g2',
      wsStatus,
      audioControlCalled,
      audioControlError,
      totalBytes,
      chunks,
      lastChunkBytes,
      lastChunkAt: lastChunkAt ? new Date(lastChunkAt).toLocaleTimeString() : '--',
      noPcmTimeout,
      lastServerAudioDebug,
      lastVoiceError,
    })
  }

  const update = () => {
    const content = renderer.render('voice_mic_probe', {
      pcmBytes: totalBytes,
      chunks,
      lastChunkBytes,
      backendBytes,
    })
    void renderer.updateMainText(content).catch((error) => {
      console.warn('[G2 MicProbe] text update failed', error)
    })
    publishDebug()
  }

  const wsReady = new Promise<void>((resolve, reject) => {
    ws.onopen = () => {
      wsStatus = 'open'
      console.log('[G2 MicProbe] audio websocket open')
      publishDebug()
      resolve()
    }
    ws.onerror = () => {
      wsStatus = 'error'
      lastVoiceError = '语音 WebSocket 连接失败'
      publishDebug()
      reject(new Error('语音 WebSocket 连接失败'))
    }
  })

  ws.onclose = () => {
    wsStatus = 'closed'
    publishDebug()
  }

  ws.onmessage = (message) => {
    try {
      const data = JSON.parse(String(message.data)) as {
        type?: string
        text?: string
        totalBytes?: number
        chunks?: number
        lastChunkBytes?: number
      }
      if (data.type === 'audio_debug') {
        backendBytes = data.totalBytes ?? backendBytes
        lastServerAudioDebug = `bytes=${data.totalBytes ?? 0} chunks=${data.chunks ?? 0} last=${data.lastChunkBytes ?? 0}`
        options.onStatus?.(`后端收到 PCM：${backendBytes} bytes`)
        update()
      }
      if (data.type === 'final_transcript' && data.text) {
        options.onTranscript?.(data.text)
        void safeShow(renderer, 'voice_transcript', { body: data.text })
      }
      if (data.type === 'answer' && data.text) {
        options.onAnswer?.(data.text)
        void safeShow(renderer, 'reply', { title: '天禄回复', body: data.text })
      }
      if (data.type === 'error' && data.text) {
        lastVoiceError = data.text
        options.onStatus?.(data.text)
        void safeShow(renderer, 'error', { title: '语音错误', body: data.text })
        publishDebug()
      }
    } catch {}
  }

  unsubscribe = bridge.onEvenHubEvent((event: EvenHubEvent) => {
    const pcm = event.audioEvent?.audioPcm
    if (!pcm || closed) return
    const bytes = toUint8Array(pcm)
    firstChunkAt ??= Date.now()
    lastChunkAt = Date.now()
    totalBytes += bytes.byteLength
    chunks += 1
    lastChunkBytes = bytes.byteLength
    console.log('[G2 MicProbe] pcm chunk', { totalBytes, chunks, lastChunkBytes, firstChunkAt, lastChunkAt })
    if (ws.readyState === WebSocket.OPEN) ws.send(bytes)
  })

  await wsReady
  console.log('[G2 MicProbe] audioControl start')
  audioControlCalled = true
  publishDebug()
  try {
    await bridge.audioControl(true)
    options.onStatus?.('G2 MicProbe 已开启：请对着眼镜说话。')
  } catch (error) {
    audioControlError = error instanceof Error ? error.message : String(error)
    lastVoiceError = audioControlError
    await safeShow(renderer, 'error', { title: 'G2 麦克风启动失败', body: audioControlError })
    options.onStatus?.(`G2 麦克风启动失败：${audioControlError}`)
    publishDebug()
    throw error
  }

  timer = window.setInterval(update, 500)
  window.setTimeout(() => {
    if (!closed && totalBytes === 0) {
      noPcmTimeout = true
      void safeShow(renderer, 'voice_no_pcm', { reason: '5 秒内 totalBytes 仍为 0' })
      options.onStatus?.('5 秒内没有收到 G2 PCM。')
      publishDebug()
    }
  }, 5000)

  return async () => {
    closed = true
    if (timer) window.clearInterval(timer)
    unsubscribe?.()
    try {
      console.log('[G2 MicProbe] audioControl stop', { totalBytes, chunks, lastChunkBytes, firstChunkAt, lastChunkAt })
      await bridge.audioControl(false)
    } catch {}
    ws.close()
  }
}

async function safeShow(
  renderer: GlassRenderer,
  screen: Parameters<GlassRenderer['show']>[0],
  state?: Parameters<GlassRenderer['show']>[1],
): Promise<void> {
  try {
    await renderer.show(screen, state)
  } catch (error) {
    console.warn('[G2 MicProbe] glass show failed', error)
  }
}

function toUint8Array(pcm: unknown): Uint8Array {
  if (pcm instanceof Uint8Array) return pcm
  if (pcm instanceof ArrayBuffer) return new Uint8Array(pcm)
  if (Array.isArray(pcm)) return new Uint8Array(pcm)
  if (ArrayBuffer.isView(pcm)) {
    return new Uint8Array(pcm.buffer, pcm.byteOffset, pcm.byteLength)
  }
  return new Uint8Array(pcm as ArrayLike<number>)
}
