export interface LocationContext {
  enabled: boolean
  status: 'disabled' | 'ready' | 'denied' | 'timeout' | 'unavailable' | 'error'
  capturedAt?: string
  approximate?: string
  address?: string
  accuracyMeters?: number
  permissionState?: PermissionState | 'unsupported' | 'unknown'
  diagnostic?: string
  message?: string
}

const CACHE_TTL_MS = 5 * 60 * 1000
const REQUEST_TIMEOUT_MS = 5000
const GEOCODE_TIMEOUT_MS = 3500
const ADDRESS_CACHE_KEY = 'g2-vva-location-address-cache-v1'

let cachedLocation: LocationContext | undefined
let cachedAt = 0

export async function getLocationContext(enabled: boolean, options: { forceRefresh?: boolean; resolveAddress?: boolean } = {}): Promise<LocationContext> {
  if (!enabled) return { enabled: false, status: 'disabled', message: '定位未开启' }
  if (!options.forceRefresh && cachedLocation && Date.now() - cachedAt < CACHE_TTL_MS) return cachedLocation

  const permissionState = await getLocationPermissionState()
  if (!navigator.geolocation) {
    return {
      enabled: true,
      status: 'unavailable',
      permissionState,
      message: '浏览器不支持定位，或 Even App WebView 未暴露定位能力',
      diagnostic: buildLocationDiagnostic('unavailable', permissionState),
    }
  }

  try {
    const position = await requestPositionWithTimeout()
    const { latitude, longitude, accuracy } = position.coords
    const approximate = `约 ${latitude.toFixed(2)}, ${longitude.toFixed(2)}`
    const address = options.resolveAddress ? await reverseGeocode(latitude, longitude) : undefined
    cachedLocation = {
      enabled: true,
      status: 'ready',
      capturedAt: new Date(position.timestamp || Date.now()).toISOString(),
      approximate,
      address,
      accuracyMeters: Number.isFinite(accuracy) ? Math.round(accuracy) : undefined,
      permissionState: await getLocationPermissionState(),
      message: address ? '定位与粗略地址已获取' : '定位已获取，仅用于本次上下文',
      diagnostic: [
        '定位：OK',
        `权限：${await getLocationPermissionState()}`,
        `粗略坐标：${approximate}`,
        Number.isFinite(accuracy) ? `精度：约 ${Math.round(accuracy)} 米` : '',
        address ? `粗略地址：${address}` : '粗略地址：未解析',
      ].filter(Boolean).join('\n'),
    }
    cachedAt = Date.now()
    return cachedLocation
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    const status = /timeout/i.test(message) ? 'timeout' : /denied|permission/i.test(message) ? 'denied' : 'error'
    return {
      enabled: true,
      status,
      permissionState: await getLocationPermissionState(),
      message,
      diagnostic: buildLocationDiagnostic(status, await getLocationPermissionState(), message),
    }
  }
}

export function formatLocationForPrompt(location: LocationContext): string {
  if (location.status !== 'ready' || !location.approximate) {
    return `定位状态：${location.message || location.status}。定位失败不影响识图。`
  }
  return [
    location.address ? `粗略地址：${location.address}` : '',
    `粗略位置：${location.approximate}`,
    location.accuracyMeters ? `定位精度约 ${location.accuracyMeters} 米` : '',
    location.capturedAt ? `定位时间：${location.capturedAt}` : '',
    '仅作为场景判断辅助，不要输出精确坐标。',
  ].filter(Boolean).join('；')
}

export function formatLocationForDisplay(location: LocationContext): string {
  if (location.diagnostic) return location.diagnostic
  return [
    `定位：${location.status}`,
    `权限：${location.permissionState ?? 'unknown'}`,
    location.message ? `说明：${location.message}` : '',
    location.address ? `粗略地址：${location.address}` : '',
    location.approximate ? `粗略坐标：${location.approximate}` : '',
    location.accuracyMeters ? `精度：约 ${location.accuracyMeters} 米` : '',
    location.capturedAt ? `时间：${location.capturedAt}` : '',
  ].filter(Boolean).join('\n')
}

export function clearLocationCache(): void {
  cachedLocation = undefined
  cachedAt = 0
}

export async function getLocationPermissionState(): Promise<LocationContext['permissionState']> {
  try {
    if (!navigator.permissions?.query) return 'unsupported'
    const status = await navigator.permissions.query({ name: 'geolocation' as PermissionName })
    return status.state
  } catch {
    return 'unknown'
  }
}

function requestPositionWithTimeout(): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error('location timeout')), REQUEST_TIMEOUT_MS)
    navigator.geolocation.getCurrentPosition(
      (position) => {
        window.clearTimeout(timer)
        resolve(position)
      },
      (error) => {
        window.clearTimeout(timer)
        reject(new Error(error.message || 'location error'))
      },
      {
        enableHighAccuracy: false,
        timeout: REQUEST_TIMEOUT_MS,
        maximumAge: CACHE_TTL_MS,
      },
    )
  })
}

async function reverseGeocode(latitude: number, longitude: number): Promise<string | undefined> {
  const cacheKey = `${latitude.toFixed(3)},${longitude.toFixed(3)}`
  const cached = readAddressCache(cacheKey)
  if (cached) return cached

  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), GEOCODE_TIMEOUT_MS)
  try {
    const url = new URL('https://nominatim.openstreetmap.org/reverse')
    url.searchParams.set('format', 'jsonv2')
    url.searchParams.set('lat', String(latitude))
    url.searchParams.set('lon', String(longitude))
    url.searchParams.set('zoom', '18')
    url.searchParams.set('addressdetails', '1')
    url.searchParams.set('accept-language', navigator.language || 'zh-CN')
    const response = await fetch(url, {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return undefined
    const data = await response.json() as { display_name?: string; name?: string; address?: Record<string, string> }
    const address = compactAddress(data)
    if (address) writeAddressCache(cacheKey, address)
    return address
  } catch {
    return undefined
  } finally {
    window.clearTimeout(timer)
  }
}

function compactAddress(data: { display_name?: string; name?: string; address?: Record<string, string> }): string | undefined {
  const address = data.address ?? {}
  const parts = [
    address.country,
    address.state || address.province,
    address.city || address.town || address.county,
    address.suburb || address.neighbourhood || address.village,
    address.road || address.pedestrian,
    data.name,
  ].filter(Boolean)
  const compact = Array.from(new Set(parts)).join(' ')
  return compact || data.display_name?.split(',').slice(0, 5).map((part) => part.trim()).filter(Boolean).join(' ')
}

function readAddressCache(key: string): string | undefined {
  try {
    const cache = JSON.parse(localStorage.getItem(ADDRESS_CACHE_KEY) || '{}') as Record<string, { value: string; cachedAt: number }>
    const item = cache[key]
    if (!item || Date.now() - item.cachedAt > CACHE_TTL_MS) return undefined
    return item.value
  } catch {
    return undefined
  }
}

function writeAddressCache(key: string, value: string): void {
  try {
    const cache = JSON.parse(localStorage.getItem(ADDRESS_CACHE_KEY) || '{}') as Record<string, { value: string; cachedAt: number }>
    cache[key] = { value, cachedAt: Date.now() }
    localStorage.setItem(ADDRESS_CACHE_KEY, JSON.stringify(cache))
  } catch {
    // Address cache is best-effort only.
  }
}

function buildLocationDiagnostic(
  status: LocationContext['status'],
  permissionState: LocationContext['permissionState'],
  message?: string,
): string {
  return [
    `定位：${status}`,
    `权限：${permissionState ?? 'unknown'}`,
    message ? `原因：${message}` : '',
    status === 'denied' ? '处理：请在系统设置里允许 Even App 使用定位。' : '',
    status === 'timeout' ? '处理：请确认手机定位已开启，并在室外或网络较好处重试。' : '',
    status === 'unavailable' ? '处理：当前 WebView 未暴露 navigator.geolocation，需要 Even App 宿主支持。' : '',
  ].filter(Boolean).join('\n')
}
