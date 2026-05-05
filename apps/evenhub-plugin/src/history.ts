import { clearIndexedHistory, loadIndexedHistory, saveIndexedHistory } from './historyStore'

export type HistoryKind = 'vision' | 'voice' | 'trading' | 'openclaw' | 'settings'

export interface HistoryItem {
  id: string
  kind: HistoryKind
  title: string
  input?: string
  answer: string
  detail?: string
  summary?: string
  thumbnailDataUrl?: string
  imageDataUrl?: string
  createdAt: string
}

const STORAGE_KEY = 'g2-vva-history-v1'
const MAX_HISTORY = 80
const LOCAL_STORAGE_MAX_IMAGE_ITEMS = 12
const MAX_KIND_HISTORY: Partial<Record<HistoryKind, number>> = {
  voice: 15,
}

let lastHistoryError = ''
let memoryHistoryFallback: HistoryItem[] = []
let cachedHistory: HistoryItem[] = []
let storageMode: 'indexeddb' | 'localstorage' | 'memory' = 'memory'
let loadStarted = false
let loadFinished = false
let saveQueue: Promise<void> = Promise.resolve()
let historyVersion = 0
let renderQueued = false

export function getLastHistoryError(): string {
  return lastHistoryError
}

export function addHistory(item: Omit<HistoryItem, 'id' | 'createdAt'>): HistoryItem {
  const historyItem: HistoryItem = {
    ...item,
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    createdAt: new Date().toISOString(),
  }
  const currentHistory = getHistory()
  const next = limitHistory([historyItem, ...currentHistory])
  cachedHistory = next
  memoryHistoryFallback = next.slice(0, MAX_HISTORY)
  historyVersion += 1
  persistHistory(next)
  return historyItem
}

export function updateHistoryItem(id: string, patch: Partial<Omit<HistoryItem, 'id' | 'createdAt'>>): HistoryItem | undefined {
  const currentHistory = getHistory()
  const index = currentHistory.findIndex((item) => item.id === id)
  if (index < 0) return undefined
  const nextItem = { ...currentHistory[index], ...patch }
  const next = currentHistory.slice()
  next[index] = nextItem
  cachedHistory = limitHistory(next)
  memoryHistoryFallback = cachedHistory.slice(0, MAX_HISTORY)
  historyVersion += 1
  persistHistory(cachedHistory)
  return nextItem
}

export function getHistory(): HistoryItem[] {
  if (!loadStarted) {
    loadStarted = true
    cachedHistory = readLocalHistory()
    memoryHistoryFallback = cachedHistory
    void hydrateHistoryFromIndexedDb()
  }
  if (cachedHistory.length) return cachedHistory
  if (memoryHistoryFallback.length) return memoryHistoryFallback
  cachedHistory = readLocalHistory()
  memoryHistoryFallback = cachedHistory
  return cachedHistory
}

export function clearHistory(): void {
  cachedHistory = []
  memoryHistoryFallback = []
  lastHistoryError = ''
  historyVersion += 1
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch (error) {
    reportHistoryError('localStorage 清空失败', error)
  }
  saveQueue = saveQueue
    .then(() => clearIndexedHistory())
    .then(() => {
      storageMode = 'indexeddb'
    })
    .catch((error) => {
      storageMode = storageMode === 'indexeddb' ? 'localstorage' : storageMode
      reportHistoryError('IndexedDB 清空失败', error)
    })
}

export function renderHistory(): void {
  const scopedLists = document.querySelectorAll<HTMLDivElement>('[data-history-list]')
  if (scopedLists.length === 0) return

  if (!loadFinished) void hydrateHistoryFromIndexedDb()

  const items = getHistory()
  for (const list of scopedLists) {
    const kind = list.dataset.historyList as HistoryKind | 'all' | undefined
    let filtered = !kind || kind === 'all' ? items : items.filter((item) => item.kind === kind)
    if (kind && kind !== 'all') {
      filtered = filtered.slice(0, MAX_KIND_HISTORY[kind] ?? MAX_HISTORY)
    }
    const children: HTMLElement[] = []
    if (lastHistoryError) children.push(createHistoryErrorElement())
    if (filtered.length === 0) {
      children.push(createHistoryEmptyElement())
    } else {
      children.push(...filtered.map(createHistoryElement))
    }
    list.replaceChildren(...children)
  }
}

function readLocalHistory(): HistoryItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return memoryHistoryFallback.length ? memoryHistoryFallback : []
    const parsed = JSON.parse(raw)
    return normalizeHistoryItems(parsed)
  } catch {
    return memoryHistoryFallback.length ? memoryHistoryFallback : []
  }
}

async function hydrateHistoryFromIndexedDb(): Promise<void> {
  loadStarted = true
  if (loadFinished && storageMode === 'indexeddb') return
  const versionAtStart = historyVersion
  try {
    const indexedHistory = limitHistory(normalizeHistoryItems(await loadIndexedHistory()))
    const localHistory = readLocalHistory()
    const loadedHistory = indexedHistory.length ? indexedHistory : localHistory
    const next = versionAtStart === historyVersion ? loadedHistory : mergeHistory(cachedHistory, loadedHistory)
    cachedHistory = next
    memoryHistoryFallback = next
    loadFinished = true
    storageMode = 'indexeddb'
    lastHistoryError = ''
    if (!indexedHistory.length && localHistory.length && versionAtStart === historyVersion) await saveIndexedHistory(localHistory)
    renderHistory()
  } catch (error) {
    loadFinished = true
    const localHistory = readLocalHistory()
    const next = versionAtStart === historyVersion ? localHistory : mergeHistory(cachedHistory, localHistory)
    cachedHistory = next
    memoryHistoryFallback = next
    storageMode = localHistory.length ? 'localstorage' : 'memory'
    reportHistoryError('IndexedDB 读取失败，已切换备用存储', error)
    renderHistory()
  }
}

function persistHistory(items: HistoryItem[]): void {
  memoryHistoryFallback = items.slice(0, MAX_HISTORY)
  saveQueue = saveQueue
    .then(async () => {
      await saveIndexedHistory(items)
      storageMode = 'indexeddb'
      lastHistoryError = ''
      tryWriteLocalHistory(createLocalStorageSnapshot(items), false)
    })
    .catch((error) => {
      reportHistoryError('IndexedDB 写入失败，尝试 localStorage 备用', error)
      if (tryWriteLocalHistory(items, true)) {
        storageMode = 'localstorage'
        return
      }

      const compactItems = items.map(stripLargeHistoryFields)
      if (tryWriteLocalHistory(compactItems, true)) {
        storageMode = 'localstorage'
        reportHistoryError('图片字段过大，已保留历史文字记录', error)
        return
      }

      storageMode = 'memory'
      reportHistoryError('历史保存失败，已仅保存在内存', error)
    })
}

function tryWriteLocalHistory(items: HistoryItem[], reportError: boolean): boolean {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(limitHistory(items)))
    return true
  } catch (error) {
    if (reportError) reportHistoryError('localStorage 写入失败', error)
    return false
  }
}

function createLocalStorageSnapshot(items: HistoryItem[]): HistoryItem[] {
  return limitHistory(items).map((item, index) => {
    if (item.kind === 'vision' && index < LOCAL_STORAGE_MAX_IMAGE_ITEMS) {
      const { imageDataUrl: _imageDataUrl, ...thumbnailOnly } = item
      return thumbnailOnly
    }
    return stripLargeHistoryFields(item)
  })
}

function stripLargeHistoryFields(item: HistoryItem): HistoryItem {
  if (!item.thumbnailDataUrl && !item.imageDataUrl) return item
  const { thumbnailDataUrl: _thumbnailDataUrl, imageDataUrl: _imageDataUrl, ...rest } = item
  return rest
}

function reportHistoryError(prefix: string, error: unknown): void {
  const message = error instanceof Error ? error.message : String(error)
  lastHistoryError = `${prefix}：${message}`
  console.warn('[G2 history]', lastHistoryError, error)
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('g2vva:history-error', { detail: { error: lastHistoryError, storageMode } }))
  }
  queueHistoryRender()
}

function normalizeHistoryItems(value: unknown): HistoryItem[] {
  if (!Array.isArray(value)) return []
  return limitHistory(
    value.filter((item): item is HistoryItem => {
      if (!item || typeof item !== 'object') return false
      const candidate = item as Partial<HistoryItem>
      return Boolean(candidate.id && candidate.kind && candidate.title && candidate.answer && candidate.createdAt)
    }),
  )
}

function mergeHistory(primary: HistoryItem[], secondary: HistoryItem[]): HistoryItem[] {
  const byId = new Map<string, HistoryItem>()
  for (const item of [...primary, ...secondary]) byId.set(item.id, item)
  return limitHistory([...byId.values()].sort((a, b) => b.createdAt.localeCompare(a.createdAt)))
}

function queueHistoryRender(): void {
  if (renderQueued || typeof document === 'undefined') return
  renderQueued = true
  queueMicrotask(() => {
    renderQueued = false
    renderHistory()
  })
}

function createHistoryEmptyElement(): HTMLDivElement {
  const empty = document.createElement('div')
  empty.className = 'history-empty'
  empty.textContent = '暂无历史记录'
  return empty
}

function createHistoryErrorElement(): HTMLDivElement {
  const errorElement = document.createElement('div')
  errorElement.className = 'history-error'
  errorElement.textContent = `历史存储提示：${lastHistoryError}`
  return errorElement
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

  if (item.thumbnailDataUrl) {
    const thumbnail = document.createElement('img')
    thumbnail.className = 'history-thumbnail'
    thumbnail.alt = item.summary || item.title || '历史缩略图'
    thumbnail.src = item.thumbnailDataUrl
    thumbnail.loading = 'lazy'
    thumbnail.style.width = '96px'
    thumbnail.style.height = '72px'
    thumbnail.style.objectFit = 'cover'
    thumbnail.style.borderRadius = '10px'
    thumbnail.style.border = '1px solid rgba(103, 246, 232, 0.22)'
    thumbnail.style.marginTop = '10px'
    details.append(thumbnail)
  }

  if (item.imageDataUrl) {
    const originalButton = document.createElement('button')
    originalButton.className = 'history-original-button'
    originalButton.type = 'button'
    originalButton.textContent = '查看采集照片'
    const original = document.createElement('img')
    original.className = 'history-original-image'
    original.alt = item.summary || item.title || '采集照片'
    original.src = item.imageDataUrl
    original.loading = 'lazy'
    original.hidden = true
    originalButton.addEventListener('click', (event) => {
      event.preventDefault()
      event.stopPropagation()
      original.hidden = !original.hidden
      originalButton.textContent = original.hidden ? '查看采集照片' : '收起采集照片'
    })
    details.append(originalButton, original)
  }

  if (item.summary) {
    const itemSummary = document.createElement('div')
    itemSummary.className = 'history-summary'
    itemSummary.textContent = item.summary
    details.append(itemSummary)
  }

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
          summary: item.summary,
          thumbnailDataUrl: item.thumbnailDataUrl,
          imageDataUrl: item.imageDataUrl,
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
