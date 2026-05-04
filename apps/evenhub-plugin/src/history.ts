export type HistoryKind = 'vision' | 'voice' | 'trading' | 'openclaw' | 'settings'

export interface HistoryItem {
  id: string
  kind: HistoryKind
  title: string
  input?: string
  answer: string
  detail?: string
  createdAt: string
}

const STORAGE_KEY = 'g2-vva-history-v1'
const MAX_HISTORY = 80
const MAX_KIND_HISTORY: Partial<Record<HistoryKind, number>> = {
  voice: 15,
}

export function addHistory(item: Omit<HistoryItem, 'id' | 'createdAt'>): HistoryItem {
  const historyItem: HistoryItem = {
    ...item,
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    createdAt: new Date().toISOString(),
  }
  const next = limitHistory([historyItem, ...getHistory()])
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  return historyItem
}

export function getHistory(): HistoryItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function clearHistory(): void {
  localStorage.removeItem(STORAGE_KEY)
}

export function renderHistory(): void {
  const scopedLists = document.querySelectorAll<HTMLDivElement>('[data-history-list]')
  if (scopedLists.length === 0) return

  const items = getHistory()
  for (const list of scopedLists) {
    const kind = list.dataset.historyList as HistoryKind | 'all' | undefined
    let filtered = !kind || kind === 'all' ? items : items.filter((item) => item.kind === kind)
    if (kind && kind !== 'all') {
      filtered = filtered.slice(0, MAX_KIND_HISTORY[kind] ?? MAX_HISTORY)
    }
    if (filtered.length === 0) {
      list.innerHTML = '<div class="history-empty">暂无历史记录</div>'
      continue
    }
    list.replaceChildren(...filtered.map(createHistoryElement))
  }
}

function limitHistory(items: HistoryItem[]): HistoryItem[] {
  const counts = new Map<HistoryKind, number>()
  const limited: HistoryItem[] = []

  for (const item of items) {
    const maxForKind = MAX_KIND_HISTORY[item.kind]
    if (maxForKind) {
      const count = counts.get(item.kind) ?? 0
      if (count >= maxForKind) continue
      counts.set(item.kind, count + 1)
    }

    limited.push(item)
    if (limited.length >= MAX_HISTORY) break
  }

  return limited
}

function createHistoryElement(item: HistoryItem): HTMLDetailsElement {
  const details = document.createElement('details')
  details.className = 'history-item'

  const summary = document.createElement('summary')
  summary.textContent = `${formatKind(item.kind)} · ${item.title} · ${formatTime(item.createdAt)}`
  details.append(summary)

  if (item.input) {
    const input = document.createElement('div')
    input.className = 'history-input'
    input.textContent = `输入：${item.input}`
    details.append(input)
  }

  const answer = document.createElement('div')
  answer.className = 'history-answer'
  answer.textContent = item.answer
  details.append(answer)

  const replay = document.createElement('button')
  replay.className = 'history-replay-button'
  replay.type = 'button'
  replay.textContent = '重播朗读'
  replay.addEventListener('click', (event) => {
    event.preventDefault()
    event.stopPropagation()
    document.dispatchEvent(
      new CustomEvent('g2vva:history-replay', {
        detail: {
          id: item.id,
          text: item.answer,
          title: item.title,
          kind: item.kind,
        },
      }),
    )
  })
  details.append(replay)

  const followup = document.createElement('button')
  followup.className = 'history-followup-button'
  followup.type = 'button'
  followup.textContent = '继续追问'
  followup.addEventListener('click', (event) => {
    event.preventDefault()
    event.stopPropagation()
    document.dispatchEvent(
      new CustomEvent('g2vva:history-followup', {
        detail: {
          id: item.id,
          kind: item.kind,
          title: item.title,
          input: item.input,
          answer: item.answer,
          detail: item.detail,
        },
      }),
    )
  })
  details.append(followup)

  const safeDetail = sanitizeHistoryDetail(item.detail)
  if (safeDetail) {
    const detail = document.createElement('div')
    detail.className = 'history-detail'
    detail.textContent = safeDetail
    details.append(detail)
  }

  return details
}

function sanitizeHistoryDetail(detail: string | undefined): string {
  if (!detail) return ''
  const blocked = /edict_backup|real_report_|daily-evolution|每日进化日志|codex-memories|MEMORY\.md|knowledge[-_]strategy|backup_\d{8}|reports\/daily/i
  return detail
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !blocked.test(line))
    .join('\n')
    .trim()
}

function formatKind(kind: HistoryKind): string {
  if (kind === 'vision') return '视觉'
  if (kind === 'voice') return '语音'
  if (kind === 'trading') return '交易'
  if (kind === 'openclaw') return 'OpenCLAW'
  return '设置'
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(value))
}
