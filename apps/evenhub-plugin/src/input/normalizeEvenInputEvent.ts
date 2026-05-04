import { EventSourceType, OsEventTypeList } from '@evenrealities/even_hub_sdk'

export type NormalizedInputEvent = {
  type: number
  source?: unknown
  envelope: 'sysEvent' | 'textEvent' | 'listEvent'
}

export function normalizeEvenInputEvent(event: any): NormalizedInputEvent[] {
  const result: NormalizedInputEvent[] = []

  if (event.sysEvent) {
    result.push({
      type: event.sysEvent.eventType ?? OsEventTypeList.CLICK_EVENT,
      source: event.sysEvent.eventSource,
      envelope: 'sysEvent',
    })
  }

  if (event.textEvent) {
    result.push({
      type: event.textEvent.eventType ?? OsEventTypeList.CLICK_EVENT,
      source: event.textEvent.eventSource,
      envelope: 'textEvent',
    })
  }

  if (event.listEvent) {
    result.push({
      type: event.listEvent.eventType ?? OsEventTypeList.CLICK_EVENT,
      source: event.listEvent.eventSource,
      envelope: 'listEvent',
    })
  }

  return result
}

export function formatInputEventForLog(event: NormalizedInputEvent, state: string): string {
  return [
    `Envelope: ${event.envelope}`,
    `Type: ${eventTypeLabel(event.type)}`,
    `Source: ${sourceLabel(event.source)}`,
    `State: ${state}`,
  ].join('\n')
}

export function eventTypeLabel(type: number): string {
  if (type === OsEventTypeList.CLICK_EVENT) return '0 CLICK'
  if (type === OsEventTypeList.SCROLL_TOP_EVENT) return '1 UP'
  if (type === OsEventTypeList.SCROLL_BOTTOM_EVENT) return '2 DOWN'
  if (type === OsEventTypeList.DOUBLE_CLICK_EVENT) return '3 DOUBLE'
  if (type === OsEventTypeList.FOREGROUND_ENTER_EVENT) return '4 ENTER'
  if (type === OsEventTypeList.FOREGROUND_EXIT_EVENT) return '5 EXIT'
  if (type === OsEventTypeList.SYSTEM_EXIT_EVENT) return '7 SYS_EXIT'
  if (type === OsEventTypeList.IMU_DATA_REPORT) return '8 IMU'
  return String(type)
}

export function sourceLabel(source: unknown): string {
  const normalized = EventSourceType.fromJson(source)
  if (normalized === EventSourceType.TOUCH_EVENT_FROM_RING) return 'R1 ring'
  if (normalized === EventSourceType.TOUCH_EVENT_FROM_GLASSES_R) return 'G2 right'
  if (normalized === EventSourceType.TOUCH_EVENT_FROM_GLASSES_L) return 'G2 left'
  if (normalized === EventSourceType.TOUCH_EVENT_FORM_DUMMY_NULL) return 'unknown'
  return safeJson(source)
}

function safeJson(value: unknown): string {
  if (value === undefined) return 'undefined'
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}
