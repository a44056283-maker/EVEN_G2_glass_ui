import type { EvenHubEvent } from '@evenrealities/even_hub_sdk'
import { formatInputEventForLog, normalizeEvenInputEvent } from '../input/normalizeEvenInputEvent'

export function formatGlassInputDebug(event: EvenHubEvent, state: string): string {
  const lines = normalizeEvenInputEvent(event).map((item) => formatInputEventForLog(item, state))
  return lines.length > 0 ? lines[0] : `Envelope: none\nType: unknown\nSource: unknown\nState: ${state}`
}
