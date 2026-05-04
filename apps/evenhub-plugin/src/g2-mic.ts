import type { EvenAppBridge, EvenHubEvent } from '@evenrealities/even_hub_sdk'

export interface G2MicRecording {
  audioBase64: string
  bytes: number
  durationMs: number
  sampleRate: 16000
  channels: 1
  format: 'pcm_s16le'
}

export async function recordG2Mic(
  bridge: EvenAppBridge,
  durationMs: number,
  onProgress?: (bytes: number) => void,
): Promise<G2MicRecording> {
  const chunks: Uint8Array[] = []
  let totalBytes = 0
  let unsubscribe: (() => void) | undefined

  const startedAt = performance.now()

  try {
    unsubscribe = bridge.onEvenHubEvent((event: EvenHubEvent) => {
      const pcm = event.audioEvent?.audioPcm
      if (!pcm) return

      const chunk = toBytes(pcm)
      chunks.push(chunk)
      totalBytes += chunk.byteLength
      onProgress?.(totalBytes)
    })

    await bridge.audioControl(true)
    await wait(durationMs)
  } finally {
    await bridge.audioControl(false)
    unsubscribe?.()
  }

  return {
    audioBase64: bytesToBase64(concatBytes(chunks, totalBytes)),
    bytes: totalBytes,
    durationMs: Math.round(performance.now() - startedAt),
    sampleRate: 16000,
    channels: 1,
    format: 'pcm_s16le',
  }
}

function toBytes(value: Uint8Array | ArrayBuffer): Uint8Array {
  return value instanceof Uint8Array ? value : new Uint8Array(value)
}

function concatBytes(chunks: Uint8Array[], totalBytes: number): Uint8Array {
  const output = new Uint8Array(totalBytes)
  let offset = 0
  for (const chunk of chunks) {
    output.set(chunk, offset)
    offset += chunk.byteLength
  }
  return output
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = ''
  const chunkSize = 0x8000
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize))
  }
  return btoa(binary)
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}
