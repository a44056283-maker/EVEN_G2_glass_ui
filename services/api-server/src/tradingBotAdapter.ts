export type TradingBotStatus = {
  online: boolean
  lastHeartbeatAt: string
  mode: 'live' | 'paper' | 'backtest'
  strategyName: string
  exchange: string
  symbols: string[]
  todayPnlPct?: number
  todayPnlUsd?: number
  openPositions: number
  openOrders: number
  riskLevel: 'normal' | 'warning' | 'danger'
  errors: string[]
  warnings: string[]
  source: 'real' | 'mock'
}

export async function getTradingBotStatus(): Promise<TradingBotStatus> {
  const baseUrl = (process.env.TRADING_BOT_API_BASE ?? '').replace(/\/+$/, '')
  const token = process.env.TRADING_BOT_READONLY_TOKEN

  if (!baseUrl) {
    return {
      online: true,
      lastHeartbeatAt: new Date(Date.now() - 8000).toISOString(),
      mode: 'paper',
      strategyName: 'mock-momentum',
      exchange: 'mock',
      symbols: ['BTCUSDT', 'ETHUSDT'],
      todayPnlPct: 1.2,
      openPositions: 2,
      openOrders: 1,
      riskLevel: 'normal',
      errors: [],
      warnings: ['当前为 mock 只读状态，未接入真实交易机器人 API。'],
      source: 'mock',
    }
  }

  const response = await fetch(`${baseUrl}/status`, {
    headers: {
      Accept: 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })
  if (!response.ok) {
    throw new Error(`真实交易机器人状态接口请求失败：${response.status} ${(await response.text()).slice(0, 240)}`)
  }

  const data = (await response.json()) as TradingBotStatus
  return { ...data, source: data.source ?? 'real' }
}

export function formatTradingBotStatus(status: TradingBotStatus): string {
  const heartbeatSeconds = Math.max(0, Math.round((Date.now() - Date.parse(status.lastHeartbeatAt)) / 1000))
  const pnl = status.todayPnlPct === undefined ? '未知' : `${status.todayPnlPct >= 0 ? '+' : ''}${status.todayPnlPct}%`
  return [
    `交易机器人运行${status.online ? '正常' : '离线'}.`,
    `心跳：${heartbeatSeconds} 秒前`,
    `模式：${status.mode}`,
    `策略：${status.strategyName}`,
    `持仓：${status.openPositions} 个`,
    `挂单：${status.openOrders} 个`,
    `风险：${status.riskLevel === 'normal' ? '正常' : status.riskLevel}`,
    `今日 PnL：${pnl}`,
    `来源：${status.source}`,
    status.errors.length ? `错误：${status.errors.slice(0, 2).join('；')}` : '未发现严重错误。',
  ].join('\n')
}
