import type { EvenHubEvent } from '@evenrealities/even_hub_sdk'
import { formatInputEventForLog, normalizeEvenInputEvent } from '../input/normalizeEvenInputEvent'

export function formatGlassInputDebug(event: EvenHubEvent, state: string): string {
  const lines = normalizeEvenInputEvent(event).map((item) => formatInputEventForLog(item, state))
  return lines.length ? lines.join('\n') : `no normalized input\nstate=${state}`
}
