export interface OpenClawRequest {
  system?: string
  user: string
  locale?: string
}

export interface OpenClawResult {
  answer: string
  provider: string
}

interface OpenClawChoice {
  message?: {
    content?: string
  }
  text?: string
}

interface OpenClawResponse {
  choices?: OpenClawChoice[]
  output_text?: string
  message?: string
  answer?: string
  content?: string
  error?: string
}

export function isOpenClawEnabled(): boolean {
  return process.env.OPENCLAW_ENABLED === 'true' && Boolean(process.env.OPENCLAW_BASE_URL)
}

export function getOpenClawPublicStatus(): { enabled: boolean; baseUrl: string; model: string; agent: string } {
  return {
    enabled: isOpenClawEnabled(),
    baseUrl: process.env.OPENCLAW_BASE_URL ? maskUrl(process.env.OPENCLAW_BASE_URL) : '',
    model: process.env.OPENCLAW_MODEL ?? 'g2-bridge',
    agent: process.env.OPENCLAW_AGENT_NAME ?? 'open law2026',
  }
}

export async function askOpenClaw(request: OpenClawRequest): Promise<OpenClawResult | undefined> {
  if (!isOpenClawEnabled()) return undefined

  const baseUrl = String(process.env.OPENCLAW_BASE_URL).replace(/\/+$/, '')
  const token = process.env.OPENCLAW_GATEWAY_TOKEN ?? process.env.OPENCLAW_TOKEN
  const model = process.env.OPENCLAW_AGENT_MODEL ?? process.env.OPENCLAW_MODEL ?? 'openclaw/tianlu'
  const endpointMode = process.env.OPENCLAW_ENDPOINT ?? 'chat_completions'
  const endpoint = endpointMode === 'responses' ? `${baseUrl}/v1/responses` : `${baseUrl}/v1/chat/completions`
  const timeoutMs = Number(process.env.OPENCLAW_TIMEOUT_MS ?? 20000)
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(
        endpointMode === 'responses'
          ? {
              model,
              input: [
                request.system ? { role: 'system', content: request.system } : undefined,
                { role: 'user', content: request.user },
              ].filter(Boolean),
            }
          : {
              model,
              messages: [
                request.system ? { role: 'system', content: request.system } : undefined,
                { role: 'user', content: request.user },
              ].filter(Boolean),
              locale: request.locale ?? 'zh-CN',
            },
      ),
      signal: controller.signal,
    })

    const raw = await response.text()
    if (!response.ok) {
      throw new Error(formatOpenClawHttpError(response.status, raw))
    }

    const data = parseOpenClawResponse(raw)
    const answer = extractOpenClawAnswer(data)
    if (!answer) throw new Error('OpenCLAW returned empty answer')
    if (/Gateway\s*502|Gateway 暫時無法連線|Gateway 暂时无法连接/i.test(answer)) {
      throw new Error(answer)
    }

    return {
      answer,
      provider: `openclaw:${model}`,
    }
  } finally {
    clearTimeout(timer)
  }
}

function formatOpenClawHttpError(status: number, raw: string): string {
  if (status === 401 || status === 403) return 'OpenCLAW 认证失败，请检查 OPENCLAW_GATEWAY_TOKEN'
  if (status === 404) return 'OpenCLAW 未连接，请检查 OPENCLAW_BASE_URL'
  if (status === 405) return 'OpenCLAW HTTP endpoint 未启用，请检查 gateway 配置'
  return `OpenCLAW failed: ${status} ${raw.slice(0, 240)}`
}

function parseOpenClawResponse(raw: string): OpenClawResponse {
  try {
    return JSON.parse(raw) as OpenClawResponse
  } catch {
    return { content: raw }
  }
}

function extractOpenClawAnswer(data: OpenClawResponse): string {
  return (
    data.choices?.[0]?.message?.content ??
    data.choices?.[0]?.text ??
    data.output_text ??
    data.answer ??
    data.message ??
    data.content ??
    ''
  ).trim()
}

function maskUrl(url: string): string {
  try {
    const parsed = new URL(url)
    return parsed.origin
  } catch {
    return url.replace(/[?#].*$/, '')
  }
}
