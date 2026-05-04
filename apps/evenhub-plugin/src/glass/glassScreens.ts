import { compactForG2, progressBar, sanitizeForG2Text } from './glassText'

export type GlassScreenId =
  | 'home'
  | 'vision_preparing'
  | 'vision_ready'
  | 'vision_captured'
  | 'vision_uploading'
  | 'voice_idle'
  | 'voice_menu'
  | 'voice_recording'
  | 'voice_finalizing'
  | 'voice_to_vision'
  | 'voice_answer'
  | 'voice_error'
  | 'voice_mic_probe'
  | 'voice_no_pcm'
  | 'voice_transcript'
  | 'trading_status'
  | 'trading_menu'
  | 'trading_prices'
  | 'trading_positions'
  | 'trading_distribution'
  | 'trading_attribution'
  | 'trading_alerts'
  | 'risk_alert'
  | 'reply'
  | 'diagnostics'
  | 'settings'
  | 'debug_input'
  | 'error'

export type GlassScreenName = GlassScreenId

export interface GlassScreenState {
  battery: string
  time?: string
  selectedIndex?: number
  activeIndex?: number
  title?: string
  body?: string
  status?: string
  reason?: string
  transcript?: string
  answer?: string
  inputDebug?: string
  pcmBytes?: number
  chunks?: number
  lastChunkBytes?: number
  backendBytes?: number
  trading?: {
    online?: boolean
    heartbeat?: string
    strategy?: string
    positions?: number | string
    orders?: number | string
    pnl?: string
    risk?: string
    source?: string
  }
  settings?: {
    microphone?: string
    camera?: string
    openclaw?: string
    trading?: string
    asr?: string
  }
  diagnostics?: {
    g2?: string
    r1?: string
    cam?: string
    mic?: string
    asr?: string
    claw?: string
    bot?: string
  }
  tabs?: Array<{
    title: string
    subtitle?: string
  }>
  actions?: Array<{
    label: string
    disabled?: boolean
  }>
  /** Extended data for trading sub-pages */
  extendedData?: {
    prices?: Array<{ symbol: string; pair: string; price: number; freshness?: string }>
    positions?: Array<{ pair: string; pnl?: number; notional?: number; share?: number; maxLeverage?: number }>
    distribution?: Array<{ pair: string; share: number; pnl?: number }>
    attribution?: { winRatePct?: number; avgRealizedPnlPct?: number; avgUnrealizedPnlPct?: number; sampleCount?: number }
    alerts?: Array<{ level?: string; message?: string; action?: string }>
    portsOnline?: number
    portsTotal?: number
    autopilotEnabled?: boolean
    riskLevel?: string
    riskScore?: number
    totalUnrealizedPnl?: number
    openPositions?: number
  }
}

const WIDTH = 48

export function renderGlassScreen(name: GlassScreenId, state: GlassScreenState): string {
  return sanitizeForG2Text(renderRawGlassScreen(name, state), { maxLines: 11, maxChars: 460 })
}

function renderRawGlassScreen(name: GlassScreenId, state: GlassScreenState): string {
  if (name === 'home') return renderHome(state)
  if (name === 'vision_preparing') return renderVisionPreparing(state)
  if (name === 'vision_ready') return renderVisionReady(state)
  if (name === 'vision_captured') return renderVisionCaptured(state)
  if (name === 'vision_uploading') return renderVisionUploading(state)
  if (name === 'voice_menu') return renderVoiceMenu(state)
  if (name === 'voice_idle') return renderVoiceIdle(state)
  if (name === 'voice_recording') return renderVoiceRecording(state)
  if (name === 'voice_finalizing') return renderVoiceFinalizing(state)
  if (name === 'voice_to_vision') return renderVoiceToVision(state)
  if (name === 'voice_answer') return renderVoiceAnswer(state)
  if (name === 'voice_error') return renderVoiceError(state)
  if (name === 'voice_mic_probe') return renderVoiceMicProbe(state)
  if (name === 'voice_no_pcm') return renderVoiceNoPcm(state)
  if (name === 'voice_transcript') return renderVoiceTranscript(state)
  if (name === 'trading_status') return renderTradingStatus(state)
  if (name === 'trading_menu') return renderTradingMenu(state)
  if (name === 'trading_prices') return renderTradingPrices(state)
  if (name === 'trading_positions') return renderTradingPositions(state)
  if (name === 'trading_distribution') return renderTradingDistribution(state)
  if (name === 'trading_attribution') return renderTradingAttribution(state)
  if (name === 'trading_alerts') return renderTradingAlerts(state)
  if (name === 'risk_alert') return renderRiskAlert(state)
  if (name === 'settings') return renderSettings(state)
  if (name === 'diagnostics') return renderDiagnostics(state)
  if (name === 'debug_input') return renderDebugInput(state)
  if (name === 'error') return renderError(state)
  return renderReply(state)
}

function renderHome(state: GlassScreenState): string {
  const selected = state.selectedIndex ?? state.activeIndex ?? 0
  const time = state.time || '12:36'
  const battery = state.battery || 'G2:--'

  const menuLine = [
    `[视觉识别${selected === 0 ? '●' : '○'}]`,
    `[呼叫天禄${selected === 1 ? '●' : '○'}]`,
    `[交易状态${selected === 2 ? '●' : '○'}]`,
    `[系统设置${selected === 3 ? '●' : '○'}]`,
  ].join('')

  const topLine = (time.slice(0, 5) + ' '.repeat(WIDTH - 5 - Math.min(9, battery.length)) + battery.slice(0, 9)).padEnd(WIDTH)

  return [
    topLine,
    '',
    menuLine,
    '',
    '          ↑↓ 选择   单触进入',
  ].join('\n')
}

export function renderVisionPreparing(state: GlassScreenState): string {
  return [
    topBar(state.time, state.battery, '视觉识别'),
    '',
    center('正在打开手机相机'),
    center('请完成拍照'),
    '',
    center('完成后自动上传识别'),
  ].join('\n')
}

export function renderVisionReady(state: GlassScreenState): string {
  return [
    topBar(state.time, state.battery, '视觉识别'),
    '',
    center('相机已就绪'),
    center('R1 单触拍照'),
    '',
    center('下滑返回'),
  ].join('\n')
}

export function renderVisionCaptured(state: GlassScreenState): string {
  return [
    topBar(state.time, state.battery, '视觉识别'),
    '',
    center('已锁定当前画面'),
    '',
    center('再次单触：上传识别'),
    '',
    center('上滑重拍  下滑取消'),
    center('等待确认...'),
  ].join('\n')
}

export function renderVisionUploading(state: GlassScreenState): string {
  return [
    topBar(state.time, state.battery, '视觉识别'),
    '',
    center('正在发送图片'),
    center('给天禄识别...'),
    '',
    center('[AI ANALYZING]'),
    center(progressBar(4, 6, 6)),
    '',
    center('请稍候'),
  ].join('\n')
}

export function renderVoiceIdle(state: GlassScreenState): string {
  return renderVoiceMenu(state)
}

export function renderVoiceMenu(state: GlassScreenState): string {
  return [
    topBar(state.time, state.battery, '天禄问答'),
    '',
    center('呼叫天禄'),
    '',
    center('手机端：按住说话'),
    center('R1：单触开始/结束'),
    '',
    center('最长录音 120 秒'),
  ].join('\n')
}

export function renderVoiceRecording(state: GlassScreenState): string {
  const elapsed = Math.max(0, Math.round(Number(state.status ?? 0)))
  const pcm = compactNumber(state.pcmBytes ?? 0)
  const chunks = state.chunks ?? 0
  return [
    topBar(state.time, state.battery, '天禄问答'),
    '',
    center('正在监听'),
    '',
    leftRight('时间', `${elapsed}/120秒`),
    leftRight('PCM', pcm),
    leftRight('CHUNKS', String(chunks)),
    '',
    center('单触结束  下滑取消'),
  ].join('\n')
}

export function renderVoiceFinalizing(state: GlassScreenState): string {
  return [
    topBar(state.time, state.battery, '天禄问答'),
    '',
    center('录音结束'),
    '',
    center('正在识别...'),
    '',
    center('[ASR PROCESSING]'),
    '',
    center('请稍候'),
  ].join('\n')
}

export function renderVoiceToVision(state: GlassScreenState): string {
  return [
    topBar(state.time, state.battery, '意图切换'),
    '',
    center('检测到视觉意图'),
    '',
    center('正在切换'),
    center('视觉识别流程...'),
    '',
    center('请稍候'),
  ].join('\n')
}

export function renderVoiceAnswer(state: GlassScreenState): string {
  const lines = splitShort(state.answer || state.body || '天禄暂无回答', 4)
  return [
    topBar(state.time, state.battery, '天禄回复'),
    '',
    center('天禄回复'),
    '',
    ...lines.map((line) => center(line)),
    '',
    center('单触继续  下滑返回'),
  ].join('\n')
}

export function renderVoiceError(state: GlassScreenState): string {
  const lines = splitShort(state.body || state.reason || '语音错误', 3)
  return [
    topBar(state.time, state.battery, '天禄问答'),
    '',
    center('语音错误'),
    '',
    ...lines.map((line) => center(line)),
    '',
    center('单触重试  下滑返回'),
  ].join('\n')
}

export function renderVoiceNoPcm(state: GlassScreenState): string {
  const reason = state.reason ? compactForG2(state.reason, 18) : '检查 G2 连接 / 权限'
  return [
    topBar(state.time, state.battery, '天禄问答'),
    '',
    center('未收到麦克风数据'),
    '',
    center(reason),
    center('或使用手动发送'),
    '',
    center('单触重试  下滑返回'),
  ].join('\n')
}

export function renderVoiceMicProbe(state: GlassScreenState): string {
  return [
    topBar(state.time, state.battery, '麦克风诊断'),
    '',
    center('G2 麦克风诊断'),
    '',
    leftRight('PCM', compactNumber(state.pcmBytes ?? 0)),
    leftRight('CHUNKS', String(state.chunks ?? 0)),
    leftRight('LAST', String(state.lastChunkBytes ?? 0)),
    '',
    center('单触刷新  下滑返回'),
  ].join('\n')
}

export function renderVoiceTranscript(state: GlassScreenState): string {
  const lines = splitShort(state.transcript || state.body || '语音已收到', 3)
  return [
    topBar(state.time, state.battery, '天禄问答'),
    '',
    center('听到：'),
    '',
    ...lines.map((line) => center(line)),
    '',
    center('天禄正在处理...'),
  ].join('\n')
}

export function renderTradingStatus(state: GlassScreenState): string {
  const trading = state.trading
  if (!trading) {
    return [
      topBar(state.time, state.battery, '交易状态'),
      '',
      center('正在读取交易只读状态'),
      '',
      center('单触刷新  下滑返回'),
    ].join('\n')
  }

  return [
    topBar(state.time, state.battery),
    center(`运行${trading.online === false ? '需关注' : '正常'}`),
    leftRight('心跳', compactForG2(trading.heartbeat ?? '--', 10)),
    leftRight('策略', compactForG2(String(trading.strategy ?? '--'), 10)),
    leftRight('持仓/挂单', `${trading.positions ?? '--'}/${trading.orders ?? '--'}`),
    leftRight('PnL', compactForG2(trading.pnl ?? '--', 10)),
    leftRight('风险', compactForG2(trading.risk ?? '--', 10)),
    center('↑↓ 切换   单击选择'),
  ].join('\n')
}

const TRADING_MENU_ITEMS = [
  { id: 'trading_status', label: '运行状态' },
  { id: 'trading_prices', label: '白名单价' },
  { id: 'trading_positions', label: '持仓盈亏' },
  { id: 'trading_distribution', label: '资金分布' },
  { id: 'trading_attribution', label: '订单归因' },
  { id: 'trading_alerts', label: '风控告警' },
]

export function renderTradingMenu(state: GlassScreenState): string {
  const selected = state.activeIndex ?? state.selectedIndex ?? 0
  const tabs1 = TRADING_MENU_ITEMS.slice(0, 3).map((item, i) => `[${item.label}${i + 0 === selected ? '●' : '○'}]`)
  const tabs2 = TRADING_MENU_ITEMS.slice(3, 6).map((item, i) => `[${item.label}${i + 3 === selected ? '●' : '○'}]`)
  const row1 = centerTabRow(tabs1)
  const row2 = centerTabRow(tabs2)
  return [
    topBar(state.time, state.battery),
    '',
    row1,
    row2,
    '',
    center('↑↓ 选择   单触进入'),
  ].join('\n')
}

export function renderTradingPrices(state: GlassScreenState): string {
  const prices = state.extendedData?.prices ?? []
  const rows = prices.slice(0, 5)
  return [
    topBar(state.time, state.battery),
    ...rows.map((p) => centerTabRow([`${p.symbol}`, `$${p.price.toFixed(p.price < 1 ? 4 : 2)}`])),
    ...Array(Math.max(0, 5 - rows.length)).fill(''),
    '',
    center('↑↓ 返回   单击进入'),
  ].join('\n')
}

export function renderTradingPositions(state: GlassScreenState): string {
  const positions = state.extendedData?.positions ?? []
  const totalPnl = state.extendedData?.totalUnrealizedPnl
  const openPos = state.extendedData?.openPositions ?? 0
  const rows = positions.slice(0, 4)
  const pnlSummary = totalPnl != null ? `${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(2)}` : '--'
  return [
    topBar(state.time, state.battery),
    center(`持仓 ${openPos} 个 · ${pnlSummary}`),
    ...rows.map((p) => {
      const pnlStr = p.pnl != null ? `${p.pnl >= 0 ? '+' : ''}${p.pnl.toFixed(2)}` : '--'
      return centerTabRow([compactForG2(p.pair, 10), pnlStr])
    }),
    ...Array(Math.max(0, 4 - rows.length)).fill(''),
    '',
    center('↑↓ 返回   单击进入'),
  ].join('\n')
}

export function renderTradingDistribution(state: GlassScreenState): string {
  const dist = state.extendedData?.distribution ?? []
  const rows = dist.slice(0, 5)
  return [
    topBar(state.time, state.battery),
    ...rows.map((d) => {
      const pct = `${d.share.toFixed(1)}%`
      const pnlStr = d.pnl != null ? `${d.pnl >= 0 ? '+' : ''}$${d.pnl.toFixed(0)}` : ''
      return centerTabRow([compactForG2(d.pair, 10), `${pct}  ${pnlStr}`])
    }),
    ...Array(Math.max(0, 5 - rows.length)).fill(''),
    '',
    center('↑↓ 返回   单击进入'),
  ].join('\n')
}

export function renderTradingAttribution(state: GlassScreenState): string {
  const attr = state.extendedData?.attribution
  const winRate = attr?.winRatePct != null ? `${attr.winRatePct.toFixed(1)}%` : '--'
  const avgReal = attr?.avgRealizedPnlPct != null ? `${attr.avgRealizedPnlPct >= 0 ? '+' : ''}${attr.avgRealizedPnlPct.toFixed(2)}%` : '--'
  const avgUnreal = attr?.avgUnrealizedPnlPct != null ? `${attr.avgUnrealizedPnlPct >= 0 ? '+' : ''}${attr.avgUnrealizedPnlPct.toFixed(2)}%` : '--'
  const samples = attr?.sampleCount ?? '--'
  return [
    topBar(state.time, state.battery),
    centerTabRow([`胜率 ${winRate}`, `均盈 ${avgReal}`, `均亏 ${avgUnreal}`]),
    center(`样本 ${samples} 单`),
    '',
    '',
    center('↑↓ 返回   单击进入'),
  ].join('\n')
}

export function renderTradingAlerts(state: GlassScreenState): string {
  const alerts = state.extendedData?.alerts ?? []
  const rows = alerts.slice(0, 4)
  return [
    topBar(state.time, state.battery),
    ...rows.map((a) => {
      const level = a.level === 'critical' || a.level === 'high' ? '!' : a.level === 'medium' ? '~' : '-'
      return center(`${level}  ${compactForG2(a.message || '无告警', 38)}`)
    }),
    ...Array(Math.max(0, 4 - rows.length)).fill(''),
    '',
    center('↑↓ 返回   单击进入'),
  ].join('\n')
}

export function renderRiskAlert(state: GlassScreenState): string {
  const lines = splitShort(state.body || state.status || '当前无重大告警，仓位风险正常。', 5)
  return [
    topBar(state.time, state.battery),
    ...lines.map((line) => center(line)),
    '',
    center('↑↓ 返回   单击进入'),
  ].join('\n')
}

export function renderReply(state: GlassScreenState): string {
  const lines = splitShort(state.answer || state.body || '暂无回复', 4)
  return [
    topBar(state.time, state.battery, state.title || '天禄回复'),
    '',
    center(state.title || '天禄回复'),
    '',
    ...lines.map((line) => center(line)),
    '',
    center('R1 单击返回'),
  ].join('\n')
}

export function renderDiagnostics(state: GlassScreenState): string {
  const d = state.diagnostics ?? {}
  return [
    topBar(state.time, state.battery, '调试'),
    '',
    center(`相机：${compactForG2(d.cam ?? '待检测', 10)}`),
    center(`麦克风：${compactForG2(d.mic ?? '待检测', 10)}`),
    center(`ASR：${compactForG2(d.asr ?? '待检测', 10)}`),
    center(`Claw：${compactForG2(d.claw ?? '待检测', 10)}`),
    '',
    center('单击返回  上滑扫描'),
  ].join('\n')
}

export function renderSettings(state: GlassScreenState): string {
  const settings = state.settings ?? {}
  return [
    topBar(state.time, state.battery, '设置'),
    '',
    center(`麦克风：${compactForG2(settings.microphone ?? 'G2/手机', 10)}`),
    center(`相机：${compactForG2(settings.camera ?? '手机后置', 10)}`),
    center(`Claw：${compactForG2(settings.openclaw ?? '已连接', 10)}`),
    center(`交易：${compactForG2(settings.trading ?? '只读', 10)}`),
    '',
    center('单击返回  上滑返回'),
  ].join('\n')
}

export function renderDebugInput(state: GlassScreenState): string {
  return [
    topBar(state.time, state.battery, '输入调试'),
    ...(state.inputDebug || '等待输入事件').split('\n').slice(0, 8),
  ].join('\n')
}

export function renderError(state: GlassScreenState): string {
  const lines = splitShort(state.body || state.status || state.title || '未知错误', 4)
  return [
    topBar(state.time, state.battery, '错误'),
    '',
    center('发生错误'),
    '',
    ...lines.map((line) => center(line)),
    '',
    center('单触重试  下滑返回'),
  ].join('\n')
}

function topBar(timeText?: string, batteryText?: string, title?: string): string {
  const time = (timeText || currentTime()).slice(0, 5)
  const batt = (batteryText || '').slice(0, 9)
  const line = (time + ' '.repeat(WIDTH - time.length - batt.length) + batt).padEnd(WIDTH)
  if (!title) return line
  return `${line}\n${center(title)}`
}

function center(value: string): string {
  const text = compactForG2(value, WIDTH)
  const left = Math.max(0, Math.floor((WIDTH - text.length) / 2))
  return `${' '.repeat(left)}${text}`
}

function centerTabRow(tabs: string[]): string {
  const total = tabs.join('')
  const left = Math.max(0, Math.floor((WIDTH - total.length) / 2))
  return ' '.repeat(left) + total
}

function leftRight(left: string, right: string, maxEach = 20): string {
  const l = compactForG2(left, maxEach)
  const r = compactForG2(right, maxEach)
  const combined = l.length + r.length
  if (combined >= WIDTH) return l + ' ' + r
  return `${l} ${r}`
}

function compactNumber(value: number): string {
  if (value >= 1000000) return `${Math.round(value / 10000)}万`
  if (value >= 10000) return `${(value / 10000).toFixed(1)}万`
  return String(value)
}

function currentTime(): string {
  const now = new Date()
  return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
}

function splitShort(text: string, maxLines: number): string[] {
  const clean = text.replace(/\n+/g, ' ').trim()
  if (!clean) return ['']
  return wrapLine(clean, WIDTH).slice(0, maxLines)
}

function wrapLine(line: string, width: number): string[] {
  if (line.length <= width) return [line]
  const result: string[] = []
  let current = ''
  for (const char of line) {
    if (current.length >= width) {
      result.push(current)
      current = char
    } else {
      current += char
    }
  }
  if (current) result.push(current)
  return result
}
