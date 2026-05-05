export interface LocationContext {
  enabled: boolean
  status: 'disabled' | 'ready' | 'denied' | 'timeout' | 'unavailable' | 'error'
  capturedAt?: string
  approximate?: string
  accuracyMeters?: number
  message?: string
}

const CACHE_TTL_MS = 5 * 60 * 1000
const REQUEST_TIMEOUT_MS = 8000

let cachedLocation: LocationContext | undefined
let cachedAt = 0

export async function getLocationContext(enabled: boolean): Promise<LocationContext> {
  if (!enabled) return { enabled: false, status: 'disabled', message: '定位未开启' }
  if (cachedLocation && Date.now() - cachedAt < CACHE_TTL_MS) return cachedLocation
  if (!navigator.geolocation) return { enabled: true, status: 'unavailable', message: '浏览器不支持定位' }

  try {
    const position = await requestPositionWithTimeout()
    const { latitude, longitude, accuracy } = position.coords
    cachedLocation = {
      enabled: true,
      status: 'ready',
      capturedAt: new Date(position.timestamp || Date.now()).toISOString(),
      approximate: `约 ${latitude.toFixed(2)}, ${longitude.toFixed(2)}`,
      accuracyMeters: Number.isFinite(accuracy) ? Math.round(accuracy) : undefined,
      message: '定位已获取，仅用于本次视觉上下文',
    }
    cachedAt = Date.now()
    return cachedLocation
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    const status = /timeout/i.test(message) ? 'timeout' : /denied|permission/i.test(message) ? 'denied' : 'error'
    return { enabled: true, status, message }
  }
}

export function formatLocationForPrompt(location: LocationContext): string {
  if (location.status !== 'ready' || !location.approximate) {
    return `定位状态：${location.message || location.status}。定位失败不影响识图。`
  }
  return [
    `粗略位置：${location.approximate}`,
    location.accuracyMeters ? `定位精度约 ${location.accuracyMeters} 米` : '',
    location.capturedAt ? `定位时间：${location.capturedAt}` : '',
    '仅作为场景判断辅助，不要输出精确坐标。',
  ].filter(Boolean).join('；')
}

function requestPositionWithTimeout(): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    let settled = false
    let watchId: number | undefined
    const finish = (callback: () => void) => {
      if (settled) return
      settled = true
      window.clearTimeout(timer)
      if (watchId !== undefined) navigator.geolocation.clearWatch(watchId)
      callback()
    }
    const timer = window.setTimeout(() => finish(() => reject(new Error('location timeout'))), REQUEST_TIMEOUT_MS)
    const onPosition = (position: GeolocationPosition) => finish(() => resolve(position))
    const onError = (error: GeolocationPositionError) => {
      if (watchId !== undefined) finish(() => reject(new Error(error.message || 'location error')))
    }

    navigator.geolocation.getCurrentPosition(
      onPosition,
      () => {
        try {
          watchId = navigator.geolocation.watchPosition(onPosition, onError, {
            enableHighAccuracy: true,
            timeout: REQUEST_TIMEOUT_MS,
            maximumAge: CACHE_TTL_MS,
          })
        } catch (error) {
          finish(() => reject(error))
        }
      },
      {
        enableHighAccuracy: true,
        timeout: REQUEST_TIMEOUT_MS,
        maximumAge: CACHE_TTL_MS,
      },
    )
  })
}
