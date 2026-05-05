export interface AppConfig {
  apiBase: string
  ttsVoiceId: string
  g2RecordMs: number
  autoSpeak: boolean
  autoListenOnStart: boolean
  enableLocationContext: boolean
}

export const defaultConfig: AppConfig = {
  apiBase: import.meta.env.VITE_API_BASE ?? 'https://g2-vision.tianlu2026.org',
  ttsVoiceId: 'female-shaonv',
  g2RecordMs: 120000,
  autoSpeak: true,
  autoListenOnStart: false,
  enableLocationContext: false,
}

const storageKey = 'g2-vva-config-v2'

export function getAppConfig(): AppConfig {
  try {
    const raw = localStorage.getItem(storageKey)
    if (!raw) return defaultConfig
    return normalizeConfig(JSON.parse(raw) as Partial<AppConfig>)
  } catch {
    return defaultConfig
  }
}

export function saveAppConfig(config: Partial<AppConfig>): AppConfig {
  const next = normalizeConfig(config)
  localStorage.setItem(storageKey, JSON.stringify(next))
  return next
}

export function resetAppConfig(): AppConfig {
  localStorage.removeItem(storageKey)
  return defaultConfig
}

function normalizeConfig(config: Partial<AppConfig>): AppConfig {
  const apiBase = String(config.apiBase || defaultConfig.apiBase).replace(/\/+$/, '')
  const ttsVoiceId = String(config.ttsVoiceId || defaultConfig.ttsVoiceId).trim() || defaultConfig.ttsVoiceId
  const g2RecordMs = clampNumber(Number(config.g2RecordMs || defaultConfig.g2RecordMs), 1500, 120000)

  return {
    apiBase,
    ttsVoiceId,
    g2RecordMs,
    autoSpeak: config.autoSpeak ?? defaultConfig.autoSpeak,
    autoListenOnStart: config.autoListenOnStart ?? defaultConfig.autoListenOnStart,
    enableLocationContext: config.enableLocationContext ?? defaultConfig.enableLocationContext,
  }
}

function clampNumber(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return defaultConfig.g2RecordMs
  return Math.max(min, Math.min(max, Math.round(value)))
}
