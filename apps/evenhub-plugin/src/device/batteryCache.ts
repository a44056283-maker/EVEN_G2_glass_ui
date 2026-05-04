/**
 * batteryCache.ts — G2 / R1 电量本地缓存
 *
 * 任何一次拿到有效电量时写缓存，页面刷新后先显示缓存值，避免长期显示 "--%"
 */

export type BatterySnapshot = {
  glasses?: number
  ring?: number
  updatedAt?: string
  source?: string
}

const CACHE_KEY = 'g2vva-battery-v2'

let _cache: BatterySnapshot = {
  glasses: undefined,
  ring: undefined,
  updatedAt: undefined,
  source: undefined,
}

export function getBatteryCache(): BatterySnapshot {
  return { ..._cache }
}

export function setBatteryCache(snapshot: BatterySnapshot, source: string): BatterySnapshot {
  const now = new Date()
  _cache = {
    glasses: snapshot.glasses ?? _cache.glasses,
    ring: snapshot.ring ?? _cache.ring,
    updatedAt: now.toLocaleTimeString('zh-CN'),
    source,
  }
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(_cache))
  } catch {
    // localStorage may be unavailable
  }
  return _cache
}

export function loadBatteryCache(): BatterySnapshot {
  try {
    const raw = localStorage.getItem(CACHE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as BatterySnapshot
      if (parsed && (typeof parsed.glasses === 'number' || typeof parsed.ring === 'number')) {
        _cache = parsed
        return _cache
      }
    }
  } catch {
    // ignore parse errors
  }
  return _cache
}

export function clearBatteryCache(): void {
  _cache = { glasses: undefined, ring: undefined, updatedAt: undefined, source: undefined }
  try {
    localStorage.removeItem(CACHE_KEY)
  } catch {
    // ignore
  }
}
