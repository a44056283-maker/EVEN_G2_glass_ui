export interface RuntimeErrorReport {
  kind: 'error' | 'unhandledrejection' | 'glass-show' | 'g2-display'
  message: string
  detail?: string
  createdAt: string
  page?: string
}

const STORAGE_KEY = 'g2-vva-runtime-errors-v1'
const MAX_REPORTS = 40
let installed = false

export function installRuntimeErrorReporter(apiBaseProvider: () => string): void {
  if (installed) return
  installed = true

  const previousOnError = window.onerror
  window.onerror = (message, source, lineno, colno, error) => {
    void recordRuntimeError(apiBaseProvider, {
      kind: 'error',
      message: typeof message === 'string' ? message : 'window error',
      detail: [
        source,
        lineno,
        colno,
        error instanceof Error && error.stack ? error.stack : undefined,
      ].filter(Boolean).join('\n'),
      createdAt: new Date().toISOString(),
      page: location.href,
    })

    if (typeof previousOnError === 'function') {
      return previousOnError.call(window, message, source, lineno, colno, error)
    }
    return false
  }

  const previousUnhandledRejection = window.onunhandledrejection
  window.onunhandledrejection = (event) => {
    void recordRuntimeError(apiBaseProvider, {
      kind: 'unhandledrejection',
      message: stringifyReason(event.reason),
      detail: reasonStack(event.reason),
      createdAt: new Date().toISOString(),
      page: location.href,
    })

    if (typeof previousUnhandledRejection === 'function') {
      return previousUnhandledRejection.call(window, event)
    }
    return undefined
  }
}

export async function recordRuntimeError(
  apiBaseProvider: () => string,
  report: RuntimeErrorReport,
): Promise<void> {
  const sanitized = sanitizeReport(report)
  persistLocal(sanitized)
  window.dispatchEvent(new CustomEvent('g2vva:runtime-error', { detail: sanitized }))

  try {
    await fetch(`${apiBaseProvider().replace(/\/+$/, '')}/debug/runtime-error`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(sanitized),
      keepalive: true,
    })
  } catch {
    // Local persistence is enough when network logging is unavailable.
  }
}

function persistLocal(report: RuntimeErrorReport): void {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const current = raw ? JSON.parse(raw) : []
    const reports = Array.isArray(current) ? current : []
    reports.unshift(sanitizeReport(report))
    localStorage.setItem(STORAGE_KEY, JSON.stringify(reports.slice(0, MAX_REPORTS)))
  } catch {
    // Ignore storage failures; history has its own visible fallback path.
  }
}

function sanitizeReport(report: RuntimeErrorReport): RuntimeErrorReport {
  return {
    ...report,
    message: redact(report.message).slice(0, 800),
    detail: report.detail ? redact(report.detail).slice(0, 1200) : undefined,
    page: report.page ? report.page.replace(/[?#].*$/, '') : undefined,
  }
}

function stringifyReason(reason: unknown): string {
  if (reason instanceof Error) return `${reason.name}: ${reason.message}`
  if (typeof reason === 'string') return reason
  try {
    return JSON.stringify(reason)
  } catch {
    return String(reason)
  }
}

function reasonStack(reason: unknown): string | undefined {
  return reason instanceof Error ? reason.stack : undefined
}

function redact(text: string): string {
  return text
    .replace(/(sk-[A-Za-z0-9_-]{12,})/g, '<redacted-key>')
    .replace(/(Bearer\s+)[A-Za-z0-9._-]+/gi, '$1<redacted-token>')
    .replace(/([?&](?:token|key|api_key|apikey|password|secret)=)[^&#\s]+/gi, '$1<redacted>')
    .replace(/((?:authorization|api[_-]?key|token|password|secret)\s*[:=]\s*)[^\s,;]+/gi, '$1<redacted>')
    .replace(/data:image\/[a-z0-9.+-]+;base64,[A-Za-z0-9+/=]+/gi, 'data:image/<redacted>;base64,<redacted>')
}
