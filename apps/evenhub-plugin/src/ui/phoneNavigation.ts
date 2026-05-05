/**
 * phoneNavigation.ts — 手机网页导航配置（独立于 Glass UI）
 *
 * 手机网页可以显示：vision / voice / trading / settings / diagnostics / history / debug
 * G2 眼镜端只能显示：vision / voice / trading
 *
 * 不要把此文件用于 G2 眼镜端渲染。
 */

export type PhoneBookmarkId =
  | 'vision'
  | 'voice'
  | 'trading'
  | 'openclaw'
  | 'diagnostics'
  | 'history'
  | 'debug'

export interface PhoneBookmark {
  id: PhoneBookmarkId
  title: string
  controlId: string
  action: string
  /** 手机面板 CSS data-active-bookmark 值 */
  cssValue: string
}

export const phoneBookmarks: PhoneBookmark[] = [
  {
    id: 'vision',
    title: '视觉识别',
    controlId: 'capture-button',
    action: '单击拍照识别',
    cssValue: 'vision',
  },
  {
    id: 'voice',
    title: '呼叫天禄',
    controlId: 'voice-button',
    action: '单击开始语音问答',
    cssValue: 'voice',
  },
  {
    id: 'trading',
    title: '交易状态',
    controlId: 'trading-button',
    action: '单击刷新交易只读',
    cssValue: 'trading',
  },
  {
    id: 'openclaw',
    title: '设置',
    controlId: 'openclaw-button',
    action: '连接诊断、权限自检、配置保存',
    cssValue: 'openclaw',
  },
  {
    id: 'history',
    title: '历史记录',
    controlId: 'history-button',
    action: '查看视觉、语音、交易、OpenCLAW 和全部历史',
    cssValue: 'history',
  },
]

/** 根据 id 查找手机书签 */
export function getPhoneBookmarkById(id: PhoneBookmarkId): PhoneBookmark | undefined {
  return phoneBookmarks.find((b) => b.id === id)
}

/** 根据 controlId 查找手机书签 */
export function getPhoneBookmarkByControlId(controlId: string): PhoneBookmark | undefined {
  return phoneBookmarks.find((b) => b.controlId === controlId)
}

/** 获取手机书签在数组中的索引（1-based，用于显示"书签 N / 4"） */
export function getPhoneBookmarkIndex(id: PhoneBookmarkId): number {
  const index = phoneBookmarks.findIndex((b) => b.id === id)
  return index >= 0 ? index + 1 : -1
}
