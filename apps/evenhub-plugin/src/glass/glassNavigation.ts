/**
 * glassNavigation.ts — G2 眼镜端导航配置（独立于手机网页 UI）
 *
 * G2 眼镜端主菜单显示四项：视觉识别 / 呼叫天禄 / 交易状态 / 系统设置
 * 不显示：OpenCLAW、相册、连接扫描、权限自检、设备诊断等（这些只在手机网页）。
 *
 * 不要把此文件用于手机网页 DOM 渲染。
 */

export type GlassBookmarkId = 'vision' | 'voice' | 'trading' | 'settings'

export interface GlassBookmark {
  id: GlassBookmarkId
  title: string
  controlId: string
  action: string
}

export const glassBookmarks: GlassBookmark[] = [
  { id: 'vision', title: '视觉识别', controlId: 'capture-button', action: '单击拍照识别' },
  { id: 'voice', title: '呼叫天禄', controlId: 'voice-button', action: '单击开始语音问答' },
  { id: 'trading', title: '交易状态', controlId: 'trading-button', action: '单击刷新交易只读' },
  { id: 'settings', title: '系统设置', controlId: 'settings-button', action: '单击进入系统设置' },
]

export function getGlassBookmarkById(id: GlassBookmarkId): GlassBookmark | undefined {
  return glassBookmarks.find((b) => b.id === id)
}

export function getGlassBookmarkIndex(id: GlassBookmarkId): number {
  return glassBookmarks.findIndex((b) => b.id === id)
}
