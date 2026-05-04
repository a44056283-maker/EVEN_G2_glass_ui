/**
 * extractBatterySnapshot.ts — 多来源电量解析
 *
 * 从任意 payload 中提取 G2（眼镜）和 R1（戒指）电量。
 * 支持所有已知字段名称和嵌套结构。
 */

import { type BatterySnapshot } from './batteryCache'

type BatteryKeys = string[]

const TOP_LEVEL_KEYS: BatteryKeys = [
  'batteryLevel',
  'battery_level',
  'battery',
  'batteryPercent',
  'battery_percent',
  'batteryPercentage',
  'battery_percentage',
  'power',
  'powerLevel',
  'power_level',
  'charge',
  'chargeLevel',
  'charge_level',
  'capacity',
  'capacityPercent',
  'capacity_percent',
  'percent',
  'percentage',
  'soc',
  'level',
]

const GLASSES_KEYS: BatteryKeys = [
  'glassesBattery',
  'glassBattery',
  'g2Battery',
  'g2_battery',
  'glasses_battery',
  'glassesBatteryLevel',
  'glassBatteryLevel',
  'g2BatteryLevel',
  'leftGlassBattery',
  'rightGlassBattery',
]

const RING_KEYS: BatteryKeys = [
  'ringBattery',
  'r1Battery',
  'r1_battery',
  'ring_battery',
  'ringBatteryLevel',
  'r1BatteryLevel',
  'remoteBattery',
  'controllerBattery',
  'ringPower',
  'r1Power',
  'remotePower',
  'controllerPower',
]

const NESTED_KEYS = [
  'status',
  'data',
  'device',
  'devices',
  'deviceInfo',
  'deviceStatus',
  'battery',
  'batteryInfo',
  'power',
  'ring',
  'r1',
  'remote',
  'controller',
  'glasses',
  'g2',
]

function asRecord(source: unknown): Record<string, unknown> | undefined {
  if (typeof source === 'object' && source !== null) return source as Record<string, unknown>
  return undefined
}

function getJsonObject(source: unknown): Record<string, unknown> | undefined {
  const record = asRecord(source)
  if (!record) return undefined
  const json = (record as Record<string, unknown>).toJson
  if (typeof json === 'function') {
    const result = json.call(record)
    if (typeof result === 'object' && result !== null) return result as Record<string, unknown>
  }
  return undefined
}

function readNumericValue(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') {
    const parsed = parseInt(value, 10)
    if (!Number.isNaN(parsed)) return parsed
  }
  return undefined
}

function normalizeBatteryValue(value: number | undefined): number | undefined {
  if (typeof value !== 'number' || !Number.isFinite(value)) return undefined
  return Math.max(0, Math.min(100, Math.round(value)))
}

function readByKeys(record: Record<string, unknown> | undefined, keys: BatteryKeys): number | undefined {
  if (!record) return undefined
  for (const key of keys) {
    const raw = record[key]
    const numeric = readNumericValue(raw)
    if (typeof numeric === 'number') return normalizeBatteryValue(numeric)
  }
  return undefined
}

function findDeepValue(source: unknown, keys: BatteryKeys): number | undefined {
  const visited = new WeakSet<object>()
  const visit = (value: unknown, depth: number): number | undefined => {
    if (depth > 4 || typeof value !== 'object' || value === null || visited.has(value)) return undefined
    visited.add(value)
    const record = value as Record<string, unknown>
    const direct = readByKeys(record, keys)
    if (typeof direct === 'number') return direct
    for (const nestedKey of NESTED_KEYS) {
      const nested = record[nestedKey]
      const found = visit(nested, depth + 1)
      if (typeof found === 'number') return found
    }
    return undefined
  }
  return visit(source, 0)
}

function collectCandidates(source: unknown): Array<Record<string, unknown>> {
  const result: Array<Record<string, unknown>> = []
  const visited = new WeakSet<object>()
  const visit = (value: unknown, depth: number): void => {
    if (depth > 3 || typeof value !== 'object' || value === null || visited.has(value)) return
    visited.add(value)
    const record = value as Record<string, unknown>
    result.push(record)
    const json = getJsonObject(value)
    if (json && json !== value) visit(json, depth + 1)
    for (const key of NESTED_KEYS) {
      visit(record[key], depth + 1)
    }
  }
  visit(source, 0)
  return result
}

/**
 * 从任意输入中提取电量快照。
 * 同时尝试找眼镜电量和戒指电量。
 */
export function extractBatterySnapshot(input: unknown): BatterySnapshot {
  const snapshot: BatterySnapshot = {}

  // 1. 如果输入本身就有明确的眼镜/戒指字段，直接拆解
  const candidates = collectCandidates(input)
  for (const candidate of candidates) {
    if (snapshot.glasses === undefined) {
      snapshot.glasses = normalizeBatteryValue(readByKeys(candidate, GLASSES_KEYS))
    }
    if (snapshot.ring === undefined) {
      snapshot.ring = normalizeBatteryValue(readByKeys(candidate, RING_KEYS))
    }
  }

  // 2. 如果没有找到眼镜/戒指特定字段，尝试顶层通用字段
  if (snapshot.glasses === undefined && snapshot.ring === undefined) {
    for (const candidate of candidates) {
      const topLevel = readByKeys(candidate, TOP_LEVEL_KEYS)
      if (typeof topLevel === 'number') {
        // 根据 SN 或其他特征判断是眼镜还是戒指
        snapshot.glasses = topLevel
        break
      }
    }
  }

  return snapshot
}

/**
 * 从单一来源提取顶层电量值（用于通用字段）
 */
export function extractTopLevelBattery(input: unknown): number | undefined {
  const record = asRecord(input)
  if (!record) return undefined
  const direct = readByKeys(record, TOP_LEVEL_KEYS)
  if (typeof direct === 'number') return direct
  const json = getJsonObject(input)
  if (json) {
    const fromJson = readByKeys(json, TOP_LEVEL_KEYS)
    if (typeof fromJson === 'number') return fromJson
    const nested = readByKeys(json['status'] as Record<string, unknown>, TOP_LEVEL_KEYS)
    if (typeof nested === 'number') return nested
  }
  return findDeepValue(input, TOP_LEVEL_KEYS)
}
