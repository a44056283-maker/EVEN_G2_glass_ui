import type { HistoryItem } from './history'
import { getBridge } from './bridge'

const DB_NAME = 'g2-vva-history-db'
const STORE_NAME = 'history'
const DB_VERSION = 1
const BRIDGE_HISTORY_KEY = 'g2-vva-history-v2'

function hasIndexedDb(): boolean {
  return typeof indexedDB !== 'undefined'
}

function openHistoryDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (!hasIndexedDb()) {
      reject(new Error('IndexedDB unavailable'))
      return
    }

    const request = indexedDB.open(DB_NAME, DB_VERSION)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' })
        store.createIndex('createdAt', 'createdAt')
        store.createIndex('kind', 'kind')
      }
    }
    request.onerror = () => reject(request.error ?? new Error('IndexedDB open failed'))
    request.onsuccess = () => resolve(request.result)
  })
}

export async function loadIndexedHistory(): Promise<HistoryItem[]> {
  const db = await openHistoryDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly')
    const request = tx.objectStore(STORE_NAME).getAll()
    request.onerror = () => reject(request.error ?? new Error('IndexedDB read failed'))
    request.onsuccess = () => {
      const items = Array.isArray(request.result) ? (request.result as HistoryItem[]) : []
      resolve(items.sort((a, b) => b.createdAt.localeCompare(a.createdAt)))
    }
    tx.oncomplete = () => db.close()
    tx.onerror = () => {
      db.close()
      reject(tx.error ?? new Error('IndexedDB transaction failed'))
    }
  })
}

export async function loadBridgeHistory(): Promise<HistoryItem[]> {
  const bridge = getBridge()
  if (!bridge) return []
  const raw = await bridge.getLocalStorage(BRIDGE_HISTORY_KEY)
  if (!raw) return []
  const parsed = JSON.parse(raw)
  return Array.isArray(parsed) ? parsed as HistoryItem[] : []
}

export async function saveBridgeHistory(items: HistoryItem[]): Promise<boolean> {
  const bridge = getBridge()
  if (!bridge) return false
  return bridge.setLocalStorage(BRIDGE_HISTORY_KEY, JSON.stringify(items))
}

export async function clearBridgeHistory(): Promise<boolean> {
  const bridge = getBridge()
  if (!bridge) return false
  return bridge.setLocalStorage(BRIDGE_HISTORY_KEY, '')
}

export async function saveIndexedHistory(items: HistoryItem[]): Promise<void> {
  const db = await openHistoryDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    store.clear()
    for (const item of items) store.put(item)
    tx.oncomplete = () => {
      db.close()
      resolve()
    }
    tx.onerror = () => {
      db.close()
      reject(tx.error ?? new Error('IndexedDB write failed'))
    }
  })
}

export async function clearIndexedHistory(): Promise<void> {
  const db = await openHistoryDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    tx.objectStore(STORE_NAME).clear()
    tx.oncomplete = () => {
      db.close()
      resolve()
    }
    tx.onerror = () => {
      db.close()
      reject(tx.error ?? new Error('IndexedDB clear failed'))
    }
  })
}
