import type { TradingReadonlyOverview } from '@g2vva/shared'

export interface TradingAskContext {
  isTradingRelated: boolean
  mode: TradingReadonlyOverview['mode']
  context: string
  hits: []
}

interface PortStatus {
  port?: number
  name?: string
  status?: string
  online?: boolean
}

interface RealtimePricesResponse {
  ok?: boolean
  ts?: number
  prices?: Record<string, {
    price?: number
    change_24h?: number
    ts?: number
  }>
}

interface DashboardPositionsResponse {
  timestamp?: number
  summary?: {
    total_balance?: number
    total_profit?: number
    active_ports?: number
    total_positions?: number
    open_trades?: number
  }
  ports?: Array<{
    port?: number
    name?: string
    online?: boolean
    autopilot?: boolean
    balance?: number
    profit?: number
    profit_percent?: number
    positions?: number
    trades?: DashboardTrade[]
  }>
}

interface MonitorPositionsResponse {
  positions?: DashboardTrade[]
}

interface DashboardTrade {
  _raw?: DashboardTrade
  pair?: string
  is_open?: boolean
  is_short?: boolean
  current_rate?: number | string
  open_rate?: number | string
  open_trade_value?: number | string
  profit_abs?: number | string
  total_profit_abs?: number | string
  profit_pct?: number | string
  profit_ratio?: number | string
  leverage?: number | string
  has_open_orders?: boolean
  port?: number
  _port?: number
  port_name?: string
  _name?: string
  exchange?: string
  amount?: number | string
  stake_amount?: number | string
}

interface FundFlowV2Response {
  pair_count?: number
  snapshot_count?: number
  summary?: unknown
  pairs?: Record<string, {
    summary?: {
      direction?: string
      avg_confidence?: number
      avg_ohlcv_netflow?: number
      avg_taker_delta_ratio?: number
      avg_book_imbalance?: number
    }
  }>
}

interface AttributionResponse {
  sample_count?: number
  trade_outcome_attribution?: {
    matched_trade_count?: number
    win_rate_pct?: number
    avg_realized_pnl_pct?: number
    avg_unrealized_pnl_pct?: number
    avg_slippage_pct?: number
  }
}

type TradingLiveOverview = NonNullable<TradingReadonlyOverview['live']>
type OpenPositionPair = NonNullable<TradingLiveOverview['openPositionPairs']>[number]
type WhitelistPrice = NonNullable<TradingLiveOverview['whitelistPrices']>[number]

const tradingIntentPattern =
  /交易|币|行情|价格|现价|白名单|仓位|持仓|开仓|平仓|止损|止盈|盈亏|浮盈|浮亏|pnl|收益|风险|风控|集中度|自动驾驶|机器人|端口|9090|9091|9092|9093|9094|9095|9096|9097|9099|8081|8082|8083|8084|v6\.?5|v6\.?6|策略|btc|eth|sol|bnb|doge|okx|binance|gate|openclaw/i

const safetyRules = [
  '只读查看，不下单',
  '只读查看，不平仓',
  '只读查看，不改仓位',
  '只读查看，不推送机器人命令',
]

const supportedQueries = [
  'V6.5/V6.6 交易规则解释',
  '机器人在线状态历史记录',
  '持仓与盈亏历史摘要',
  '白名单币种和外部信号记录',
  '风险、集中度、自动驾驶预检记录',
]

export function isTradingQuestion(question: string): boolean {
  return tradingIntentPattern.test(question)
}

export async function buildTradingAskContext(question: string): Promise<TradingAskContext> {
  if (!isTradingQuestion(question)) {
    return {
      isTradingRelated: false,
      mode: getTradingMode(),
      context: '',
      hits: [],
    }
  }

  const live = await fetchTradingLiveOverview()
  const liveContext = formatLiveTradingContext(live)

  return {
    isTradingRelated: true,
    mode: getTradingMode(),
    context: [
      '交易系统只读上下文：',
      '硬边界：G2 只能查看、总结和风险提示；不得下单、平仓、改仓、改止损止盈或推送机器人命令。',
      liveContext,
    ]
      .filter(Boolean)
      .join('\n'),
    hits: [],
  }
}

export async function getTradingReadonlyOverview(): Promise<TradingReadonlyOverview> {
  const live = await fetchTradingLiveOverview()

  return {
    enabled: process.env.TRADING_READONLY_ENABLED === 'true',
    readOnly: true,
    mode: getTradingMode(),
    safetyRules,
    supportedQueries,
    live,
    memoryHits: [],
    updatedAt: new Date().toISOString(),
  }
}

function getTradingMode(): TradingReadonlyOverview['mode'] {
  return process.env.TRADING_READONLY_ENABLED === 'true' ? 'live-readonly' : 'memory-only'
}

async function fetchTradingLiveOverview(): Promise<TradingReadonlyOverview['live']> {
  const baseUrls = getTradingBaseUrls()
  if (process.env.TRADING_READONLY_ENABLED !== 'true' || baseUrls.length === 0) {
    return undefined
  }

  const snapshots = await Promise.all(baseUrls.map((baseUrl) => fetchTradingSourceSnapshot(baseUrl)))
  const okSnapshots = snapshots.filter((snapshot) => !snapshot.error)
  if (okSnapshots.length === 0) {
    return {
      baseUrl: baseUrls.map(maskUrl).join(', '),
      dataSources: snapshots.map((snapshot) => snapshot.dataSource),
      error: snapshots.map((snapshot) => `${snapshot.dataSource.baseUrl}: ${snapshot.dataSource.error}`).join('；'),
    }
  }

  return mergeTradingSourceSnapshots(okSnapshots, snapshots.map((snapshot) => snapshot.dataSource))
}

async function fetchTradingSourceSnapshot(baseUrl: string): Promise<{
  dataSource: NonNullable<TradingLiveOverview['dataSources']>[number]
  live?: TradingLiveOverview
  error?: string
}> {
  try {
    const whitelistSymbols = getWhitelistSymbols()
    const [ports, dashboard, realtimePrices, monitorPositions, fundFlow, attribution] = await Promise.all([
      fetchJson<PortStatus[]>(`${baseUrl}/api/ports_status`),
      fetchJson<DashboardPositionsResponse>(`${baseUrl}/api/dashboard/positions`),
      fetchJson<RealtimePricesResponse>(`${baseUrl}/api/prices/realtime`),
      fetchJson<MonitorPositionsResponse>(`${baseUrl}/api/monitor/positions`).catch(() => undefined),
      fetchJson<FundFlowV2Response>(`${baseUrl}/api/l5/fund_flow_v2`).catch(() => undefined),
      fetchJson<AttributionResponse>(`${baseUrl}/api/l5/daily_attribution?hours=24`).catch(() => undefined),
    ])
    const onlinePorts = ports.filter((port) => isPortOnline(port))
    const sourceName = maskUrl(baseUrl)
    const rawTrades = collectOpenTrades(dashboard, monitorPositions)
    const openPositionPairs = buildOpenPositionPairsFromTrades(rawTrades, sourceName)
    const whitelistPrices = buildWhitelistPricesFromRealtime(whitelistSymbols, realtimePrices)
    const totalNotional = openPositionPairs.reduce((sum, pair) => sum + Number(pair.notional ?? 0), 0)
    const totalUnrealizedPnl = openPositionPairs.reduce((sum, pair) => sum + Number(pair.pnl ?? 0), 0)
    const openPositions = Number(dashboard.summary?.open_trades ?? dashboard.summary?.total_positions ?? rawTrades.length)
    const riskSummary = buildRiskSummary(openPositionPairs, totalUnrealizedPnl)
    const live: TradingLiveOverview = {
      baseUrl: sourceName,
      dataSources: [{
        baseUrl: sourceName,
        ok: true,
        endpoint: '/api/dashboard/positions',
        source: '9099-public-console',
        openPositions,
        pairCount: openPositionPairs.length,
      }],
      portsOnline: onlinePorts.length,
      portsTotal: ports.length,
      autopilotEnabled: dashboard.ports?.some((port) => port.autopilot) ?? false,
      riskLevel: riskSummary.level,
      riskScore: riskSummary.score,
      openPositions,
      totalNotional,
      totalUnrealizedPnl,
      whitelistPrices,
      openPositionPairs,
      pairConcentration: buildPairConcentration(openPositionPairs),
      alarms: riskSummary.alarms,
      botSummary: buildBotSummary(ports),
      marketFlow: buildMarketFlowSummary(fundFlow),
      attribution: buildAttributionSummary(attribution),
      aiAssessment: buildLocalTradingAiAssessment({
        openPositions,
        totalNotional,
        totalUnrealizedPnl,
        riskLevel: riskSummary.level,
        riskScore: riskSummary.score,
        pairs: openPositionPairs,
        marketFlow: buildMarketFlowSummary(fundFlow),
        attribution: buildAttributionSummary(attribution),
      }),
      checkedAt: dashboard.timestamp ? new Date(Number(dashboard.timestamp) * 1000).toISOString() : new Date().toISOString(),
    }

    return {
      dataSource: live.dataSources![0],
      live,
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return {
      dataSource: {
        baseUrl: maskUrl(baseUrl),
        ok: false,
        error: message,
      },
      error: message,
    }
  }
}

function mergeTradingSourceSnapshots(
  snapshots: Array<{ live?: TradingLiveOverview }>,
  dataSources: NonNullable<TradingLiveOverview['dataSources']>,
): TradingLiveOverview {
  const lives = snapshots.map((snapshot) => snapshot.live).filter((live): live is TradingLiveOverview => Boolean(live))
  const pairs = mergeOpenPositionPairs(lives.flatMap((live) => live.openPositionPairs ?? []))
  const totalNotional = pairs.reduce((sum, pair) => sum + Number(pair.notional ?? 0), 0)
  const totalUnrealizedPnl = pairs.reduce((sum, pair) => sum + Number(pair.pnl ?? 0), 0)
  const openPositions = pairs.reduce((sum, pair) => sum + Number(pair.count ?? 0), 0)

  return {
    baseUrl: dataSources.map((source) => source.baseUrl).join(', '),
    dataSources,
    portsOnline: lives.reduce((sum, live) => sum + Number(live.portsOnline ?? 0), 0),
    portsTotal: lives.reduce((sum, live) => sum + Number(live.portsTotal ?? 0), 0),
    autopilotEnabled: lives.some((live) => live.autopilotEnabled),
    riskLevel: pickWorstRiskLevel(lives.map((live) => live.riskLevel)),
    riskScore: Math.max(...lives.map((live) => Number(live.riskScore ?? 0))),
    openPositions,
    totalNotional,
    totalUnrealizedPnl,
    whitelistPrices: mergeWhitelistPrices(lives.flatMap((live) => live.whitelistPrices ?? [])),
	    openPositionPairs: pairs,
	    pairConcentration: buildPairConcentration(pairs),
	    alarms: lives.flatMap((live) => live.alarms ?? []).slice(0, 3),
	    botSummary: lives[0]?.botSummary,
	    marketFlow: lives[0]?.marketFlow,
	    attribution: lives[0]?.attribution,
	    aiAssessment: buildLocalTradingAiAssessment({
	      openPositions,
	      totalNotional,
	      totalUnrealizedPnl,
	      riskLevel: pickWorstRiskLevel(lives.map((live) => live.riskLevel)),
	      riskScore: Math.max(...lives.map((live) => Number(live.riskScore ?? 0))),
	      pairs,
	      marketFlow: lives[0]?.marketFlow,
	      attribution: lives[0]?.attribution,
	    }),
	    checkedAt: lives.map((live) => live.checkedAt).filter(Boolean).sort().at(-1),
	  }
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, {
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    throw new Error(`${url} ${response.status}`)
  }
  return response.json() as Promise<T>
}

function formatLiveTradingContext(live: TradingReadonlyOverview['live']): string {
  if (!live) return ''
  if (live.error) return `实时交易只读接口暂不可用：${live.error}`

  const pairs = live.pairConcentration
    ?.map((item) => `${item.pair} ${(item.share * 100).toFixed(1)}%，PnL ${formatNumber(item.pnl)}`)
    .join('；')
  const prices = live.whitelistPrices
    ?.map((item) => `${item.symbol} ${formatPrice(item.price)}`)
    .join('；')
  const alarm = live.alarms?.[0]?.message

  return [
    '实时交易只读数据：',
    prices ? `白名单价格：${prices}` : '',
    `机器人在线：${live.portsOnline ?? '-'} / ${live.portsTotal ?? '-'}`,
    `自动驾驶：${live.autopilotEnabled ? '开启' : '关闭'}`,
    `风险：${live.riskLevel ?? '-'}，分数 ${live.riskScore ?? '-'}`,
    `持仓：${live.openPositions ?? '-'} 个，名义仓位 ${formatNumber(live.totalNotional)}，浮动盈亏 ${formatNumber(live.totalUnrealizedPnl)}`,
    live.openPositionPairs?.length ? `持仓交易对：${formatOpenPositionPairs(live.openPositionPairs)}` : '',
    pairs ? `集中度：${pairs}` : '',
    alarm ? `主要警报：${alarm}` : '',
  ]
    .filter(Boolean)
    .join('\n')
}

function formatOpenPositionPairs(pairs: NonNullable<NonNullable<TradingReadonlyOverview['live']>['openPositionPairs']>): string {
  return pairs
    .map((item) => {
      const side = [
        typeof item.long === 'number' ? `多${item.long}` : '',
        typeof item.short === 'number' ? `空${item.short}` : '',
      ]
        .filter(Boolean)
        .join('/')
      const pnl = typeof item.pnl === 'number' ? `PnL ${formatNumber(item.pnl)}` : ''
      return `${item.pair}${side ? ` ${side}` : ''}${pnl ? ` ${pnl}` : ''}`
    })
    .join('；')
}

function formatNumber(value: number | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '-'
  return value.toFixed(2)
}

function formatPrice(value: number): string {
  if (!Number.isFinite(value)) return '-'
  if (value >= 1000) return value.toFixed(1)
  if (value >= 10) return value.toFixed(2)
  return value.toFixed(5)
}

function getWhitelistSymbols(): string[] {
  const raw = process.env.TRADING_ALLOWED_SYMBOLS ?? 'BTC,ETH,SOL,BNB,DOGE'
  return raw
    .split(',')
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean)
}

function getTradingBaseUrls(): string[] {
  const raw = process.env.TRADING_BASE_URLS ?? process.env.TRADING_BASE_URL ?? 'https://console.tianlu2026.org'
  return Array.from(
    new Set(
      raw
        .split(',')
        .map((item) => item.trim().replace(/\/+$/, ''))
        .filter(Boolean),
    ),
  )
}

function mergeOpenPositionPairs(pairs: OpenPositionPair[]): OpenPositionPair[] {
  const mode = (process.env.TRADING_SOURCE_MERGE_MODE ?? 'max').toLowerCase()
  const byPair = new Map<string, OpenPositionPair>()

  for (const pair of pairs) {
    const normalized = normalizePair(pair.pair)
    if (!normalized) continue
    const previous = byPair.get(normalized)
    if (!previous) {
      byPair.set(normalized, { ...pair, pair: normalized })
      continue
    }

    if (mode === 'sum') {
      byPair.set(normalized, {
        ...previous,
        pair: normalized,
        count: Number(previous.count ?? 0) + Number(pair.count ?? 0),
        long: Number(previous.long ?? 0) + Number(pair.long ?? 0),
        short: Number(previous.short ?? 0) + Number(pair.short ?? 0),
        pnl: Number(previous.pnl ?? 0) + Number(pair.pnl ?? 0),
        notional: Number(previous.notional ?? 0) + Number(pair.notional ?? 0),
        currentPrice: pair.currentPrice ?? previous.currentPrice,
        maxLeverage: Math.max(Number(previous.maxLeverage ?? 0), Number(pair.maxLeverage ?? 0)) || undefined,
        source: [previous.source, pair.source].filter(Boolean).join('+'),
      })
      continue
    }

    const previousWeight = Number(previous.count ?? 0) || Number(previous.notional ?? 0)
    const nextWeight = Number(pair.count ?? 0) || Number(pair.notional ?? 0)
    if (nextWeight > previousWeight) byPair.set(normalized, { ...pair, pair: normalized })
  }

  const totalNotional = Array.from(byPair.values()).reduce((sum, pair) => sum + Number(pair.notional ?? 0), 0)
  return Array.from(byPair.values())
    .map((pair) => ({
      ...pair,
      share: totalNotional > 0 && typeof pair.notional === 'number' ? pair.notional / totalNotional : pair.share,
    }))
    .sort((a, b) => Number(b.share ?? 0) - Number(a.share ?? 0))
}

function mergeWhitelistPrices(prices: WhitelistPrice[]): WhitelistPrice[] {
  const bySymbol = new Map<string, WhitelistPrice>()
  for (const price of prices) {
    const symbol = price.symbol.toUpperCase()
    const previous = bySymbol.get(symbol)
    if (!previous) {
      bySymbol.set(symbol, { ...price, symbol })
      continue
    }

    if (!previous.updatedAt || (price.updatedAt && price.updatedAt > previous.updatedAt)) {
      bySymbol.set(symbol, { ...price, symbol })
    }
  }
  return Array.from(bySymbol.values()).sort((a, b) => a.symbol.localeCompare(b.symbol))
}

function buildPairConcentration(pairs: OpenPositionPair[]): NonNullable<TradingLiveOverview['pairConcentration']> {
  const totalNotional = pairs.reduce((sum, pair) => sum + Number(pair.notional ?? 0), 0)
  return pairs
    .map((pair) => ({
      pair: pair.pair,
      share: totalNotional > 0 && typeof pair.notional === 'number' ? pair.notional / totalNotional : Number(pair.share ?? 0),
      pnl: pair.pnl,
      notional: pair.notional,
      count: pair.count,
    }))
    .sort((a, b) => b.share - a.share)
    .slice(0, 6)
}

function pickWorstRiskLevel(levels: Array<string | undefined>): string | undefined {
  const rank: Record<string, number> = { danger: 3, high: 3, warning: 2, medium: 2, normal: 1, low: 1 }
  return levels
    .filter((level): level is string => Boolean(level))
    .sort((a, b) => Number(rank[b.toLowerCase()] ?? 0) - Number(rank[a.toLowerCase()] ?? 0))[0]
}

function collectOpenTrades(dashboard: DashboardPositionsResponse, monitorPositions: MonitorPositionsResponse | undefined): DashboardTrade[] {
  const fromDashboard = (dashboard.ports ?? []).flatMap((port) =>
    (port.trades ?? [])
      .filter((trade) => trade.is_open !== false)
      .map((trade) => ({
        ...trade,
        port: trade.port ?? port.port,
        port_name: trade.port_name ?? port.name,
      })),
  )
  const fromMonitor = (monitorPositions?.positions ?? [])
    .filter((position) => position.is_open !== false)
    .map((position) => ({
      ...(position._raw ?? {}),
      ...position,
      pair: position.pair ?? position._raw?.pair,
      is_open: position.is_open ?? position._raw?.is_open,
      is_short: position.is_short ?? position._raw?.is_short,
      current_rate: position.current_rate ?? position._raw?.current_rate,
      open_rate: position.open_rate ?? position._raw?.open_rate,
      open_trade_value: position.open_trade_value ?? position._raw?.open_trade_value,
      profit_abs: position.profit_abs ?? position._raw?.profit_abs,
      total_profit_abs: position.total_profit_abs ?? position._raw?.total_profit_abs,
      leverage: position.leverage ?? position._raw?.leverage,
      amount: position.amount ?? position._raw?.amount,
      stake_amount: position.stake_amount ?? position._raw?.stake_amount,
      port: position.port ?? position._port,
      port_name: position.port_name ?? position._name,
    }))

  return fromMonitor.length > 0 ? fromMonitor : fromDashboard
}

function buildOpenPositionPairsFromTrades(trades: DashboardTrade[], source?: string): OpenPositionPair[] {
  const byPair = new Map<string, {
    pair: string
    count: number
    long: number
    short: number
    pnl: number
    notional: number
    currentPrice?: number
    maxLeverage?: number
    source?: string
  }>()

  for (const trade of trades) {
    const pair = normalizePair(trade.pair)
    if (!pair) continue
    const previous = byPair.get(pair) ?? {
      pair,
      count: 0,
      long: 0,
      short: 0,
      pnl: 0,
      notional: 0,
      source,
    }
    const notional = pickFirstFinite(
      trade.open_trade_value,
      multiplyFinite(trade.current_rate, trade.amount, trade.leverage),
      multiplyFinite(trade.open_rate, trade.amount, trade.leverage),
      trade.stake_amount,
    )
    const pnl = pickFirstFinite(trade.total_profit_abs, trade.profit_abs)
    const leverage = Number(trade.leverage)
    previous.count += 1
    if (trade.is_short) previous.short += 1
    else previous.long += 1
    if (typeof pnl === 'number') previous.pnl += pnl
    if (typeof notional === 'number') previous.notional += notional
    const price = pickFirstFinite(trade.current_rate, trade.open_rate)
    if (typeof price === 'number') previous.currentPrice = price
    if (Number.isFinite(leverage) && leverage > 0) {
      previous.maxLeverage = Math.max(previous.maxLeverage ?? 0, leverage)
    }
    byPair.set(pair, previous)
  }

  const totalNotional = Array.from(byPair.values()).reduce((sum, pair) => sum + pair.notional, 0)
  return Array.from(byPair.values())
    .map((pair) => ({
      ...pair,
      share: totalNotional > 0 ? pair.notional / totalNotional : 0,
    }))
    .sort((a, b) => Number(b.share ?? 0) - Number(a.share ?? 0))
}

function buildWhitelistPricesFromRealtime(
  symbols: string[],
  realtime: RealtimePricesResponse,
): WhitelistPrice[] {
  const prices = realtime.prices ?? {}
  const rows: WhitelistPrice[] = []
  for (const symbol of symbols) {
    const raw = prices[symbol.toLowerCase()] ?? prices[symbol.toUpperCase()] ?? prices[`${symbol}/USDT`] ?? prices[`${symbol}USDT`]
    const price = Number(raw?.price)
    if (!Number.isFinite(price) || price <= 0) continue
    rows.push({
      symbol,
      pair: `${symbol}/USDT`,
      price,
      source: '/api/prices/realtime',
      sourceLayer: '9099-realtime',
      status: realtime.ok === false ? 'error' : 'ok',
      freshness: 'live',
      updatedAt: raw?.ts ? new Date(Number(raw.ts) * 1000).toISOString() : realtime.ts ? new Date(Number(realtime.ts) * 1000).toISOString() : new Date().toISOString(),
    })
  }
  return rows.sort((a, b) => a.symbol.localeCompare(b.symbol))
}

function buildRiskSummary(pairs: OpenPositionPair[], totalUnrealizedPnl: number): {
  level: string
  score: number
  alarms: NonNullable<TradingLiveOverview['alarms']>
} {
  const top = buildPairConcentration(pairs)[0]
  let score = 0
  const alarms: NonNullable<TradingLiveOverview['alarms']> = []
  if (top?.share && top.share >= 0.45) {
    score += 35
    alarms.push({ level: 'warning', message: `${top.pair} 集中度 ${(top.share * 100).toFixed(1)}% 偏高` })
  } else if (top?.share && top.share >= 0.3) {
    score += 18
  }
  if (totalUnrealizedPnl < 0) score += Math.min(30, Math.abs(totalUnrealizedPnl) / 10)
  const level = score >= 70 ? 'danger' : score >= 45 ? 'warning' : 'normal'
  if (totalUnrealizedPnl < 0) {
    alarms.push({ level: score >= 45 ? 'warning' : 'info', message: `当前总浮亏 ${formatNumber(totalUnrealizedPnl)}` })
  }
  return { level, score: Number(score.toFixed(1)), alarms: alarms.slice(0, 3) }
}

function buildBotSummary(ports: PortStatus[]): NonNullable<TradingLiveOverview['botSummary']> {
  const online = ports.filter((port) => isPortOnline(port)).length
  const macB = ports.filter((port) => Number(port.port) >= 8081 && Number(port.port) <= 8084)
  const macA = ports.filter((port) => Number(port.port) >= 9090 && Number(port.port) <= 9097)
  return {
    online,
    total: ports.length,
    macA: `${macA.filter(isPortOnline).length}/${macA.length}`,
    macB: `${macB.filter(isPortOnline).length}/${macB.length}`,
  }
}

function buildMarketFlowSummary(flow: FundFlowV2Response | undefined): TradingLiveOverview['marketFlow'] {
  if (!flow) return undefined
  const pairSummaries = Object.entries(flow.pairs ?? {})
    .slice(0, 5)
    .map(([pair, value]) => {
      const summary = value.summary
      return `${normalizePair(pair)} ${summary?.direction ?? '-'} 置信${formatNumber(summary?.avg_confidence)}`
    })
  return {
    source: '/api/l5/fund_flow_v2',
    pairCount: flow.pair_count,
    summary: pairSummaries.join('；'),
  }
}

function buildAttributionSummary(attribution: AttributionResponse | undefined): TradingLiveOverview['attribution'] {
  if (!attribution) return undefined
  const raw = attribution.trade_outcome_attribution
  return {
    source: '/api/l5/daily_attribution?hours=24',
    sampleCount: attribution.sample_count ?? raw?.matched_trade_count,
    winRatePct: raw?.win_rate_pct,
    avgRealizedPnlPct: raw?.avg_realized_pnl_pct,
    avgUnrealizedPnlPct: raw?.avg_unrealized_pnl_pct,
  }
}

function buildLocalTradingAiAssessment(input: {
  openPositions: number
  totalNotional: number
  totalUnrealizedPnl: number
  riskLevel?: string
  riskScore?: number
  pairs: OpenPositionPair[]
  marketFlow?: TradingLiveOverview['marketFlow']
  attribution?: TradingLiveOverview['attribution']
}): NonNullable<TradingLiveOverview['aiAssessment']> {
  const top = buildPairConcentration(input.pairs)[0]
  const riskScore = Number(input.riskScore ?? 0)
  const pnl = Number(input.totalUnrealizedPnl ?? 0)
  const suggestions: string[] = []

  if (riskScore >= 70 || /danger|high|危险/i.test(String(input.riskLevel ?? ''))) {
    suggestions.push('风险偏高，先暂停新增暴露，优先检查亏损仓和集中仓。')
  } else if (riskScore >= 45 || /warning|medium|warn/i.test(String(input.riskLevel ?? ''))) {
    suggestions.push('风险中等，优先观察集中度、亏损仓和资金流背离。')
  } else {
    suggestions.push('整体风险正常，可继续只读观察，不建议人工追单。')
  }

  if (top?.share && top.share >= 0.3) {
    suggestions.push(`${top.pair} 占比 ${(top.share * 100).toFixed(1)}%，需要重点盯集中风险。`)
  }
  if (pnl < 0) suggestions.push('当前组合为浮亏，先复核亏损最大的交易对。')
  if (input.attribution?.winRatePct !== undefined && input.attribution.winRatePct < 40) {
    suggestions.push(`近24小时归因胜率 ${input.attribution.winRatePct.toFixed(1)}%，不宜放大仓位。`)
  }
  if (input.marketFlow?.summary) {
    suggestions.push('结合 L5 资金流分歧，优先等确认信号。')
  }

  return {
    provider: 'local-rule-v1',
    source: 'console-realtime-local-assessment',
    summary: [
      `组合持仓 ${input.openPositions} 个，名义 ${formatNumber(input.totalNotional)}，浮盈亏 ${formatNumber(input.totalUnrealizedPnl)}。`,
      suggestions[0] ?? '保持只读观察。',
    ].join(' '),
    summaryPoints: buildSixPointTradingSummary(input),
    suggestions: suggestions.slice(0, 4),
    createdAt: new Date().toISOString(),
  }
}

function buildSixPointTradingSummary(input: {
  openPositions: number
  totalNotional: number
  totalUnrealizedPnl: number
  riskLevel?: string
  riskScore?: number
  pairs: OpenPositionPair[]
  marketFlow?: TradingLiveOverview['marketFlow']
  attribution?: TradingLiveOverview['attribution']
}): string[] {
  const top = buildPairConcentration(input.pairs)[0]
  const pairs = input.pairs.slice(0, 5).map((pair) => pair.pair).join(' / ')
  return [
    `持仓规模：${input.openPositions} 个，名义 ${formatNumber(input.totalNotional)}。`,
    `组合盈亏：当前浮盈亏 ${formatNumber(input.totalUnrealizedPnl)}。`,
    `风险评分：${input.riskLevel ?? '-'} ${input.riskScore ?? '-'} 分。`,
    top ? `集中度：${top.pair} ${(top.share * 100).toFixed(1)}%，仓位 ${formatNumber(top.notional)}。` : '集中度：暂无有效持仓集中度。',
    pairs ? `主要交易对：${pairs}。` : '主要交易对：暂无。',
    input.marketFlow?.summary ? `L5资金流：${input.marketFlow.summary}。` : 'L5资金流：暂无实时摘要。',
    input.attribution
      ? `订单归因：样本 ${input.attribution.sampleCount ?? '-'}，胜率 ${formatNumber(input.attribution.winRatePct)}%。`
      : '订单归因：暂无实时归因。',
  ].slice(0, 7)
}

function isPortOnline(port: PortStatus): boolean {
  return port.online === true || String(port.status ?? '').toLowerCase() === 'online'
}

function multiplyFinite(...values: Array<unknown>): number | undefined {
  const numbers = values.map((value) => Number(value))
  if (numbers.some((value) => !Number.isFinite(value))) return undefined
  return numbers.reduce<number>((product, value) => product * value, 1)
}

function pickFirstFinite(...values: Array<unknown>): number | undefined {
  for (const value of values) {
    const number = Number(value)
    if (Number.isFinite(number)) return number
  }
  return undefined
}

function normalizePair(pair: string | undefined): string {
  const raw = (pair ?? '').trim().toUpperCase().replace(/:USDT$/, '').replace('-', '/')
  if (!raw) return ''
  if (raw.includes('/')) return raw
  if (raw.endsWith('USDT')) return `${raw.slice(0, -4)}/USDT`
  return raw
}

function maskUrl(url: string): string {
  try {
    return new URL(url).origin
  } catch {
    return url.replace(/[?#].*$/, '')
  }
}
