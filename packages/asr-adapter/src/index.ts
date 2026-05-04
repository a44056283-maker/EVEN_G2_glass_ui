import type { AsrStatusResponse, TranscribeRequest, TranscribeResponse } from '@g2vva/shared'

export function getAsrStatus(env: NodeJS.ProcessEnv = process.env): AsrStatusResponse {
  const provider = (env.ASR_PROVIDER ?? '').toLowerCase()

  if (provider === 'mock') {
    return {
      available: true,
      provider: 'mock',
      message: 'ASR 当前为 mock 模式，仅用于链路验收。',
    }
  }

  if (provider === 'http') {
    if (!env.ASR_HTTP_URL) {
      return {
        available: false,
        provider: 'http',
        reason: 'not-configured',
        message: 'ASR_PROVIDER=http 但 ASR_HTTP_URL 为空。',
      }
    }

    return {
      available: true,
      provider: 'http',
      message: 'HTTP ASR 已配置。',
    }
  }

  if (provider === 'minimax' || provider === 'minimax-asr') {
    if (!env.MINIMAX_API_KEY) {
      return {
        available: false,
        provider: 'minimax-asr',
        reason: 'missing-key',
        message: 'G2 麦克风转文字暂未开启；点击“呼叫天禄”会尝试手机语音输入。',
      }
    }

    if (!env.MINIMAX_ASR_ENDPOINT) {
      return {
        available: false,
        provider: 'minimax-asr',
        reason: 'not-configured',
        message: 'G2 麦克风可以录音，但 MiniMax ASR 端点未配置，暂时不能把 PCM 音频转文字。',
      }
    }

    return {
      available: true,
      provider: `minimax-asr:${env.MINIMAX_ASR_MODEL ?? 'minimax-asr'}`,
      message: 'MiniMax ASR 已配置，可以把 G2 麦克风音频转成文字。',
    }
  }

  return {
    available: false,
    provider: env.ASR_PROVIDER ?? 'not-configured',
    reason: 'not-configured',
    message: 'G2 麦克风可以录音，但后端真实 ASR 接口未启用，暂时不能把 PCM 音频转文字。',
  }
}

export async function transcribeAudio(request: TranscribeRequest): Promise<TranscribeResponse> {
  const provider = (process.env.ASR_PROVIDER ?? '').toLowerCase()

  if (provider === 'mock') {
    return {
      provider: 'mock',
      text: '你好天禄，帮我看一下交易机器人运行如何',
    }
  }

  if (provider === 'http') {
    return transcribeWithHttp(request)
  }

  if (provider === 'minimax' || provider === 'minimax-asr') {
    return transcribeWithMiniMax(request)
  }

  return {
    provider: process.env.ASR_PROVIDER ?? 'not-configured',
    text: '',
  }
}

async function transcribeWithHttp(request: TranscribeRequest): Promise<TranscribeResponse> {
  const endpoint = process.env.ASR_HTTP_URL
  if (!endpoint) {
    return {
      provider: 'http-asr-not-configured',
      text: '',
    }
  }

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      ...(process.env.ASR_HTTP_API_KEY ? { Authorization: `Bearer ${process.env.ASR_HTTP_API_KEY}` } : {}),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      audioBase64: request.audioBase64,
      sampleRate: request.sampleRate,
      channels: request.channels,
      format: request.format,
      mimeType: request.mimeType,
      durationMs: request.durationMs,
      source: request.source,
      locale: request.locale,
    }),
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(`HTTP ASR failed: ${response.status} ${text}`)
  }

  const data = (await response.json()) as {
    text?: string
    result?: string
    transcript?: string
    data?: { text?: string; result?: string; transcript?: string }
  }

  return {
    provider: 'http-asr',
    text: (data.text ?? data.result ?? data.transcript ?? data.data?.text ?? data.data?.result ?? data.data?.transcript ?? '').trim(),
  }
}

async function transcribeWithMiniMax(request: TranscribeRequest): Promise<TranscribeResponse> {
  const apiKey = process.env.MINIMAX_API_KEY
  const endpoint = process.env.MINIMAX_ASR_ENDPOINT
  const model = process.env.MINIMAX_ASR_MODEL ?? 'minimax-asr'

  if (!apiKey) {
    return {
      provider: 'minimax-asr-missing-key',
      text: '',
    }
  }

  if (!endpoint) {
    return {
      provider: 'minimax-asr-not-configured',
      text: '',
    }
  }

  const format = request.format || 'pcm_s16le'
  if (format !== 'pcm_s16le') {
    return {
      provider: `minimax-asr-unsupported-format:${format}`,
      text: '',
    }
  }

  const pcm = Buffer.from(request.audioBase64 || '', 'base64')
  if (pcm.length === 0) {
    return {
      provider: 'minimax-asr-empty-audio',
      text: '',
    }
  }

  const wav = pcmToWav(pcm, request.sampleRate ?? 16000, request.channels ?? 1)
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model,
      audio: wav.toString('base64'),
      audio_format: 'wav',
      sample_rate: request.sampleRate ?? 16000,
      channels: request.channels ?? 1,
      language: localeToLanguage(request.locale),
    }),
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(`MiniMax ASR failed: ${response.status} ${text}`)
  }

  const data = (await response.json()) as {
    text?: string
    result?: string
    data?: { text?: string; result?: string }
  }
  const text = data.text ?? data.result ?? data.data?.text ?? data.data?.result ?? ''

  return {
    provider: `minimax-asr:${model}`,
    text: text.trim(),
  }
}

function pcmToWav(pcm: Buffer, sampleRate: number, channels: number): Buffer {
  const bitsPerSample = 16
  const byteRate = (sampleRate * channels * bitsPerSample) / 8
  const blockAlign = (channels * bitsPerSample) / 8
  const header = Buffer.alloc(44)

  header.write('RIFF', 0)
  header.writeUInt32LE(36 + pcm.length, 4)
  header.write('WAVE', 8)
  header.write('fmt ', 12)
  header.writeUInt32LE(16, 16)
  header.writeUInt16LE(1, 20)
  header.writeUInt16LE(channels, 22)
  header.writeUInt32LE(sampleRate, 24)
  header.writeUInt32LE(byteRate, 28)
  header.writeUInt16LE(blockAlign, 32)
  header.writeUInt16LE(bitsPerSample, 34)
  header.write('data', 36)
  header.writeUInt32LE(pcm.length, 40)

  return Buffer.concat([header, pcm])
}

function localeToLanguage(locale: string | undefined): string {
  if (!locale) return 'zh'
  return locale.toLowerCase().startsWith('zh') ? 'zh' : locale.split('-')[0] || 'zh'
}
