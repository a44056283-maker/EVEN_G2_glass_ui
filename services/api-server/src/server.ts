import cors from '@fastify/cors'
import websocket from '@fastify/websocket'
import { getAsrStatus, transcribeAudio } from '@g2vva/asr-adapter'
import { formatMemoryContext, searchMemory } from '@g2vva/memory-adapter'
import { askMiniMax, synthesizeMiniMaxTts } from '@g2vva/minimax-adapter'
import type {
  AskRequest,
  AskResponse,
  AsrStatusResponse,
  OpenClawStatusResponse,
  TtsRequest,
  TtsResponse,
  TranscribeRequest,
  TranscribeResponse,
  TradingReadonlyOverview,
  VisionRequest,
  VisionResponse,
} from '@g2vva/shared'
import { buildTradingAskContext, getTradingReadonlyOverview } from '@g2vva/trading-adapter'
import { describeImage } from '@g2vva/vision-adapter'
import dotenv from 'dotenv'
import Fastify from 'fastify'
import { existsSync } from 'node:fs'
import { appendFile, mkdir } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { askOpenClaw, getOpenClawPublicStatus } from './openclaw.js'
import { transcribePcmBuffer } from './asrAdapter.js'

const here = dirname(fileURLToPath(import.meta.url))
const envPath = [
  resolve(process.cwd(), '.env'),
  resolve(process.cwd(), '../../.env'),
  resolve(here, '../.env'),
  resolve(here, '../../../.env'),
].find((candidate) => existsSync(candidate))

dotenv.config(envPath ? { path: envPath } : undefined)
process.env.G2_MEMORY_ROOT ??= resolve(here, '../../../data/remote-memory-cache')

const app = Fastify({
  logger: true,
  bodyLimit: 12 * 1024 * 1024,
})
const port = Number(process.env.PORT ?? 8787)
const runtimeErrorLogPath = resolve(here, '../../../docs/gpt-advisor/logs/runtime-errors.jsonl')

interface RuntimeErrorLogRequest {
  kind?: unknown
  message?: unknown
  detail?: unknown
  createdAt?: unknown
  page?: unknown
}

interface RuntimeErrorLogEntry {
  receivedAt: string
  kind: string
  message: string
  detail?: string
  createdAt?: string
  page?: string
  source: 'evenhub-plugin'
}

app.addContentTypeParser('text/plain', { parseAs: 'string' }, (_request, body, done) => {
  try {
    done(null, body ? JSON.parse(body as string) : {})
  } catch (error) {
    done(error as Error)
  }
})

await app.register(cors, {
  origin: true,
  methods: ['GET', 'POST', 'OPTIONS'],
})

await app.register(websocket)

app.get('/health', async () => ({
  ok: true,
  service: 'g2-vision-voice-api',
  time: new Date().toISOString(),
  openclaw: getOpenClawPublicStatus(),
}))

app.post<{ Body: RuntimeErrorLogRequest; Reply: { ok: true } }>('/debug/runtime-error', async (request) => {
  const entry = sanitizeRuntimeErrorLog(request.body)
  await appendRuntimeErrorLog(entry)
  return { ok: true }
})

app.post<{ Body: VisionRequest; Reply: VisionResponse }>('/vision', async (request) => {
  const startedAt = Date.now()
  const vision = await describeImage(request.body)
  const needsClarification = shouldClarifyVision(vision.description, vision.confidence)
  const answer = await askMiniMax({
    locale: request.body.locale,
    system: needsClarification
      ? [
          '你是 Even G2 眼镜视觉复核助手。只输出最终中文短回答，不要输出推理过程。',
          '画面低置信度或看不清时，必须先澄清不确定点，再给出能确认的内容或建议重新拍摄。',
          '不要把本次视觉结果写入知识库或承诺稍后保存。',
        ].join('\n')
      : undefined,
    user: buildVisionAnswerPrompt(request.body, vision.description, {
      confidence: vision.confidence,
      needsClarification,
    }),
  })

  return {
    description: vision.description,
    answer: sanitizeDirectAnswer(answer),
    provider: `vision:${vision.provider}+${needsClarification ? 'llm-review' : 'llm'}`,
    source: 'vision-api',
    elapsedMs: Date.now() - startedAt,
    createdAt: new Date().toISOString(),
    confidence: vision.confidence,
    needsClarification,
  }
})

app.post<{ Body: AskRequest & { text?: string; userId?: string }; Reply: AskResponse }>('/ask', async (request) => {
  return answerQuestion(request.body.question ?? request.body.text ?? '', {
    lastVisionSummary: request.body.lastVisionSummary,
    locale: request.body.locale,
    capturedAt: request.body.capturedAt,
    locationContext: request.body.locationContext,
  })
})

app.get('/audio', { websocket: true }, (socket, request) => {
  const query = request.query as { token?: string; mode?: string; source?: string; mockText?: string }
  const token = String(query.token ?? '')
  const mode = query.mode === 'probe' || query.mode === 'mock-asr' || query.mode === 'asr' ? query.mode : 'asr'
  const source = String(query.source ?? 'g2')
  const mockText = String(query.mockText ?? '你好天禄，帮我看一下交易机器人运行如何').trim()
  if (!isSessionTokenValid(token)) {
    socket.send(JSON.stringify({ type: 'error', text: 'G2 Bridge session token 无效' }))
    socket.close()
    return
  }

  const chunks: Buffer[] = []
  let bytes = 0
  let chunkCount = 0
  let lastChunkBytes = 0
  let startedAt = Date.now()
  let firstChunkAt = 0
  let lastChunkAt = 0
  let finalTimer: NodeJS.Timeout | undefined
  let debugTimer: NodeJS.Timeout | undefined
  let answered = false

  const sendDebug = () => {
    socket.send(JSON.stringify({
      type: 'audio_debug',
      mode,
      source,
      totalBytes: bytes,
      chunks: chunkCount,
      lastChunkBytes,
      firstChunkAt: firstChunkAt ? new Date(firstChunkAt).toISOString() : undefined,
      lastChunkAt: lastChunkAt ? new Date(lastChunkAt).toISOString() : undefined,
      durationMs: Date.now() - startedAt,
    }))
  }

  const finalize = async (reason = 'timeout') => {
    if (answered || bytes === 0) return
    answered = true
    try {
      if (mode === 'probe') return
      socket.send(JSON.stringify({ type: 'partial_transcript', text: '正在识别语音……' }))
      if (mode === 'mock-asr' && bytes < 16000 && chunkCount < 5) {
        socket.send(JSON.stringify({
          type: 'asr_error',
          message: `音频太短，暂不返回 mock transcript。bytes=${bytes} chunks=${chunkCount} reason=${reason}`,
        }))
        return
      }
      const asr = mode === 'mock-asr'
        ? { provider: 'probe-mock-asr', text: mockText || '你好天禄，帮我看一下交易机器人运行如何' }
        : await transcribePcmBuffer(Buffer.concat(chunks, bytes))
      if (!asr.text) {
        socket.send(JSON.stringify({ type: 'error', text: 'ASR 没有返回文字' }))
        return
      }
      socket.send(JSON.stringify({ type: 'final_transcript', text: asr.text, provider: asr.provider }))
    } catch (error) {
      socket.send(
        JSON.stringify({
          type: mode === 'asr' ? 'asr_error' : 'error',
          message: error instanceof Error ? error.message : String(error),
          text: error instanceof Error ? error.message : String(error),
        }),
      )
    }
  }

  socket.on('message', (message: Buffer | ArrayBuffer | Buffer[]) => {
    const maybeText = decodeTextMessage(message)
    if (maybeText) {
      try {
        const data = JSON.parse(maybeText) as { type?: string; reason?: string; durationMs?: number; totalBytes?: number }
        if (data.type === 'end_of_speech') {
          sendDebug()
          void finalize(data.reason || 'end_of_speech')
          return
        }
      } catch {
        app.log.info({ message: maybeText.slice(0, 120) }, 'Ignoring non-JSON audio text message')
      }
    }

    const chunk = messageToBuffer(message)
    if (chunk.byteLength === 0) return
    startedAt = startedAt || Date.now()
    firstChunkAt ||= Date.now()
    lastChunkAt = Date.now()
    lastChunkBytes = chunk.byteLength
    chunks.push(chunk)
    bytes += chunk.byteLength
    chunkCount += 1
    socket.send(JSON.stringify({ type: 'audio_bytes', bytes }))
    if (mode === 'probe') {
      sendDebug()
      return
    }
    if (finalTimer) clearTimeout(finalTimer)
    finalTimer = setTimeout(() => void finalize(), Number(process.env.G2_AUDIO_FINALIZE_MS ?? 1400))
  })

  debugTimer = setInterval(sendDebug, 1000)

  socket.on('close', () => {
    if (finalTimer) clearTimeout(finalTimer)
    if (debugTimer) clearInterval(debugTimer)
  })
})

function decodeTextMessage(message: Buffer | ArrayBuffer | Buffer[]): string {
  const chunk = messageToBuffer(message)
  const text = chunk.toString('utf8').trim()
  if (!text.startsWith('{')) return ''
  return text
}

function messageToBuffer(message: Buffer | ArrayBuffer | Buffer[]): Buffer {
  if (Buffer.isBuffer(message)) return message
  if (Array.isArray(message)) return Buffer.concat(message)
  return Buffer.from(message)
}

function buildVisionAnswerPrompt(
  request: VisionRequest,
  description: string,
  options: { confidence?: number; needsClarification: boolean },
): string {
  return [
    options.needsClarification
      ? '请复核下面的视觉识别结果，生成澄清式短回答。'
      : '请把下面的画面描述整理成适合 Even G2 眼镜小屏幕显示的中文短回答。',
    '要求：最多 4 行；先说重点；不要写成营销文案；看不清就明确说看不清。',
    '位置、近期画面和拍摄时间只能作为辅助上下文，不能替代图片中实际可见内容。',
    '不要自动写入知识库，不要承诺保存或异步同步。',
    request.capturedAt ? `拍摄时间：${request.capturedAt}` : '',
    request.locationContext ? `位置上下文：${request.locationContext}` : '',
    request.recentVisionContext ? `近期视觉上下文：${request.recentVisionContext}` : '',
    typeof options.confidence === 'number' ? `视觉置信度：${options.confidence}` : '',
    `画面描述：${description}`,
    request.prompt ? `用户问题：${request.prompt}` : '',
  ]
    .filter(Boolean)
    .join('\n')
}

function shouldClarifyVision(description: string, confidence?: number): boolean {
  if (typeof confidence === 'number') {
    const normalizedConfidence = confidence > 1 ? confidence / 100 : confidence
    if (normalizedConfidence < 0.55) return true
  }
  return /看不清|无法看清|不清楚|无法确认|不能确定|不确定|模糊|遮挡|曝光不足|太暗|过曝|识别不到|没有返回/.test(description)
}

async function answerQuestion(
  question: string,
  options: {
    lastVisionSummary?: string
    locale?: string
    capturedAt?: string
    locationContext?: string
  } = {},
): Promise<AskResponse> {
  const finalQuestion = question.trim()
  const { lastVisionSummary, locale, capturedAt, locationContext } = options
  if (!finalQuestion) {
    return {
      answer: '没有收到问题。请说：你好天禄，帮我看一下我们的交易机器人运行如何。',
      provider: 'local:empty-question',
      createdAt: new Date().toISOString(),
    }
  }

  const tradingIntent = isTradingQuestionText(finalQuestion)
  const tradingOverview = tradingIntent
    ? await getTradingReadonlyOverview().catch((error) => {
        app.log.warn({ error }, 'Trading readonly overview unavailable')
        return undefined
      })
    : undefined
  const tradingContext = tradingIntent
    ? {
        isTradingRelated: true,
        mode: tradingOverview?.mode ?? ('live-readonly' as const),
        context: [
          '当前问题命中交易机器人只读查询；必须优先使用控制台公网实时只读数据，不执行任何交易动作。',
          tradingOverview ? formatTradingOverviewContext(tradingOverview) : '实时交易只读概览暂未返回。',
        ].join('\n'),
        hits: [],
      }
    : await buildTradingAskContext(finalQuestion)
  const memory = tradingContext.isTradingRelated
    ? { hits: [] }
    : await searchMemory(finalQuestion, { limit: 5 })
  const memoryContext = formatMemoryContext(memory.hits)

  if (tradingIntent) {
    return {
      answer: formatTradingReadonlyAnswer(tradingOverview),
      provider: tradingOverview?.live?.error ? 'local:trading-live-error' : 'local:trading-live-readonly',
      createdAt: new Date().toISOString(),
    }
  }

  const system = [
    '你是 Even G2 眼镜语音问答助手。回答要短，适合眼镜显示和语音朗读。',
    '所有回答必须直接返回给当前页面和眼镜显示；禁止说“稍后发送到 Telegram/电报/TG/手机/第三方平台”，禁止承诺异步转发。',
    '你可以引用本机同步的天禄记忆，但只输出结论，不要泄露密钥、路径中的敏感信息或大段原文。',
    '如果提供了实时位置上下文，只能作为当前语音问答的辅助信息；不得输出精确坐标，不得把位置写入长期记忆。',
    '如果问题需要调用交易系统，只允许只读查看和风险解释，不允许下单、改仓、平仓或绕过风控。',
    tradingContext.isTradingRelated
      ? '交易系统相关回答必须只做只读分析、复盘、风险提示和操作建议清单；不得声称已经下单、改仓、平仓或直接执行交易。V6.5 是硬规则层，AI 只做审核员/管理员。若实时数据未接入，只能明确说明“当前为记忆/历史记录口径”。'
      : '',
  ]
    .filter(Boolean)
    .join('\n')
  const user = [
    !tradingIntent && capturedAt ? `提问时间：${capturedAt}` : '',
    !tradingIntent && locationContext ? `实时位置上下文：${locationContext}` : '',
    tradingContext.context,
    memoryContext ? `已检索到的天禄记忆：\n${memoryContext}` : '',
    lastVisionSummary ? `最近画面摘要：${lastVisionSummary}` : '',
    `用户问题：${finalQuestion}`,
  ]
    .filter(Boolean)
    .join('\n')

  const shouldUseOpenClaw = tradingIntent || tradingContext.isTradingRelated
  const openClaw = shouldUseOpenClaw
    ? await withTimeout(
        askOpenClaw({
          locale,
          system,
          user,
        }),
        tradingIntent ? 2500 : 6000,
      ).catch((error) => {
        app.log.warn({ error }, 'OpenCLAW unavailable; falling back to MiniMax')
        return undefined
      })
    : undefined

  if (openClaw) {
    return {
      answer: sanitizeDirectAnswer(openClaw.answer),
      provider: openClaw.provider,
      createdAt: new Date().toISOString(),
    }
  }

  const answer = await askMiniMax({
    locale,
    system,
    user,
  })
  const cleanedAnswer = sanitizeDirectAnswer(answer)
  if (!isGenericNoAnswer(cleanedAnswer)) {
    return {
      answer: cleanedAnswer,
      provider: 'minimax:fallback',
      createdAt: new Date().toISOString(),
    }
  }

  const retryAnswer = await askMiniMax({
    locale,
    system: [
      '你是天禄助手。你必须直接回答用户当前问题，不能说“收到问题”“稍后显示”“发到手机”“发到 Telegram”。',
      '如果缺少实时位置、联网搜索或外部数据，就明确说明限制，并给出可用的通用建议。',
      '回答要短、中文、可直接显示在手机网页和 Even G2 眼镜上。',
    ].join('\n'),
    user: [
      lastVisionSummary ? `最近画面摘要：${lastVisionSummary}` : '',
      `用户问题：${finalQuestion}`,
      '请现在直接回答。',
    ]
      .filter(Boolean)
      .join('\n'),
  }).catch((error) => {
    app.log.warn({ error }, 'MiniMax strict retry failed')
    return ''
  })
  const cleanedRetry = sanitizeDirectAnswer(retryAnswer)

  return {
    answer: isGenericNoAnswer(cleanedRetry) ? buildLocalGeneralFallback(finalQuestion) : cleanedRetry,
    provider: isGenericNoAnswer(cleanedRetry) ? 'local:general-fallback' : 'minimax:fallback-retry',
    createdAt: new Date().toISOString(),
  }
}

app.get('/trading/overview', async () => enrichTradingOverviewWithAi(await getTradingReadonlyOverview()))

app.get('/glasses/api/summary', async () => {
  const overview = await enrichTradingOverviewWithAi(await getTradingReadonlyOverview(), { compact: true })
  const live = overview.live
  return {
    ok: Boolean(live && !live.error),
    ts: Date.now(),
    source: live?.baseUrl ?? 'https://console.tianlu2026.org',
    stale: Boolean(live?.error),
    console: { health: live?.error ? 'degraded' : 'healthy' },
    bots: {
      online: live?.botSummary?.online ?? live?.portsOnline,
      total: live?.botSummary?.total ?? live?.portsTotal,
      macA: live?.botSummary?.macA,
      macB: live?.botSummary?.macB,
    },
    portfolio: {
      positions: live?.openPositions,
      notional: live?.totalNotional,
      unrealizedPnl: live?.totalUnrealizedPnl,
    },
    prices: Object.fromEntries((live?.whitelistPrices ?? []).map((price) => [price.pair, price.price])),
    risk: {
      level: live?.riskLevel,
      score: live?.riskScore,
      topConcentration: live?.pairConcentration?.[0],
    },
    aiAssessment: live?.aiAssessment,
    error: live?.error,
  }
})

app.get('/glasses/api/prices', async () => {
  const overview = await getTradingReadonlyOverview()
  const live = overview.live
  return {
    ok: Boolean(live && !live.error),
    ts: Date.now(),
    source: live?.baseUrl ?? 'https://console.tianlu2026.org',
    stale: Boolean(live?.error),
    prices: live?.whitelistPrices ?? [],
    error: live?.error,
  }
})

app.get('/glasses/api/positions', async () => {
  const overview = await getTradingReadonlyOverview()
  const live = overview.live
  return {
    ok: Boolean(live && !live.error),
    ts: Date.now(),
    source: live?.baseUrl ?? 'https://console.tianlu2026.org',
    stale: Boolean(live?.error),
    positions: live?.openPositionPairs ?? [],
    totals: {
      positions: live?.openPositions,
      notional: live?.totalNotional,
      unrealizedPnl: live?.totalUnrealizedPnl,
    },
    error: live?.error,
  }
})

app.get('/glasses/api/l5', async () => {
  const overview = await enrichTradingOverviewWithAi(await getTradingReadonlyOverview(), { compact: true })
  const live = overview.live
  return {
    ok: Boolean(live && !live.error),
    ts: Date.now(),
    source: live?.baseUrl ?? 'https://console.tianlu2026.org',
    stale: Boolean(live?.error),
    fundFlow: live?.marketFlow,
    attribution: live?.attribution,
    aiAssessment: live?.aiAssessment,
    error: live?.error,
  }
})

app.get<{ Params: { pair: string } }>('/glasses/api/pair/:pair', async (request) => {
  const overview = await getTradingReadonlyOverview()
  const live = overview.live
  const normalizedPair = normalizePairForResponse(request.params.pair)
  const position = live?.openPositionPairs?.find((item) => normalizePairForResponse(item.pair) === normalizedPair)
  const price = live?.whitelistPrices?.find((item) => normalizePairForResponse(item.pair) === normalizedPair)
  return {
    ok: Boolean(live && !live.error),
    ts: Date.now(),
    source: live?.baseUrl ?? 'https://console.tianlu2026.org',
    stale: Boolean(live?.error),
    pair: normalizedPair,
    price,
    position,
    risk: {
      level: live?.riskLevel,
      score: live?.riskScore,
    },
    error: live?.error,
  }
})

app.get('/glasses/api/alerts', async () => {
  const overview = await getTradingReadonlyOverview()
  const live = overview.live
  return {
    ok: Boolean(live && !live.error),
    ts: Date.now(),
    source: live?.baseUrl ?? 'https://console.tianlu2026.org',
    stale: Boolean(live?.error),
    alerts: live?.alarms ?? [],
    error: live?.error,
  }
})

app.get<{ Reply: OpenClawStatusResponse }>('/openclaw/status', async () => getOpenClawPublicStatus())

app.post<{ Body: AskRequest; Reply: AskResponse }>('/openclaw/ask', async (request) => {
  const tradingOverview = isTradingQuestionText(request.body.question)
    ? await getTradingReadonlyOverview().catch(() => undefined)
    : undefined
  const memory = await searchMemory(request.body.question, { limit: 5 })
  const memoryContext = formatMemoryContext(memory.hits)
  const tradingContext = await buildTradingAskContext(request.body.question)

  const system = [
    '你是 OpenCLAW 连接的 G2 眼镜对话入口。回答必须短，适合眼镜显示和语音朗读。',
    '所有回答必须直接返回给当前页面和眼镜显示；禁止说“稍后发送到 Telegram/电报/TG/手机/第三方平台”，禁止承诺异步转发。',
    '只允许读取、分析、总结和给出建议，不允许执行交易、改仓、下单、平仓或绕过风控。',
    '涉及交易系统时，V6.5 主控规则优先，AI 只做审核员/管理员，机器人只执行既定规则。',
  ].join('\n')
  const user = [
    tradingOverview ? `交易机器人公网实时只读状态：\n${formatTradingOverviewContext(tradingOverview)}` : '',
    tradingContext.context,
    memoryContext ? `可参考记忆：\n${memoryContext}` : '',
    request.body.lastVisionSummary ? `最近画面摘要：${request.body.lastVisionSummary}` : '',
    `用户问题：${request.body.question}`,
  ]
    .filter(Boolean)
    .join('\n')

  const openClaw = await askOpenClaw({
    locale: request.body.locale,
    system,
    user,
  }).catch((error) => {
    app.log.warn({ error }, 'OpenCLAW unavailable in /openclaw/ask')
    return undefined
  })

  if (!openClaw) {
    if (tradingOverview) {
      return {
        answer: formatTradingReadonlyAnswer(tradingOverview),
        provider: 'local:trading-live-readonly',
        createdAt: new Date().toISOString(),
      }
    }

    return {
      answer: 'OpenCLAW 当前未启用或暂时无法连接。你可以先使用普通天禄问答，或检查 OpenCLAW 网关状态。',
      provider: 'openclaw:unavailable',
      createdAt: new Date().toISOString(),
    }
  }

  const answer = sanitizeDirectAnswer(openClaw.answer)
  if (isGenericNoAnswer(answer)) {
    return {
      answer,
      provider: 'openclaw:unavailable',
      createdAt: new Date().toISOString(),
    }
  }

  return {
    answer,
    provider: openClaw.provider,
    createdAt: new Date().toISOString(),
  }
})

app.get<{ Querystring: { q?: string; limit?: string } }>('/memory/search', async (request) => {
  const query = request.query.q?.trim() ?? ''
  const limit = Math.min(Number(request.query.limit ?? 6), 10)
  if (!query) return { query, hits: [] }
  const result = await searchMemory(query, { limit })
  return {
    query: result.query,
    root: result.root,
    hits: result.hits,
  }
})

app.post<{ Body: TtsRequest; Reply: TtsResponse }>('/tts', async (request) => {
  return synthesizeMiniMaxTts(request.body)
})

app.get<{ Reply: AsrStatusResponse }>('/asr/status', async () => getAsrStatus())

app.post<{ Body: TranscribeRequest; Reply: TranscribeResponse }>('/transcribe', async (request) => {
  return transcribeAudio(request.body)
})

function sanitizeDirectAnswer(answer: string): string {
  const original = answer.trim()
  if (!original) return '天禄没有拿到有效回答，请再问一次。'

  const lines = original
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => !/telegram|电报|tg|第三方平台|稍后发送|稍後發送|完成后会传|完成後會傳|传到手机|發到手機|发到手机/i.test(line))

  const cleaned = lines
    .join('\n')
    .replace(/[🦞📱]/g, '')
    .replace(/(完成[后後]|稍后|稍後).{0,18}(Telegram|电报|TG|手机|第三方平台).*/gi, '')
    .replace(/(会|會|将|將).{0,10}(传|傳|发|發|发送|推送).{0,18}(Telegram|电报|TG|手机|第三方平台).*/gi, '')
    .trim()

  if (!cleaned || isInvalidDirectAnswer(cleaned)) {
    return '天禄没有拿到有效回答，请再问一次。'
  }

  return cleaned
}

function isInvalidDirectAnswer(answer: string): boolean {
  return /我已收到问题|收到问题|把结果直接显示|结果直接显示在这里|會把結果直接顯示在這裡|正在分析研究|完成后会传|完成後會傳|telegram|电报|tg|第三方平台/i.test(answer)
}

function isGenericNoAnswer(answer: string): boolean {
  return /天禄没有拿到有效回答|没有拿到有效回答|请再问一次/.test(answer)
}

async function appendRuntimeErrorLog(entry: RuntimeErrorLogEntry): Promise<void> {
  await mkdir(dirname(runtimeErrorLogPath), { recursive: true })
  await appendFile(runtimeErrorLogPath, `${JSON.stringify(entry)}\n`, 'utf8')
}

function sanitizeRuntimeErrorLog(body: RuntimeErrorLogRequest | undefined): RuntimeErrorLogEntry {
  const payload = body && typeof body === 'object' ? body : {}
  const kind = sanitizeRuntimeKind(payload.kind)
  const message = sanitizeRuntimeText(payload.message, 'runtime error', 800)
  const detail = sanitizeRuntimeText(payload.detail, '', 1200)
  const createdAt = sanitizeRuntimeText(payload.createdAt, '', 80)
  const page = sanitizeRuntimePage(payload.page)

  return {
    receivedAt: new Date().toISOString(),
    kind,
    message,
    ...(detail ? { detail } : {}),
    ...(createdAt ? { createdAt } : {}),
    ...(page ? { page } : {}),
    source: 'evenhub-plugin',
  }
}

function sanitizeRuntimeKind(value: unknown): string {
  const kind = typeof value === 'string' ? value : ''
  if (['error', 'unhandledrejection', 'glass-show', 'g2-display'].includes(kind)) return kind
  return 'error'
}

function sanitizeRuntimeText(value: unknown, fallback: string, maxLength: number): string {
  const text = typeof value === 'string' ? value : fallback
  return redactRuntimeText(text).slice(0, maxLength)
}

function sanitizeRuntimePage(value: unknown): string | undefined {
  if (typeof value !== 'string' || !value) return undefined
  return redactRuntimeText(value.replace(/[?#].*$/, '')).slice(0, 300)
}

function redactRuntimeText(text: string): string {
  return text
    .replace(/(sk-[A-Za-z0-9_-]{12,})/g, '<redacted-key>')
    .replace(/(Bearer\s+)[A-Za-z0-9._-]+/gi, '$1<redacted-token>')
    .replace(/([?&](?:token|key|api_key|apikey|password|secret)=)[^&#\s]+/gi, '$1<redacted>')
    .replace(/((?:authorization|api[_-]?key|token|password|secret)\s*[:=]\s*)[^\s,;]+/gi, '$1<redacted>')
    .replace(/data:image\/[a-z0-9.+-]+;base64,[A-Za-z0-9+/=]+/gi, 'data:image/<redacted>;base64,<redacted>')
}

function buildLocalGeneralFallback(question: string): string {
  if (/附近|周边|好玩|好吃|景点|餐厅|南洋|南新|旅游|古迹/.test(question)) {
    return [
      '我现在没有你的实时定位和本地搜索结果，不能准确判断附近地点。',
      '你可以告诉我城市、街区或具体位置，我再按“景点、古迹、美食、路线”给你整理。',
      '也可以说“天禄，看一下这个地方”，我会结合视觉识别结果回答。',
    ].join('\n')
  }

  return [
    '我已收到问题，但实时外部资料不足。',
    '请补充地点、对象或目标，我会直接给出可显示在眼镜上的结论。',
  ].join('\n')
}

function formatTradingReadonlyAnswer(overview: TradingReadonlyOverview | undefined): string {
  const live = overview?.live
  if (!overview || !live) {
    return [
      '实时交易数据暂未返回。',
      '当前不会使用 mock 持仓回答。',
      '请检查控制台公网域名和交易只读接口。',
    ].join('\n')
  }

  if (live.error) {
    return [
      '实时交易数据同步失败。',
      live.error,
      '当前不会使用 mock 持仓回答。',
      '请检查 console.tianlu2026.org 控制台接口。',
    ].join('\n')
  }

  const pairs = live.openPositionPairs ?? []
  const pairText = pairs.length
    ? pairs.slice(0, 8).map(formatTradingPairLine).join('；')
    : '暂无持仓交易对明细'
  const whitelistText = live.whitelistPrices?.length
    ? live.whitelistPrices
        .map((item) => `${item.symbol} ${formatPrice(item.price)}`)
        .join('；')
    : ''
  const concentration = live.pairConcentration?.[0]
  const assessment = buildTradingAssessment(live)
  const botText = live.botSummary
    ? `机器人：${live.botSummary.online ?? live.portsOnline ?? '-'} / ${live.botSummary.total ?? live.portsTotal ?? '-'} 在线；MacA ${live.botSummary.macA ?? '-'}，MacB ${live.botSummary.macB ?? '-'}`
    : `机器人：${live.portsOnline ?? '-'} / ${live.portsTotal ?? '-'} 在线`
  const flowText = live.marketFlow?.summary ? `L5资金流：${live.marketFlow.summary}` : ''
  const attributionText = live.attribution
    ? `归因：样本${live.attribution.sampleCount ?? '-'}，胜率${formatPercent(live.attribution.winRatePct)}，已实现${formatSignedPercent(live.attribution.avgRealizedPnlPct)}`
    : ''
  const aiAssessmentText = live.aiAssessment?.summary ? `${live.aiAssessment.provider}评测：${live.aiAssessment.summary}` : ''
  const aiSuggestions = live.aiAssessment?.suggestions?.length
    ? `建议：${live.aiAssessment.suggestions.slice(0, 3).join('；')}`
    : ''

  return [
    `实时源：${live.baseUrl || 'https://console.tianlu2026.org'}`,
    whitelistText ? `白名单价：${whitelistText}` : '',
    `${botText}；自动驾驶${live.autopilotEnabled ? '开启' : '关闭'}`,
    `持仓：${live.openPositions ?? '-'} 个，交易对：${pairs.length} 个`,
    `名义仓位：${formatAmount(live.totalNotional)}，浮盈亏：${formatSignedAmount(live.totalUnrealizedPnl)}`,
    `风险：${translateRisk(live.riskLevel)}，评分：${live.riskScore ?? '-'}`,
    concentration ? `最高集中：${concentration.pair} ${(concentration.share * 100).toFixed(1)}%` : '',
    `持仓对：${pairText}`,
    flowText,
    attributionText,
    aiAssessmentText,
    aiSuggestions,
    assessment ? `评测：${assessment}` : '',
    live.alarms?.[0]?.message ? `警报：${live.alarms[0].message}` : '未发现严重警报。',
  ]
    .filter(Boolean)
    .join('\n')
}

async function enrichTradingOverviewWithAi(
  overview: TradingReadonlyOverview,
  options: { compact?: boolean } = {},
): Promise<TradingReadonlyOverview> {
  const live = overview.live
  if (!live || live.error) return overview

  const fallback = live.aiAssessment
  const user = [
    '请基于以下交易机器人只读实时数据，给 Even G2 眼镜生成一段中文短评。',
    '要求：只读分析，不下单、不平仓、不改仓；最多 4 条建议；直接给结论；不要 Markdown。',
    `数据源：${live.baseUrl}`,
    `机器人：${live.botSummary?.online ?? live.portsOnline ?? '-'} / ${live.botSummary?.total ?? live.portsTotal ?? '-'} 在线，MacA ${live.botSummary?.macA ?? '-'}，MacB ${live.botSummary?.macB ?? '-'}`,
    `白名单价格：${live.whitelistPrices?.map((item) => `${item.symbol} ${formatPrice(item.price)}`).join('，') || '-'}`,
    `持仓：${live.openPositions ?? '-'} 个，交易对 ${live.openPositionPairs?.length ?? '-'} 个，名义仓位 ${formatAmount(live.totalNotional)}，浮盈亏 ${formatSignedAmount(live.totalUnrealizedPnl)}`,
    `风险：${translateRisk(live.riskLevel)}，评分 ${live.riskScore ?? '-'}`,
    `最高集中：${live.pairConcentration?.[0] ? `${live.pairConcentration[0].pair} ${(live.pairConcentration[0].share * 100).toFixed(1)}%` : '-'}`,
    `L5资金流：${live.marketFlow?.summary ?? '-'}`,
    `归因：样本${live.attribution?.sampleCount ?? '-'}，胜率${formatPercent(live.attribution?.winRatePct)}，已实现${formatSignedPercent(live.attribution?.avgRealizedPnlPct)}`,
  ].join('\n')

  const aiText = await withTimeout(
    askMiniMax({
      system:
        '你是天禄交易系统的只读风险评测助手。你只能基于实时数据做观察、风险提示和复核建议，不能建议执行下单/平仓/改杠杆。回答要短，适合眼镜小屏和语音朗读。',
      user,
    }),
    options.compact ? 8000 : 12000,
  ).catch((error) => {
    app.log.warn({ error }, 'MiniMax trading assessment unavailable; using local assessment')
    return ''
  })

  if (!aiText) return overview

  return {
    ...overview,
    live: {
      ...live,
      aiAssessment: {
        provider: 'MiniMax-M2.7',
        source: 'minimax-realtime-trading-assessment',
        summary: sanitizeDirectAnswer(aiText).slice(0, 420),
        summaryPoints: fallback?.summaryPoints,
        suggestions: fallback?.suggestions,
        createdAt: new Date().toISOString(),
      },
    },
  }
}

function formatTradingOverviewContext(overview: TradingReadonlyOverview): string {
  return [
    `模式：${overview.mode}`,
    `更新时间：${overview.updatedAt}`,
    `实时回答：\n${formatTradingReadonlyAnswer(overview)}`,
  ].join('\n')
}

function formatTradingPairLine(pair: NonNullable<NonNullable<TradingReadonlyOverview['live']>['openPositionPairs']>[number]): string {
  const side = [
    typeof pair.long === 'number' ? `多${pair.long}` : '',
    typeof pair.short === 'number' ? `空${pair.short}` : '',
  ].filter(Boolean).join('/')
  return [
    pair.pair,
    side,
    typeof pair.currentPrice === 'number' ? `现价${formatPrice(pair.currentPrice)}` : '',
    typeof pair.pnl === 'number' ? `PnL${formatSignedAmount(pair.pnl)}` : '',
  ].filter(Boolean).join(' ')
}

function normalizePairForResponse(pair: string | undefined): string {
  const raw = (pair ?? '').trim().toUpperCase().replace(/:USDT$/, '').replace('-', '/')
  if (!raw) return ''
  if (raw.includes('/')) return raw
  if (raw.endsWith('USDT')) return `${raw.slice(0, -4)}/USDT`
  return raw
}

function buildTradingAssessment(live: NonNullable<TradingReadonlyOverview['live']>): string {
  const notes: string[] = []
  const riskScore = Number(live.riskScore ?? 0)
  const top = live.pairConcentration?.[0]
  const pnl = Number(live.totalUnrealizedPnl ?? 0)

  if (/danger|high|危险/i.test(String(live.riskLevel ?? '')) || riskScore >= 80) {
    notes.push('风险偏高，先处理警报并降低新增暴露。')
  } else if (/warning|warn|警/i.test(String(live.riskLevel ?? '')) || riskScore >= 55) {
    notes.push('风险中等，重点看集中度、亏损仓和止损有效性。')
  } else {
    notes.push('整体风险正常，适合继续只读观察。')
  }
  if (top && top.share >= 0.3) notes.push(`${top.pair} 集中度偏高。`)
  if (pnl < 0) notes.push('当前总浮亏，优先复核亏损最大的交易对。')
  return notes.join(' ')
}

function translateRisk(level: string | undefined): string {
  if (!level) return '-'
  if (/normal|low/i.test(level)) return '正常'
  if (/warning|medium|warn/i.test(level)) return '预警'
  if (/danger|high/i.test(level)) return '危险'
  return level
}

function formatAmount(value: number | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '-'
  return value.toFixed(2)
}

function formatSignedAmount(value: number | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '-'
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}`
}

function formatPrice(value: number | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '-'
  if (value >= 1000) return value.toFixed(1)
  if (value >= 10) return value.toFixed(2)
  return value.toFixed(5)
}

function formatPercent(value: number | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '-'
  return `${value.toFixed(1)}%`
}

function formatSignedPercent(value: number | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '-'
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
}

app.setErrorHandler((error, _request, reply) => {
  app.log.error(error)
  reply.status(500).send({
    error: 'internal_error',
    detail: toUserFacingError(error),
  })
})

await app.listen({ port, host: '0.0.0.0' })

function toUserFacingError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error)

  if (message.includes('body is too large')) return '照片太大，请重新拍照，系统会自动压缩后上传。'
  if (message.includes('input image sensitive') || message.includes('new_sensitive')) {
    return '图片被视觉接口安全策略拒绝，请换一个普通物体或环境重新拍照。'
  }
  if (message.includes('MiniMax VLM failed')) return '真实视觉识别接口暂时失败，请重新拍照或稍后再试。'
  if (message.includes('MiniMax chat failed')) return 'MiniMax 文本接口暂时失败，请稍后再试。'

  return message
}

function isSessionTokenValid(token: string): boolean {
  const expected = process.env.G2_BRIDGE_SESSION_TOKEN
  if (!expected) return true
  return token === expected
}

function isTradingQuestionText(text: string): boolean {
  return /交易机器人|机器人运行|机器人状态|交易状态|运行如何|状态如何|今日收益|今天收益|收益率|盈亏|持仓|仓位|挂单|白名单|币价|现价|行情|PnL|pnl|风险|风控|策略|开仓|平仓|止盈|止损|BTC|ETH|SOL|BNB|DOGE|OKX|Binance|Gate/i.test(text)
}

function withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`timeout after ${timeoutMs}ms`)), timeoutMs)
    promise.then(
      (value) => {
        clearTimeout(timer)
        resolve(value)
      },
      (error) => {
        clearTimeout(timer)
        reject(error)
      },
    )
  })
}
