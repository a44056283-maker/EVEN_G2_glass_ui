const defaultHttpUrl = import.meta.env.VITE_G2_BRIDGE_HTTP_URL ?? 'https://g2-vision.tianlu2026.org'
const defaultWsUrl =
  import.meta.env.VITE_G2_BRIDGE_WS_URL ?? defaultHttpUrl.replace(/^http/i, (match: string) => (match === 'https' ? 'wss' : 'ws'))
const defaultToken = import.meta.env.VITE_G2_SESSION_TOKEN ?? ''

export function getG2BridgeHttpUrl(): string {
  return String(defaultHttpUrl).replace(/\/+$/, '')
}

export function getG2BridgeWsUrl(): string {
  return String(defaultWsUrl).replace(/\/+$/, '')
}

export function getG2SessionToken(): string {
  return String(defaultToken)
}

export async function postVision(imageBase64: string, prompt?: string): Promise<{ answer: string }> {
  const response = await fetch(`${getG2BridgeHttpUrl()}/vision`, {
    method: 'POST',
    headers: bridgeHeaders(),
    body: JSON.stringify({ imageBase64, mimeType: 'image/jpeg', prompt, locale: navigator.language || 'zh-CN' }),
  })
  if (!response.ok) throw new Error(`视觉请求失败：${response.status} ${await safeText(response)}`)
  return response.json()
}

export async function postAsk(text: string): Promise<{ answer: string; audioUrl?: string }> {
  const response = await fetch(`${getG2BridgeHttpUrl()}/ask`, {
    method: 'POST',
    headers: bridgeHeaders(),
    body: JSON.stringify({ question: text, text, userId: 'g2-user', locale: navigator.language || 'zh-CN' }),
  })
  if (!response.ok) throw new Error(`天禄问答失败：${response.status} ${await safeText(response)}`)
  return response.json()
}

export function connectAudioWebSocket(): WebSocket {
  return new WebSocket(`${getG2BridgeWsUrl()}/audio?token=${encodeURIComponent(getG2SessionToken())}`)
}

function bridgeHeaders(): HeadersInit {
  const token = getG2SessionToken()
  return {
    'Content-Type': 'text/plain;charset=UTF-8',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

async function safeText(response: Response): Promise<string> {
  try {
    return await response.text()
  } catch {
    return ''
  }
}
