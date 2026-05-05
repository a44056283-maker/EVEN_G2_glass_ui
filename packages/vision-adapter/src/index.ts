import type { VisionRequest } from '@g2vva/shared'

export interface VisionDescription {
  description: string
  provider: string
  confidence?: number
}

export async function describeImage(request: VisionRequest): Promise<VisionDescription> {
  const provider = process.env.VISION_PROVIDER

  if (provider === 'minimax-vlm') {
    return describeWithMiniMaxVlm(request)
  }

  if (provider === 'http-vlm') {
    return describeWithHttpVlm(request)
  }

  if (!provider) throw new Error('真实视觉识别未配置：请设置 VISION_PROVIDER=minimax-vlm 或 http-vlm。')
  throw new Error(`不支持的真实视觉识别提供方：${provider}`)
}

async function describeWithMiniMaxVlm(request: VisionRequest): Promise<VisionDescription> {
  const apiKey = process.env.MINIMAX_API_KEY
  if (!apiKey) throw new Error('MINIMAX_API_KEY is required for minimax-vlm')

  const baseUrl = process.env.MINIMAX_BASE_URL ?? 'https://api.minimaxi.com/v1'
  const response = await fetch(`${baseUrl}/coding_plan/vlm`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      prompt: buildVisionPrompt(request),
      image_url: `data:${request.mimeType ?? 'image/jpeg'};base64,${request.imageBase64}`,
    }),
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(`MiniMax VLM failed: ${response.status} ${text}`)
  }

  const data = (await response.json()) as {
    content?: string
    base_resp?: { status_code?: number; status_msg?: string }
  }

  if (data.base_resp?.status_code && data.base_resp.status_code !== 0) {
    throw new Error(`MiniMax VLM failed: ${data.base_resp.status_code} ${data.base_resp.status_msg ?? ''}`)
  }

  return {
    provider: 'minimax-vlm',
    description: data.content?.trim() || '视觉接口没有返回图片描述。',
  }
}

async function describeWithHttpVlm(request: VisionRequest): Promise<VisionDescription> {
  const endpoint = process.env.VISION_HTTP_ENDPOINT
  if (!endpoint) throw new Error('VISION_HTTP_ENDPOINT is required for http-vlm')

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(process.env.VISION_HTTP_API_KEY ? { Authorization: `Bearer ${process.env.VISION_HTTP_API_KEY}` } : {}),
    },
    body: JSON.stringify({ ...request, prompt: buildVisionPrompt(request) }),
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(`HTTP VLM failed: ${response.status} ${text}`)
  }

  const data = (await response.json()) as { description?: string; text?: string; answer?: string; confidence?: number }
  return {
    provider: 'http-vlm',
    description: data.description ?? data.text ?? data.answer ?? '视觉接口没有返回描述。',
    confidence: data.confidence,
  }
}

function buildVisionPrompt(request: VisionRequest): string {
  return [
    '请真实识别这张手机摄像头图片。用中文简要说明画面中的主要人物、物体、文字、场景和需要注意的信息。',
    '必须区分你实际看见的内容和上下文推断；不要编造看不见的内容。',
    '如果画面模糊、遮挡、曝光不足或无法确认，请明确说明不确定点。',
    request.capturedAt ? `拍摄时间：${request.capturedAt}` : '',
    request.locationContext ? `位置上下文：${request.locationContext}` : '',
    request.recentVisionContext ? `近期视觉上下文：${request.recentVisionContext}` : '',
    request.prompt ? `用户问题：${request.prompt}` : '',
  ]
    .filter(Boolean)
    .join('\n')
}
