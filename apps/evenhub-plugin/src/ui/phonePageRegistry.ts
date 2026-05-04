/**
 * phonePageRegistry.ts — 手机网页页面锁页机制
 *
 * 每个页面只能显示规定的区块，不允许串页。
 * 页面显示/隐藏统一由 applyPhonePageVisibility() 控制。
 */

import { type PhoneBookmarkId } from './phoneNavigation'

/** 手机网页页面所有可显示的区块 ID */
export type PhonePageSectionId =
  | 'status-panel'
  | 'vision-result-panel'
  | 'history-panel-vision'
  | 'voice-panel'
  | 'trading-panel'
  | 'config-panel'
  | 'debug-log'

/**
 * 每个书签允许显示的页面区块
 * 规则：只有这里列出的区块才允许显示
 */
export const PHONE_PAGE_SECTIONS: Record<PhoneBookmarkId, PhonePageSectionId[]> = {
  vision: ['status-panel', 'vision-result-panel', 'history-panel-vision'],
  voice: ['voice-panel'],
  trading: ['trading-panel'],
  openclaw: ['config-panel', 'debug-log'],
  diagnostics: ['debug-log'],
  history: [],
  debug: ['debug-log'],
}

/** 所有区块的 CSS 选择器 */
const ALL_SECTION_SELECTORS = [
  '[data-phone-section="status-panel"]',
  '[data-phone-section="vision-result-panel"]',
  '[data-phone-section="history-panel-vision"]',
  '[data-phone-section="voice-panel"]',
  '[data-phone-section="trading-panel"]',
  '[data-phone-section="config-panel"]',
  '[data-phone-section="debug-log"]',
].join(', ')

/**
 * 根据当前激活的书签，只显示该书签允许的区块，隐藏其余区块
 */
export function applyPhonePageVisibility(activeBookmark: PhoneBookmarkId): void {
  const allowedSections = PHONE_PAGE_SECTIONS[activeBookmark] ?? []
  const app = document.querySelector<HTMLElement>('#app')
  if (!app) return

  // 先全部隐藏
  for (const section of document.querySelectorAll<HTMLElement>(ALL_SECTION_SELECTORS)) {
    section.classList.remove('is-visible')
    section.style.display = 'none'
  }

  // 再显示允许的区块
  for (const sectionId of allowedSections) {
    const section = document.querySelector<HTMLElement>(`[data-phone-section="${sectionId}"]`)
    if (section) {
      section.classList.add('is-visible')
      section.style.display = ''
    }
  }
}

/**
 * 获取某个书签是否允许显示某个区块
 */
export function isSectionAllowedForBookmark(bookmark: PhoneBookmarkId, section: PhonePageSectionId): boolean {
  return PHONE_PAGE_SECTIONS[bookmark]?.includes(section) ?? false
}
