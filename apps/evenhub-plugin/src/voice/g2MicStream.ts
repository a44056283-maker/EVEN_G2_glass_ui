import type { EvenAppBridge, EvenHubEvent } from '@evenrealities/even_hub_sdk'
import { waitForEvenAppBridge } from '@evenrealities/even_hub_sdk'

export interface G2MicStreamOptions {
  wsUrl: string
  onStatus?: (text: string) => void
  onTranscript?: (text: string) => void
  onAnswer?: (text: string, audioUrl?: string) => void
  onBytes?: (bytes: number) => void
  onError?: (text: string) => void
}

export async function startG2MicStream(options: G2MicStreamOptions): Promise<() => Promise<void>> {
  const bridge = await waitForEvenAppBridge()
  const ws = new WebSocket(`${options.wsUrl.replace(/\/+$/, '')}/audio`)
  ws.binaryType = 'arraybuffer'

  let totalBytes = 0
  let unsubscribe: (() => void) | undefined
  let audioEnabled = false

  ws.onopen = async () => {
    options.onStatus?.('天禄正在监听 G2 麦克风')
    await bridge.audioControl(true)
    audioEnabled = true
  }

  ws.onerror = () => {
    const message = '语音连接失败，请检查 G2 Bridge 后端'
    options.onStatus?.(message)
    options.onError?.(message)
  }

  ws.onclose = () => {
    if (!audioEnabled) return
    void bridge.audioControl(false).catch(() => undefined)
    audioEnabled = false
  }

  ws.onmessage = (message) => {
    let data: {
      type?: string
      text?: string
      audioUrl?: string
      bytes?: number
    }

    try {
      data = JSON.parse(String(message.data)) as typeof data
    } catch {
      return
    }

    if (data.type === 'partial_transcript' && data.text) options.onStatus?.(`听到：${data.text}`)
    if (data.type === 'final_transcript' && data.text) options.onTranscript?.(data.text)
    if (data.type === 'answer' && data.text) options.onAnswer?.(data.text, data.audioUrl)
    if (data.type === 'audio_bytes' && data.bytes) options.onStatus?.(`收到语音数据：${data.bytes} bytes`)
    if (data.type === 'error') {
      const text = data.text || 'G2 语音识别失败'
      options.onStatus?.(text)
      options.onError?.(text)
    }
  }

  unsubscribe = bridge.onEvenHubEvent((event: EvenHubEvent) => {
    const pcm = event.audioEvent?.audioPcm
    if (!pcm || ws.readyState !== WebSocket.OPEN) return
    const bytes = toBytes(pcm)
    totalBytes += bytes.byteLength
    options.onBytes?.(totalBytes)
    ws.send(bytes)
  })

  return async () => {
    unsubscribe?.()
    if (audioEnabled) {
      try {
        await bridge.audioControl(false)
      } catch {}
    }
    ws.close()
  }
}

function toBytes(value: Uint8Array | ArrayBuffer): Uint8Array {
  return value instanceof Uint8Array ? value : new Uint8Array(value)
}
