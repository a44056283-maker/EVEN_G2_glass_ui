import type { EvenAppBridge, EvenHubEvent } from '@evenrealities/even_hub_sdk'
import { getG2BridgeWsUrl } from '../api/g2BridgeApi'

export type VoiceSessionMode = 'probe' | 'mock-asr' | 'asr'
export type StopReason = 'released' | 'clicked_stop' | 'max_duration' | 'cancelled' | 'no_pcm' | 'error'

export interface G2PcmVoiceDebugState {
  voiceState: 'starting' | 'recording' | 'finalizing' | 'transcribing' | 'answer' | 'error' | 'no_pcm' | 'cancelled'
  strategy: 'g2-pcm'
  mode: VoiceSessionMode
  isHolding: boolean
  holdStartedAt: string
  elapsedMs: number
  maxDurationMs: number
  remainingMs: number
  stopReason: string
  wsStatus: 'idle' | 'connecting' | 'open' | 'error' | 'closed'
  audioControlCalled: boolean
  audioControlError: string
  totalBytes: number
  chunks: number
  lastChunkBytes: number
  lastChunkAt: string
  lastServerAudioDebug: string
  lastTranscript: string
  lastVoiceError: string
}

export interface G2PcmVoiceSessionOptions {
  bridge: EvenAppBridge
  mode: VoiceSessionMode
  maxDurationMs: number
  mockText?: string
  onDebug?: (debug: G2PcmVoiceDebugState) => void
  onStatus?: (text: string) => void
  onTranscript?: (text: string, meta?: { provider?: string; durationMs?: number; totalBytes?: number; mode?: string }) => void
  onError?: (error: Error) => void
  onMaxDuration?: () => void
}

export interface ActiveG2PcmVoiceSession {
  stop(reason: StopReason): Promise<void>
}

export async function startG2PcmVoiceSession(options: G2PcmVoiceSessionOptions): Promise<ActiveG2PcmVoiceSession> {
  const startedAt = Date.now()
  const mode = options.mode
  let wsStatus: G2PcmVoiceDebugState['wsStatus'] = 'connecting'
  let voiceState: G2PcmVoiceDebugState['voiceState'] = 'starting'
  let audioControlCalled = false
  let audioControlError = ''
  let totalBytes = 0
  let chunks = 0
  let lastChunkBytes = 0
  let lastChunkAt = ''
  let lastServerAudioDebug = ''
  let lastTranscript = ''
  let lastVoiceError = ''
  let stopReason = ''
  let stopped = false
  let finalTranscriptReceived = false
  let unsubscribe: (() => void) | undefined
  let tickTimer: number | undefined
  let maxTimer: number | undefined
  let noPcmTimer: number | undefined
  let closeTimer: number | undefined

  const params = new URLSearchParams({
    mode,
    source: 'g2',
  })
  if (options.mockText) params.set('mockText', options.mockText)

  const ws = new WebSocket(`${getG2BridgeWsUrl().replace(/\/+$/, '')}/audio?${params.toString()}`)
  ws.binaryType = 'arraybuffer'

  const publishDebug = () => {
    const elapsedMs = Date.now() - startedAt
    options.onDebug?.({
      voiceState,
      strategy: 'g2-pcm',
      mode,
      isHolding: !stopped,
      holdStartedAt: new Date(startedAt).toLocaleTimeString(),
      elapsedMs,
      maxDurationMs: options.maxDurationMs,
      remainingMs: Math.max(0, options.maxDurationMs - elapsedMs),
      stopReason,
      wsStatus,
      audioControlCalled,
      audioControlError,
      totalBytes,
      chunks,
      lastChunkBytes,
      lastChunkAt,
      lastServerAudioDebug,
      lastTranscript,
      lastVoiceError,
    })
  }

  const fail = (error: Error) => {
    voiceState = totalBytes === 0 ? 'no_pcm' : 'error'
    lastVoiceError = error.message
    publishDebug()
    options.onError?.(error)
  }

  const finishStop = async (reason: StopReason) => {
    if (stopped) return
    stopped = true
    stopReason = reason
    voiceState = reason === 'cancelled' ? 'cancelled' : 'finalizing'
    publishDebug()

    try {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: 'end_of_speech',
          reason,
          durationMs: Date.now() - startedAt,
          totalBytes,
        }))
      }
    } catch {}

    try {
      await options.bridge.audioControl(false)
    } catch {}

    unsubscribe?.()
    if (tickTimer) window.clearInterval(tickTimer)
    if (maxTimer) window.clearTimeout(maxTimer)
    if (noPcmTimer) window.clearTimeout(noPcmTimer)

    if (reason === 'cancelled') {
      window.setTimeout(() => ws.close(), 120)
      return
    }

    closeTimer = window.setTimeout(() => {
      if (!finalTranscriptReceived) ws.close()
    }, 8000)
  }

  ws.onopen = async () => {
    wsStatus = 'open'
    voiceState = 'recording'
    publishDebug()
    try {
      audioControlCalled = true
      publishDebug()
      await options.bridge.audioControl(true)
      options.onStatus?.('G2 麦克风已开启，正在听你说话。')
    } catch (error) {
      audioControlError = error instanceof Error ? error.message : String(error)
      fail(new Error(`G2 麦克风启动失败：${audioControlError}`))
    }
  }

  ws.onerror = () => {
    wsStatus = 'error'
    fail(new Error('语音 WebSocket 连接失败'))
  }

  ws.onclose = () => {
    wsStatus = 'closed'
    publishDebug()
  }

  ws.onmessage = (message) => {
    try {
      const data = JSON.parse(String(message.data)) as {
        type?: string
        text?: string
        message?: string
        provider?: string
        totalBytes?: number
        chunks?: number
        lastChunkBytes?: number
      }

      if (data.type === 'audio_debug') {
        lastServerAudioDebug = `bytes=${data.totalBytes ?? 0} chunks=${data.chunks ?? 0} last=${data.lastChunkBytes ?? 0}`
        publishDebug()
        return
      }

      if (data.type === 'partial_transcript' && data.text) {
        voiceState = 'transcribing'
        options.onStatus?.(data.text)
        publishDebug()
        return
      }

      if (data.type === 'final_transcript' && data.text) {
        finalTranscriptReceived = true
        voiceState = 'transcribing'
        lastTranscript = data.text
        publishDebug()
        options.onTranscript?.(data.text, {
          provider: data.provider,
          durationMs: Date.now() - startedAt,
          totalBytes,
          mode,
        })
        if (closeTimer) window.clearTimeout(closeTimer)
        window.setTimeout(() => ws.close(), 200)
        return
      }

      if (data.type === 'asr_error' || data.type === 'error') {
        fail(new Error(data.message || data.text || '语音识别失败'))
      }
    } catch {}
  }

  unsubscribe = options.bridge.onEvenHubEvent((event: EvenHubEvent) => {
    if (stopped) return
    const pcm = event.audioEvent?.audioPcm
    if (!pcm) return
    const bytes = toUint8Array(pcm)
    totalBytes += bytes.byteLength
    chunks += 1
    lastChunkBytes = bytes.byteLength
    lastChunkAt = new Date().toLocaleTimeString()
    console.info('[voice:g2] pcm', { bytes: bytes.byteLength, totalBytes, chunks })
    if (ws.readyState === WebSocket.OPEN) ws.send(bytes)
    publishDebug()
  })

  tickTimer = window.setInterval(publishDebug, 500)
  maxTimer = window.setTimeout(() => {
    options.onMaxDuration?.()
    void finishStop('max_duration')
  }, options.maxDurationMs)
  noPcmTimer = window.setTimeout(() => {
    if (!stopped && totalBytes === 0) {
      voiceState = 'no_pcm'
      lastVoiceError = '5 秒内未收到 G2 麦克风 PCM 数据'
      publishDebug()
      options.onStatus?.('未收到 G2 麦克风数据。')
    }
  }, 5000)

  return {
    stop: finishStop,
  }
}

export function toUint8Array(pcm: unknown): Uint8Array {
  if (pcm instanceof Uint8Array) return pcm
  if (pcm instanceof ArrayBuffer) return new Uint8Array(pcm)
  if (Array.isArray(pcm)) return new Uint8Array(pcm)
  if (ArrayBuffer.isView(pcm)) {
    return new Uint8Array(pcm.buffer, pcm.byteOffset, pcm.byteLength)
  }
  return new Uint8Array(pcm as ArrayLike<number>)
}
