/**
 * phoneUiState.ts — 手机网页 UI 状态单一真相源
 *
 * 规则：
 * - #app.dataset.activeBookmark 只能由此文件中的函数修改
 * - 手机网页 tab 点击只能调用 setPhoneActiveBookmark()
 * - 不得在 tab 点击时触发 G2/语音/交易业务逻辑
 */

import { type PhoneBookmarkId, phoneBookmarks } from './phoneNavigation'
import { PHONE_PAGE_SECTIONS, applyPhonePageVisibility } from './phonePageRegistry'

// 当前激活的手机书签
let _phoneActiveBookmarkId: PhoneBookmarkId = 'vision'

/** 获取当前激活的手机书签 ID */
export function getPhoneActiveBookmarkId(): PhoneBookmarkId {
  return _phoneActiveBookmarkId
}

/**
 * 设置手机网页激活书签（唯一合法修改 dataset.activeBookmark 的途径）
 * 同时更新 tab 高亮和页面显示
 */
export function setPhoneActiveBookmark(id: PhoneBookmarkId): void {
  _phoneActiveBookmarkId = id
  syncPhoneBookmarkDom()
}

/** 将手机书签状态同步到 DOM（CSS 显示/隐藏依赖于 dataset.activeBookmark） */
export function syncPhoneBookmarkDom(): void {
  const app = document.querySelector<HTMLElement>('#app')
  if (!app) return

  // 单一真相源：只在这里设置 dataset.activeBookmark
  app.dataset.activeBookmark = _phoneActiveBookmarkId

  // 更新 tab 高亮状态
  updatePhoneTabActiveState(_phoneActiveBookmarkId)

  // 应用页面可见性（根据 PHONE_PAGE_SECTIONS 显示/隐藏区块）
  applyPhonePageVisibility(_phoneActiveBookmarkId)

  // 更新书签卡片信息
  renderPhoneBookmarkCard(_phoneActiveBookmarkId)
}

/** 更新 tab 按钮高亮状态 */
export function updatePhoneTabActiveState(id: PhoneBookmarkId): void {
  const bm = phoneBookmarks.find((b) => b.id === id)
  if (!bm) return

  for (const button of document.querySelectorAll<HTMLButtonElement>('.bookmark-tab')) {
    const isActive = button.id === bm.controlId
    button.classList.toggle('bookmark-active', isActive)
    button.setAttribute('aria-current', isActive ? 'true' : 'false')
  }
}

/** 更新书签卡片内容 */
export function renderPhoneBookmarkCard(id: PhoneBookmarkId): void {
  const bm = phoneBookmarks.find((b) => b.id === id)
  if (!bm) return

  const phoneIndex = phoneBookmarks.findIndex((b) => b.id === id)
  const kicker = document.querySelector('#bookmark-kicker')
  const title = document.querySelector('#bookmark-title')
  const desc = document.querySelector('#bookmark-desc')
  const action = document.querySelector('#bookmark-action')

  if (kicker) kicker.textContent = `书签 ${phoneIndex + 1} / ${phoneBookmarks.length}`
  if (title) title.textContent = bm.title
  if (desc) desc.textContent = bm.action
  if (action) {
    // action 按钮文字根据页面不同显示不同提示
    if (id === 'vision') action.textContent = 'R1 上下切换，单击执行'
    else if (id === 'voice') action.textContent = '按住说话，松开识别'
    else if (id === 'trading') action.textContent = '单击刷新状态'
    else if (id === 'openclaw') action.textContent = 'R1 单击扫描，上下滑动'
    else if (id === 'history') action.textContent = '查看全部历史与分类历史'
  }
}

/** 初始化手机网页 UI 状态（在 DOMReady 时调用） */
export function initPhoneUiState(): void {
  syncPhoneBookmarkDom()
}
