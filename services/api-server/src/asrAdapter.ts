export interface StreamingAsrResult {
  text: string
  provider: string
}

export async function transcribePcmBuffer(pcm: Buffer): Promise<StreamingAsrResult> {
  const provider = (process.env.ASR_PROVIDER ?? '').toLowerCase()

  if (provider === 'http') {
    return transcribeWithHttp(pcm)
  }

  if (provider === 'mock') {
    return {
      provider: 'mock',
      text: '你好天禄，帮我看一下交易机器人运行如何',
    }
  }

  if (provider === 'minimax' || provider === 'minimax-asr') {
    const endpoint = process.env.MINIMAX_ASR_ENDPOINT
    if (!endpoint) {
      throw new Error('真实 ASR 未接入：ASR_PROVIDER=minimax 但 MINIMAX_ASR_ENDPOINT 为空，G2 麦克风 PCM 已收到但不能转文字。')
    }
    return transcribeWithHttpEndpoint(pcm, endpoint, {
      provider: 'minimax-asr',
      authorization: process.env.MINIMAX_API_KEY ? `Bearer ${process.env.MINIMAX_API_KEY}` : undefined,
      model: process.env.MINIMAX_ASR_MODEL ?? 'minimax-asr',
    })
  }

  throw new Error('真实 ASR 未接入：请配置 ASR_PROVIDER=http + ASR_HTTP_URL，或配置 MiniMax 可用的 MINIMAX_ASR_ENDPOINT。')
}

async function transcribeWithHttp(pcm: Buffer): Promise<StreamingAsrResult> {
  const url = process.env.ASR_HTTP_URL
  if (!url) {
    throw new Error('真实 ASR 未接入：ASR_PROVIDER=http 但 ASR_HTTP_URL 为空。')
  }

  return transcribeWithHttpEndpoint(pcm, url, {
    provider: 'http',
    authorization: process.env.ASR_HTTP_API_KEY ? `Bearer ${process.env.ASR_HTTP_API_KEY}` : undefined,
  })
}

async function transcribeWithHttpEndpoint(
  pcm: Buffer,
  url: string,
  options: { provider: string; authorization?: string; model?: string },
): Promise<StreamingAsrResult> {
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(options.authorization ? { Authorization: options.authorization } : {}),
    },
    body: JSON.stringify({
      model: options.model,
      audioBase64: pcm.toString('base64'),
      format: 'pcm_s16le',
      sampleRate: 16000,
      channels: 1,
    }),
  })

  if (!response.ok) {
    throw new Error(`ASR HTTP failed: ${response.status} ${(await response.text()).slice(0, 240)}`)
  }

  const data = (await response.json()) as { text?: string; result?: string; data?: { text?: string } }
  return {
    provider: options.provider,
    text: (data.text ?? data.result ?? data.data?.text ?? '').trim(),
  }
}
