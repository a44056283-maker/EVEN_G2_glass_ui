export type LocaleCode = 'zh-CN' | 'en-US' | 'ja-JP' | string

export interface VisionRequest {
  imageBase64: string
  mimeType?: 'image/jpeg' | 'image/png' | string
  prompt?: string
  locale?: LocaleCode
  capturedAt?: string
  locationContext?: string
  recentVisionContext?: string
}

export interface VisionResponse {
  description: string
  answer: string
  provider: string
  createdAt: string
  source?: string
  elapsedMs?: number
  confidence?: number
  needsClarification?: boolean
}

export interface AskRequest {
  question: string
  lastVisionSummary?: string
  locale?: LocaleCode
  capturedAt?: string
  locationContext?: string
}

export interface AskResponse {
  answer: string
  provider: string
  createdAt: string
}

export interface OpenClawStatusResponse {
  enabled: boolean
  baseUrl: string
  model: string
  agent: string
}

export interface TtsRequest {
  text: string
  voiceId?: string
  locale?: LocaleCode
}

export interface TtsResponse {
  audioBase64?: string
  mimeType?: string
  fallbackText?: string
  provider: string
}

export interface TranscribeRequest {
  audioBase64: string
  sampleRate?: number
  channels?: number
  format?: 'pcm_s16le' | string
  mimeType?: string
  durationMs?: number
  source?: 'g2' | 'phone' | 'headset' | string
  locale?: LocaleCode
}

export interface TranscribeResponse {
  text: string
  provider: string
}

export interface AsrStatusResponse {
  available: boolean
  provider: string
  reason?: 'not-configured' | 'missing-key' | 'stub'
  message: string
}

export interface TradingReadonlyOverview {
  enabled: boolean
  readOnly: true
  mode: 'memory-only' | 'live-readonly'
  safetyRules: string[]
  supportedQueries: string[]
  live?: {
    baseUrl: string
    dataSources?: Array<{
      baseUrl: string
      ok: boolean
      openPositions?: number
      pairCount?: number
      endpoint?: string
      source?: string
      error?: string
    }>
    portsOnline?: number
    portsTotal?: number
    autopilotEnabled?: boolean
    riskLevel?: string
    riskScore?: number
    openPositions?: number
    totalNotional?: number
    totalUnrealizedPnl?: number
    whitelistPrices?: Array<{
      symbol: string
      pair: string
      price: number
      source: string
      updatedAt?: string
      status?: string
      freshness?: 'live' | 'fresh' | 'stale' | 'fallback'
      sourceLayer?: string
    }>
    openPositionPairs?: Array<{
      pair: string
      count?: number
      long?: number
      short?: number
      pnl?: number
      notional?: number
      share?: number
      currentPrice?: number
      maxLeverage?: number
      source?: string
    }>
    botSummary?: {
      online?: number
      total?: number
      macA?: string
      macB?: string
    }
    marketFlow?: {
      source?: string
      summary?: string
      pairCount?: number
    }
    attribution?: {
      source?: string
      sampleCount?: number
      winRatePct?: number
      avgRealizedPnlPct?: number
      avgUnrealizedPnlPct?: number
    }
    aiAssessment?: {
      provider: string
      summary: string
      suggestions?: string[]
      summaryPoints?: string[]
      source?: string
      createdAt?: string
    }
    pairConcentration?: Array<{
      pair: string
      share: number
      pnl?: number
      notional?: number
      count?: number
    }>
    alarms?: Array<{
      level?: string
      message?: string
      action?: string
    }>
    checkedAt?: string
    error?: string
  }
  memoryHits: Array<{
    path: string
    title: string
    snippet: string
    score: number
    updatedAt?: string
  }>
  updatedAt: string
}

export interface ApiErrorBody {
  error: string
  detail?: string
}
