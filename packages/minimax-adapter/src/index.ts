import type { LocaleCode, TtsResponse } from '@g2vva/shared'

export interface MiniMaxConfig {
  apiKey?: string
  baseUrl: string
  textModel: string
  ttsModel: string
  ttsVoiceId: string
}

export function getMiniMaxConfig(env: NodeJS.ProcessEnv = process.env): MiniMaxConfig {
  return {
    apiKey: env.MINIMAX_API_KEY,
    baseUrl: env.MINIMAX_BASE_URL ?? 'https://api.minimax.io/v1',
    textModel: env.MINIMAX_TEXT_MODEL ?? 'MiniMax-M2.7-highspeed',
    ttsModel: env.MINIMAX_TTS_MODEL ?? 'speech-2.8-hd',
    ttsVoiceId: env.MINIMAX_TTS_VOICE_ID ?? 'female-shaonv',
  }
}

export async function askMiniMax(
  input: {
    system?: string
    user: string
    locale?: LocaleCode
  },
  config = getMiniMaxConfig(),
): Promise<string> {
  if (!config.apiKey) {
    const visionMatch = input.user.match(/画面描述：(.+?)(\n用户问题：|$)/s)
    if (visionMatch?.[1]) {
      return visionMatch[1].trim().slice(0, 180)
    }

    const questionMatch = input.user.match(/用户问题：(.+)$/s)
    if (questionMatch?.[1]) {
      return `收到问题：${questionMatch[1].trim().slice(0, 150)}`
    }

    return input.user.trim().slice(0, 180)
  }

  const response = await fetch(`${config.baseUrl}/chat/completions`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${config.apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: config.textModel,
      messages: [
        {
          role: 'system',
          content:
            input.system ??
            '你是运行在 Even G2 智能眼镜上的视觉助手。只输出最终答案，不要输出思考过程、分析过程、<think> 标签或 Markdown。回答必须简短、清楚、适合 576x288 小屏幕显示。',
        },
        { role: 'user', content: input.user },
      ],
      temperature: 0.3,
    }),
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(`MiniMax chat failed: ${response.status} ${text}`)
  }

  const data = (await response.json()) as {
    choices?: Array<{ message?: { content?: string } }>
  }
  return cleanMiniMaxAnswer(data.choices?.[0]?.message?.content) || '没有收到有效回答。'
}

function cleanMiniMaxAnswer(content: string | undefined): string {
  return (content ?? '')
    .replace(/<think>[\s\S]*?<\/think>/gi, '')
    .replace(/^\s*[\r\n]+/, '')
    .trim()
}

export async function synthesizeMiniMaxTts(
  request: { text: string; locale?: LocaleCode; voiceId?: string },
  config = getMiniMaxConfig(),
): Promise<TtsResponse> {
  if (!config.apiKey) {
    return {
      provider: 'browser-fallback',
      fallbackText: request.text,
    }
  }

  // MiniMax TTS model and response fields can vary by account/version.
  // Keep the adapter isolated so the endpoint can be adjusted without touching the app.
  const response = await fetch(`${config.baseUrl}/t2a_v2`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${config.apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: config.ttsModel,
      text: request.text,
      stream: false,
      voice_setting: {
        voice_id: request.voiceId ?? config.ttsVoiceId,
        speed: 1.04,
        vol: 1,
        pitch: 1,
      },
      audio_setting: {
        sample_rate: 32000,
        bitrate: 128000,
        format: 'mp3',
        channel: 1,
      },
    }),
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(`MiniMax TTS failed: ${response.status} ${text}`)
  }

  const data = (await response.json()) as {
    data?: { audio?: string }
    audio?: string
  }
  const audio = data.data?.audio ?? data.audio

  return {
    provider: 'minimax',
    audioBase64: audio ? hexToBase64(audio) : undefined,
    mimeType: 'audio/mpeg',
    fallbackText: request.text,
  }
}

function hexToBase64(value: string): string {
  if (!/^[\da-f]+$/i.test(value) || value.length % 2 !== 0) return value
  return Buffer.from(value, 'hex').toString('base64')
}
