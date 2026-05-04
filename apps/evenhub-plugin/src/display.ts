import {
  type EvenAppBridge,
  RebuildPageContainer,
  TextContainerProperty,
} from '@evenrealities/even_hub_sdk'

const CONTAINER_ID = 1
const CONTAINER_NAME = 'g2-vision'
const BODY_CONTAINER_ID = 1
const BODY_CONTAINER_NAME = CONTAINER_NAME
const G2_W = 576
const G2_H = 288

const enum G2Color {
  Dim = 1,
  Muted = 2,
  Cyan = 3,
  Teal = 5,
}

type HudMode = 'home' | 'vision' | 'voice' | 'trading' | 'reply' | 'settings'

let glassesBatteryLevel: number | undefined
let ringBatteryLevel: number | undefined

export function setG2BatteryLevel(value: number | undefined): void {
  setDeviceBatteryLevels({ glasses: value })
}

export function setDeviceBatteryLevels(levels: { glasses?: number; ring?: number }): void {
  if (typeof levels.glasses === 'number') glassesBatteryLevel = normalizeBattery(levels.glasses)
  if (typeof levels.ring === 'number') ringBatteryLevel = normalizeBattery(levels.ring)
  updateWebBattery()
}

export function startWebClock(): void {
  const update = () => {
    for (const el of document.querySelectorAll<HTMLElement>('[data-current-time]')) {
      el.textContent = currentTimeText()
    }
  }
  update()
  window.setInterval(update, 15000)
}

export function buildMainContainer(content: string): RebuildPageContainer {
  const text = new TextContainerProperty({
    xPosition: 0,
    yPosition: 0,
    width: G2_W,
    height: G2_H,
    borderWidth: 1,
    borderColor: 5,
    paddingLength: 8,
    containerID: CONTAINER_ID,
    containerName: CONTAINER_NAME,
    content,
    isEventCapture: 1,
  })

  return new RebuildPageContainer({
    containerTotalNum: 1,
    textObject: [text],
  })
}

export interface G2BookmarkView {
  activeIndex: number
  activeActionIndex?: number
  title: string
  body: string
  action: string
  items: Array<{ title: string; subtitle: string }>
  actions?: Array<{ label: string; disabled?: boolean }>
}

export async function showBookmarkOnG2(bridge: EvenAppBridge | undefined, view: G2BookmarkView): Promise<void> {
  const content = formatHudText(view)
  updateDebug(content)
  if (!bridge) return

  await bridge.rebuildPageContainer(buildMainContainer(content))
}

export async function showOnG2(bridge: EvenAppBridge | undefined, content: string): Promise<void> {
  updateDebug(content)

  if (!bridge) return

  const { title, body } = splitFormattedContent(content)
  await bridge.rebuildPageContainer(
    buildMainContainer(formatReplyHudText(title, body)),
  )
}

export function formatForG2(title: string, body: string): string {
  return [title, body].filter(Boolean).join('\n').slice(0, 360)
}

function buildHudView(view: G2BookmarkView): TextContainerProperty[] {
  const mode = getHudMode(view)
  if (view.activeActionIndex === undefined && isHomeLike(view)) return buildHudHome(view)
  if (mode === 'vision') return buildHudVision(view)
  if (mode === 'voice') return buildHudVoice(view)
  if (mode === 'trading') return buildHudTrading(view)
  if (mode === 'settings') return buildHudSettings(view)
  return buildHudReply(view)
}

function buildHudHome(view: G2BookmarkView): TextContainerProperty[] {
  return [
    ...buildHudFrame('天禄助手'),
    textBox(2, 36, 46, 250, 48, '天禄助手', { borderWidth: 0, color: G2Color.Teal, padding: 0 }),
    textBox(3, 36, 92, 310, 24, '你好，交易之路，天禄同行。', { borderWidth: 0, color: G2Color.Muted, padding: 0 }),
    ...buildMenuTiles(view, 128),
    textBox(30, 42, 260, 360, 20, '● G2 已连接  ·  OpenClaw 在线', {
      borderWidth: 0,
      color: G2Color.Teal,
      padding: 0,
    }),
    textBox(31, 400, 252, 132, 26, 'R1 上下切换', {
      borderColor: G2Color.Dim,
      borderRadius: 13,
      color: G2Color.Muted,
      padding: 5,
    }),
  ]
}

function buildHudVision(view: G2BookmarkView): TextContainerProperty[] {
  const body = view.body || ''
  const isCaptured = /已拍照|重拍|双击发送|确认上传|再次单触/.test(body)
  const isUploading = /发送|上传|请求|识别中|请稍候/.test(body)
  const isError = /失败|不可用|错误|允许相机/.test(body)
  const title = isError ? '相机不可用' : isUploading ? '正在发送图片给天禄' : isCaptured ? '已拍照' : 'R1 单击拍照'
  const hint = isError
    ? '请在手机 Even App 中允许相机权限'
    : isUploading
      ? '天禄正在读取画面，请稍候'
      : isCaptured
        ? '单触上传 · 上滑重拍 · 下滑取消'
        : '单触拍照 · 下滑返回'

  return [
    ...buildHudFrame('视觉识别'),
    textBox(10, 95, 70, 386, 150, `       ◉\n\n${title}\n${hint}`, {
      borderWidth: isError ? 2 : 2,
      borderColor: isError ? G2Color.Dim : G2Color.Teal,
      borderRadius: 22,
      color: isError ? G2Color.Muted : G2Color.Teal,
      padding: 18,
    }),
    textBox(11, 40, 128, 70, 22, '•  •  •', { borderWidth: 0, color: G2Color.Cyan, padding: 0 }),
    textBox(12, 466, 128, 70, 22, '•  •  •', { borderWidth: 0, color: G2Color.Cyan, padding: 0 }),
    buildActionStrip(view, 238),
  ]
}

function buildHudVoice(view: G2BookmarkView): TextContainerProperty[] {
  const body = compact(view.body || '点击或开麦后开始问天禄', 62)
  const listening = /监听|收到|听到|连接中/.test(body)
  const thinking = /思考|检查|请求/.test(body)
  const error = /失败|未收到|不可用|拒绝/.test(body)
  const stateText = error ? '语音异常' : thinking ? '天禄正在思考' : listening ? '正在监听' : '待命'

  return [
    ...buildHudFrame('天禄问答'),
    textBox(10, 223, 54, 130, 130, listening ? '  │││\n│││││\n  │││' : thinking ? '  ◌\n◌ ◎ ◌\n  ◌' : '  ◎\n天禄', {
      borderWidth: 2,
      borderColor: error ? G2Color.Dim : G2Color.Teal,
      borderRadius: 64,
      color: error ? G2Color.Muted : G2Color.Teal,
      padding: 24,
    }),
    textBox(11, 204, 190, 168, 28, stateText, { borderWidth: 0, color: error ? G2Color.Muted : G2Color.Teal, padding: 0 }),
    textBox(12, 72, 230, 432, 40, `“${body}”`, {
      borderColor: G2Color.Dim,
      borderRadius: 20,
      color: G2Color.Muted,
      padding: 8,
    }),
  ]
}

function buildHudTrading(view: G2BookmarkView): TextContainerProperty[] {
  const body = view.body || '真实交易状态未读取\n点击刷新'
  const pnl = body.match(/(?:PnL|盈亏|浮盈亏)[：:\s]*([+\-]?\d+(?:\.\d+)?%?)/i)?.[1] ?? '--'
  const positions = body.match(/持仓[：:\s]*(\d+)/)?.[1] ?? '--'
  const orders = body.match(/挂单[：:\s]*(\d+)/)?.[1] ?? '--'
  const risk = body.match(/风险[：:\s]*([^\n；;]+)/)?.[1]?.slice(0, 8) ?? '未读取'
  const strategy = body.match(/策略[：:\s]*([^\n；;]+)/)?.[1]?.slice(0, 16) ?? '未读取'
  const heartbeat = body.match(/心跳[：:\s]*([^\n；;]+)/)?.[1]?.slice(0, 12) ?? '--'

  return [
    ...buildHudFrame('交易状态'),
    textBox(10, 188, 48, 200, 38, '▱ 运行正常', { borderWidth: 0, color: G2Color.Teal, padding: 0 }),
    textBox(11, 178, 86, 220, 26, `心跳 ${heartbeat}`, { borderColor: G2Color.Dim, borderRadius: 13, color: G2Color.Muted, padding: 5 }),
    metricBox(20, 56, 124, '策略', strategy),
    metricBox(21, 222, 124, '持仓', positions),
    metricBox(22, 388, 124, '挂单', orders),
    metricBox(23, 56, 194, 'PnL', pnl, G2Color.Teal),
    metricBox(24, 305, 194, '风险', risk, /danger|危险|高|警/.test(risk) ? G2Color.Dim : G2Color.Teal, 215),
  ]
}

function buildHudReply(view: G2BookmarkView): TextContainerProperty[] {
  return [
    ...buildHudFrame('天禄回复'),
    textBox(10, 86, 58, 404, 170, `▣\n${compact(view.body || view.title, 110)}`, {
      borderColor: G2Color.Dim,
      borderRadius: 20,
      color: G2Color.Muted,
      padding: 18,
    }),
    textBox(11, 214, 246, 148, 24, 'R1 单击返回', { borderWidth: 0, color: G2Color.Teal, padding: 0 }),
  ]
}

function buildHudSettings(view: G2BookmarkView): TextContainerProperty[] {
  const rows = [
    ['麦克风', '已授权'],
    ['相机', '已授权'],
    ['OpenClaw', '已连接'],
    ['交易机器人', '已连接'],
  ] as const
  return [
    ...buildHudFrame('设置'),
    ...rows.map(([label, status], index) =>
      textBox(10 + index, 58, 52 + index * 52, 460, 40, `${settingIcon(index)}  ${label}                 ${status}   ›`, {
        borderColor: G2Color.Dim,
        borderRadius: 12,
        color: index === view.activeActionIndex ? G2Color.Teal : G2Color.Muted,
        padding: 9,
      }),
    ),
    buildActionStrip(view, 260),
  ]
}

function buildHudFrame(title: string): TextContainerProperty[] {
  return [
    textBox(BODY_CONTAINER_ID, 0, 0, G2_W, G2_H, '', {
      borderColor: G2Color.Dim,
      borderRadius: 28,
      padding: 0,
      capture: true,
      name: BODY_CONTAINER_NAME,
    }),
    textBox(91, 22, 12, 82, 24, currentTimeText(), { borderWidth: 0, color: G2Color.Teal, padding: 0 }),
    textBox(92, 214, 12, 148, 24, `· ${title} ·`, { borderWidth: 0, color: G2Color.Muted, padding: 0 }),
    textBox(93, 426, 12, 118, 24, batteryText(), { borderWidth: 0, color: G2Color.Teal, padding: 0 }),
    textBox(94, 12, 10, 36, 32, '╭', { borderWidth: 0, color: G2Color.Teal, padding: 0 }),
    textBox(95, 528, 10, 36, 32, '╮', { borderWidth: 0, color: G2Color.Teal, padding: 0 }),
    textBox(96, 12, 246, 36, 32, '╰', { borderWidth: 0, color: G2Color.Teal, padding: 0 }),
    textBox(97, 528, 246, 36, 32, '╯', { borderWidth: 0, color: G2Color.Teal, padding: 0 }),
  ]
}

function buildMenuTiles(view: G2BookmarkView, y: number): TextContainerProperty[] {
  const items = view.items.slice(0, 4)
  return items.map((item, index) => {
    const col = index % 2
    const row = Math.floor(index / 2)
    const active = index === view.activeIndex
    return textBox(10 + index, 36 + col * 254, y + row * 58, 222, 46, `${active ? '◆' : tileIcon(index)}  ${item.title}`, {
      borderWidth: active ? 2 : 1,
      borderColor: active ? G2Color.Teal : G2Color.Dim,
      borderRadius: 12,
      color: active ? G2Color.Teal : G2Color.Muted,
      padding: 10,
    })
  })
}

function buildActionStrip(view: G2BookmarkView, y: number): TextContainerProperty {
  const action = view.activeActionIndex === undefined ? view.action : (view.actions?.[view.activeActionIndex]?.label ?? view.action)
  return textBox(60, 76, y, 424, 28, compact(`R1 ${action.replace(/\n/g, ' · ')}`, 38), {
    borderColor: G2Color.Dim,
    borderRadius: 14,
    color: G2Color.Teal,
    padding: 6,
  })
}

function metricBox(id: number, x: number, y: number, label: string, value: string, color = G2Color.Muted, width = 150): TextContainerProperty {
  return textBox(id, x, y, width, 56, `${label}\n${value}`, {
    borderColor: G2Color.Dim,
    borderRadius: 10,
    color,
    padding: 8,
  })
}

function textBox(
  id: number,
  x: number,
  y: number,
  width: number,
  height: number,
  content: string,
  options: {
    borderWidth?: number
    borderColor?: number
    borderRadius?: number
    color?: number
    padding?: number
    capture?: boolean
    name?: string
  } = {},
): TextContainerProperty {
  return new TextContainerProperty({
    xPosition: x,
    yPosition: y,
    width,
    height,
    borderWidth: options.borderWidth ?? 1,
    borderColor: options.borderColor ?? G2Color.Dim,
    borderRadius: options.borderRadius ?? 10,
    paddingLength: options.padding ?? 6,
    containerID: id,
    containerName: options.name ?? `hud-${id}`,
    content,
    isEventCapture: options.capture ? 1 : 0,
  })
}

function getHudMode(view: G2BookmarkView): HudMode {
  const title = `${view.title} ${view.items[view.activeIndex]?.title ?? ''}`
  if (/视觉/.test(title)) return 'vision'
  if (/问答|天禄|语音/.test(title)) return 'voice'
  if (/交易/.test(title)) return 'trading'
  if (/设置|OpenCLAW|CLAW/.test(title)) return 'settings'
  return 'reply'
}

function isHomeLike(view: G2BookmarkView): boolean {
  return !/^R1 选择/.test(view.title) && !/正在|失败|结果|已拍照|相机|听到|OpenCLAW|交易只读/.test(view.title)
}

function tileIcon(index: number): string {
  return ['◉', '▣', '◇', '⚙'][index] ?? '□'
}

function settingIcon(index: number): string {
  return ['♬', '▣', '⌁', '▤'][index] ?? '•'
}

function compact(value: string, max: number): string {
  const text = value.replace(/\s+/g, ' ').trim()
  return text.length <= max ? text : `${text.slice(0, max - 1)}…`
}

function splitFormattedContent(content: string): { title: string; body: string } {
  const [title = '天禄回复', ...rest] = content.split('\n')
  const body = rest.join('\n').replace(/^━+\n?/, '').trim() || content
  return { title: title.trim() || '天禄回复', body }
}

function centerText(value: string, width: number): string {
  const text = compact(value, width)
  const left = Math.max(0, Math.floor((width - text.length) / 2))
  return `${' '.repeat(left)}${text}`.padEnd(width, ' ')
}

function wrapLines(value: string, width: number): string[] {
  const lines: string[] = []
  let current = ''
  for (const char of value) {
    if (current.length >= width || char === '\n') {
      lines.push(current)
      current = char === '\n' ? '' : char
    } else {
      current += char
    }
  }
  if (current) lines.push(current)
  return lines.length > 0 ? lines : ['']
}

function updateDebug(content: string): void {
  const el = document.querySelector<HTMLPreElement>('#debug-log')
  if (el) el.textContent = content
}

function formatBookmarkDebug(view: G2BookmarkView): string {
  const tabs = view.items.map((item, index) => `${index === view.activeIndex ? '■' : '□'} ${item.title}`).join('  ')
  const actions = view.actions?.map((item, index) => `${index === view.activeActionIndex ? '■' : '□'} ${item.label}`).join('  ')
  return `${tabs}\n${actions ?? ''}\n\n${view.title}\n${view.body}\n${view.action}`
}

function formatHudText(view: G2BookmarkView): string {
  const mode = getHudMode(view)
  if (view.activeActionIndex === undefined && isHomeLike(view)) return formatHomeHudText(view)
  if (mode === 'vision') return formatVisionHudText(view)
  if (mode === 'voice') return formatVoiceHudText(view)
  if (mode === 'trading') return formatTradingHudText(view)
  if (mode === 'settings') return formatSettingsHudText(view)
  return formatReplyHudText(view.title, view.body)
}

function formatHomeHudText(view: G2BookmarkView): string {
  const items = view.items.slice(0, 4)
  const tile = (index: number) => {
    const item = items[index]
    if (!item) return ''
    const marker = index === view.activeIndex ? '◆' : '◇'
    return `${marker} ${item.title} / ${item.subtitle}`
  }
  return [
    hudHeader('天禄助手'),
    '',
    'TIANLU ASSISTANT',
    '交易之路，天禄同行',
    '',
    tile(0),
    tile(1),
    tile(2),
    tile(3),
    '',
    'G2 已连接  OpenClaw 在线',
    hudFooter('R1 上下切换 / 单击进入'),
  ].join('\n').slice(0, 430)
}

function formatVisionHudText(view: G2BookmarkView): string {
  const body = view.body || ''
  const isCaptured = /已拍照|重拍|双击发送|确认上传|再次单触/.test(body)
  const isUploading = /发送|上传|请求|识别中|请稍候/.test(body)
  const isError = /失败|不可用|错误|允许相机/.test(body)
  const title = isError ? '相机不可用' : isUploading ? '正在发送图片给天禄' : isCaptured ? '已拍照' : 'R1 单击拍照'
  const hint = isError
    ? '请在手机 Even App 中允许相机权限'
    : isUploading
      ? '天禄正在读取画面，请稍候'
      : isCaptured
        ? '单触上传 · 上滑重拍 · 下滑取消'
        : '单触拍照 · 下滑返回'
  return [
    hudHeader('视觉识别'),
    '',
    'VISION SCAN',
    '',
    `◆ ${title}`,
    compact(hint, 28),
    '',
    '相机：手机后置摄像头',
    statusLine(isError ? '相机异常' : isUploading ? '发送中' : isCaptured ? '等待确认' : '待拍照'),
    '',
    hudFooter('单触拍照 / 再单触上传'),
  ].join('\n').slice(0, 430)
}

function formatVoiceHudText(view: G2BookmarkView): string {
  const body = compact(view.body || '点击或开麦后开始问天禄', 62)
  const listening = /监听|收到|听到|连接中/.test(body)
  const thinking = /思考|检查|请求/.test(body)
  const error = /失败|未收到|不可用|拒绝/.test(body)
  const stateText = error ? '语音异常' : thinking ? '天禄正在思考' : listening ? '正在监听' : '待命'
  return [
    hudHeader('天禄问答'),
    '',
    'VOICE CORE',
    '',
    listening ? '▮ ▮ ▮ ▮ ▮' : thinking ? '◇ ◇ ◆ ◇ ◇' : '◆ 语音待命',
    `状态：${stateText}`,
    '',
    `听取：${compact(body, 34)}`,
    '',
    '麦克风：G2 优先 / 手机耳机兜底',
    hudFooter('R1 单击语音确认'),
  ].join('\n').slice(0, 430)
}

function formatTradingHudText(view: G2BookmarkView): string {
  const body = view.body || '真实交易状态未读取\n点击刷新'
  const pnl = body.match(/(?:PnL|盈亏|浮盈亏)[：:\s]*([+\-]?\d+(?:\.\d+)?%?)/i)?.[1] ?? '--'
  const positions = body.match(/持仓[：:\s]*(\d+)/)?.[1] ?? '--'
  const orders = body.match(/挂单[：:\s]*(\d+)/)?.[1] ?? '--'
  const risk = body.match(/风险[：:\s]*([^\n；;]+)/)?.[1]?.slice(0, 8) ?? '未读取'
  const strategy = body.match(/策略[：:\s]*([^\n；;]+)/)?.[1]?.slice(0, 16) ?? '未读取'
  const heartbeat = body.match(/心跳[：:\s]*([^\n；;]+)/)?.[1]?.slice(0, 12) ?? '--'
  const running = /离线|失败|错误|danger|危险/i.test(body) ? '需要关注' : '运行正常'
  return [
    hudHeader('交易状态'),
    '',
    `◆ ${running}`,
    `心跳 ${heartbeat}`,
    '',
    `策略  ${strategy}`,
    `持仓  ${positions}    挂单  ${orders}`,
    `PnL   ${pnl}    风险  ${risk}`,
    '',
    '只读查询 · 禁止交易执行',
    hudFooter('R1 单击刷新'),
  ].join('\n').slice(0, 430)
}

function formatSettingsHudText(_view: G2BookmarkView): string {
  return [
    hudHeader('设置'),
    '',
    'SYSTEM LINKS',
    '',
    '◆ 麦克风       G2 优先',
    '◇ 相机         已授权',
    '◇ OpenClaw     已连接',
    '◇ 交易机器人   只读连接',
    '',
    hudFooter('R1 上下切换 / 单击执行'),
  ].join('\n').slice(0, 430)
}

function formatReplyHudText(title: string, body: string): string {
  const lines = wrapLines(compact(body, 150), 24).slice(0, 6)
  return [
    hudHeader(compact(title, 8)),
    '',
    'TIANLU REPLY',
    '',
    ...lines.map((line) => `  ${line}`),
    '',
    hudFooter('R1 单击返回'),
  ].join('\n').slice(0, 430)
}

function hudHeader(title: string): string {
  return `TL OS  ${currentTimeText()}  ${compact(title, 8)}  ${batteryText()}`
}

function hudFooter(action: string): string {
  return `R1  ${action}`
}

function statusLine(text: string): string {
  return `状态：${text}`
}

function batteryText(): string {
  const g2 = glassesBatteryLevel != null && glassesBatteryLevel > 0 ? `${glassesBatteryLevel}%` : '--'
  return `G2：${g2}`
}

export function getGlassBatteryText(): string {
  return batteryText()
}

function currentTimeText(): string {
  const now = new Date()
  return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
}

function updateWebBattery(): void {
  const g2 = glassesBatteryLevel != null && glassesBatteryLevel > 0 ? `${glassesBatteryLevel}%` : '--'
  for (const el of document.querySelectorAll<HTMLElement>('[data-g2-battery]')) {
    el.textContent = `G2：${g2}`
  }
  for (const el of document.querySelectorAll<HTMLElement>('[data-r1-battery]')) {
    el.textContent = ''
  }
}

function normalizeBattery(value: number | undefined): number | undefined {
  if (typeof value !== 'number' || !Number.isFinite(value)) return undefined
  return Math.max(0, Math.min(100, Math.round(value)))
}

function formatBattery(value: number | undefined): string {
  return typeof value === 'number' && value > 0 ? `${value}%` : '未上报'
}

function truncate(value: string, max: number): string {
  const text = value.trim()
  return text.length <= max ? text : `${text.slice(0, max - 1)}…`
}
