import { type EvenAppBridge, waitForEvenAppBridge } from '@evenrealities/even_hub_sdk'

let bridge: EvenAppBridge | undefined

export async function initBridge(): Promise<EvenAppBridge | undefined> {
  try {
    bridge = await waitForEvenAppBridge()
    return bridge
  } catch (error) {
    console.warn('Even bridge unavailable; browser debug mode enabled.', error)
    return undefined
  }
}

export function getBridge(): EvenAppBridge | undefined {
  return bridge
}
