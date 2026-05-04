import { type EvenHubEvent, OsEventTypeList } from '@evenrealities/even_hub_sdk'
import { normalizeEvenInputEvent } from './input/normalizeEvenInputEvent'

type ControlDirection = 'next' | 'previous'
export type ControlIntent = 'click' | 'double_click' | 'next' | 'previous'

export function isClickEvent(event: EvenHubEvent): boolean {
  if (normalizeEvenInputEvent(event).some((item) => item.type === OsEventTypeList.CLICK_EVENT)) return true

  const textType = normalizeEventType(event.textEvent?.eventType)
  if (event.textEvent && (textType === OsEventTypeList.CLICK_EVENT || textType === undefined)) return true

  const sysType = normalizeEventType(event.sysEvent?.eventType)
  if (event.sysEvent && (sysType === OsEventTypeList.CLICK_EVENT || sysType === undefined)) return true

  const listType = normalizeEventType(event.listEvent?.eventType)
  if (event.listEvent && (listType === OsEventTypeList.CLICK_EVENT || listType === undefined)) return true

  return false
}

export function getControlDirection(event: EvenHubEvent): ControlDirection | undefined {
  const normalized = normalizeEvenInputEvent(event)
  if (normalized.some((item) => item.type === OsEventTypeList.SCROLL_BOTTOM_EVENT)) return 'next'
  if (normalized.some((item) => item.type === OsEventTypeList.SCROLL_TOP_EVENT)) return 'previous'

  const eventType = [
    event.listEvent?.eventType,
    event.textEvent?.eventType,
    event.sysEvent?.eventType,
    readLooseEventType(event.jsonData),
  ]
    .map(normalizeEventType)
    .find((item) => item !== undefined)

  if (eventType === OsEventTypeList.SCROLL_BOTTOM_EVENT) return 'next'
  if (eventType === OsEventTypeList.SCROLL_TOP_EVENT) return 'previous'

  const loose = [
    event.listEvent?.currentSelectItemName,
    readLooseValue(event.jsonData, 'gesture'),
    readLooseValue(event.jsonData, 'direction'),
    readLooseValue(event.jsonData, 'action'),
    readLooseValue(event.jsonData, 'key'),
  ]
    .filter((item) => item !== undefined && item !== null)
    .join(' ')
    .toUpperCase()

  if (/(NEXT|RIGHT|DOWN|FORWARD|CLOCKWISE|CW|下|右|后|顺)/.test(loose)) return 'next'
  if (/(PREV|PREVIOUS|LEFT|UP|BACK|COUNTER|CCW|上|左|前|逆)/.test(loose)) return 'previous'
  return undefined
}

export function getControlIntent(event: EvenHubEvent): ControlIntent | undefined {
  const normalized = normalizeEvenInputEvent(event)
  if (normalized.some((item) => item.type === OsEventTypeList.DOUBLE_CLICK_EVENT)) return 'double_click'
  if (normalized.some((item) => item.type === OsEventTypeList.SCROLL_BOTTOM_EVENT)) return 'next'
  if (normalized.some((item) => item.type === OsEventTypeList.SCROLL_TOP_EVENT)) return 'previous'
  if (normalized.some((item) => item.type === OsEventTypeList.CLICK_EVENT)) return 'click'
  const direction = getControlDirection(event)
  if (direction) return direction
  return isClickEvent(event) ? 'click' : undefined
}

function normalizeEventType(raw: unknown): OsEventTypeList | undefined {
  if (raw === undefined || raw === null) return undefined
  const normalized = OsEventTypeList.fromJson(raw)
  if (normalized !== undefined) return normalized

  const text = String(raw).toUpperCase()
  if (text.includes('SCROLL_BOTTOM') || text.includes('BOTTOM') || text.includes('DOWN') || text.includes('NEXT')) {
    return OsEventTypeList.SCROLL_BOTTOM_EVENT
  }
  if (text.includes('SCROLL_TOP') || text.includes('TOP') || text.includes('UP') || text.includes('PREVIOUS')) {
    return OsEventTypeList.SCROLL_TOP_EVENT
  }
  if (text.includes('DOUBLE')) return OsEventTypeList.DOUBLE_CLICK_EVENT
  if (text.includes('CLICK') || text.includes('TAP')) return OsEventTypeList.CLICK_EVENT
  return undefined
}

function readLooseEventType(jsonData: Record<string, unknown> | undefined): unknown {
  if (!jsonData) return undefined
  return (
    jsonData.eventType ??
    jsonData.Event_Type ??
    jsonData.event_type ??
    jsonData.type ??
    (typeof jsonData.data === 'object' && jsonData.data ? (jsonData.data as Record<string, unknown>).eventType : undefined)
  )
}

function readLooseValue(jsonData: Record<string, unknown> | undefined, key: string): unknown {
  if (!jsonData) return undefined
  const direct = jsonData[key]
  if (direct !== undefined) return direct
  const data = typeof jsonData.data === 'object' && jsonData.data ? (jsonData.data as Record<string, unknown>) : undefined
  return data?.[key]
}
