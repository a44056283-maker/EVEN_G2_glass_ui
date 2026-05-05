import { type DeviceInfo, type DeviceStatus, type EvenHubEvent } from '@evenrealities/even_hub_sdk'
import {
  askAssistant,
  askOpenClaw,
  getAsrStatus,
  getOpenClawStatus,
  getTradingOverview,
  recognizeImage,
  requestTts,
  transcribePhoneAudio,
} from './api'
import type { TradingReadonlyOverview } from '@g2vva/shared'
import { getBridge, initBridge } from './bridge'
import { loadBatteryCache, setBatteryCache, getBatteryCache, type BatterySnapshot } from './device/batteryCache'
import { extractBatterySnapshot } from './device/extractBatterySnapshot'
import {
  capturePhoto,
  capturePreparedPhoto,
  imageFileToCapturedImage,
  isFileInputRequestActive,
  selectPhotoFromAlbum,
  type CapturedImage,
  prepareCameraSession,
} from './camera'
import {
  captureFrameFromVisionEngine,
  getVisionEngineState,
  isVisionEngineReady,
  startVisionEngineFromPhoneGesture,
} from './camera/visionEngine'
import { getAppConfig, resetAppConfig, saveAppConfig } from './config'
import { formatForG2, getGlassBatteryText, setDeviceBatteryLevels, showBookmarkOnG2, showOnG2, startWebClock } from './display'
import { getControlDirection, getControlIntent, isClickEvent } from './events'
import { addHistory, clearHistory, initHistoryStorage, renderHistory, updateHistoryItem } from './history'
import { formatInputEventForLog, normalizeEvenInputEvent } from './input/normalizeEvenInputEvent'
import {
  clearLocationCache,
  formatLocationForDisplay,
  formatLocationForPrompt,
  getLocationContext,
  getLocationPermissionState,
} from './locationContext'
import { installRuntimeErrorReporter, recordRuntimeError } from './runtimeErrorReporter'
import { speakResponse, speakWithBrowser, stopSpeechPlayback, unlockAudioPlayback } from './speech'
import { GlassRenderer } from './glass/GlassRenderer'
import { startGlassMicProbe } from './glass/glassMicProbe'
import { formatGlassInputDebug } from './glass/glassInputDebug'
import { glassBookmarks, type GlassBookmarkId } from './glass/glassNavigation'
import { type PhoneBookmarkId, phoneBookmarks, getPhoneBookmarkById } from './ui/phoneNavigation'
import {
  setPhoneActiveBookmark,
  syncPhoneBookmarkDom,
  updatePhoneTabActiveState,
  renderPhoneBookmarkCard,
} from './ui/phoneUiState'
import { applyPhonePageVisibility } from './ui/phonePageRegistry'
import {
  startG2PcmVoiceSession,
  type ActiveG2PcmVoiceSession,
  type G2PcmVoiceDebugState,
  type StopReason,
  type VoiceSessionMode,
} from './voice/g2PcmVoiceSession'
import { startPhoneMicRecorder, type ActivePhoneMicRecorder } from './voice/phoneMicRecorder'
import './style.css'

const initialText = formatForG2('天禄助手', '视觉识别\n呼叫天禄\n交易状态')
const stepOrder = ['capture', 'compress', 'upload', 'vision', 'speak'] as const
type StepId = (typeof stepOrder)[number]
type G2BookmarkId = GlassBookmarkId
type VisionState = 'idle' | 'preparing' | 'camera_ready' | 'captured' | 'uploading' | 'result' | 'error'
type VoiceTarget = 'assistant' | 'openclaw'
type RuntimeMode = 'browser-desktop' | 'browser-mobile' | 'even-webview' | 'even-bridge'
type VoiceDebugState = {
  voicePageState: 'idle' | 'probe' | 'listening' | 'recording' | 'finalizing' | 'transcribing' | 'answer' | 'error' | 'no_pcm'
  micSource: 'none' | 'g2' | 'phone'
  wsStatus: 'idle' | 'connecting' | 'open' | 'error' | 'closed'
  audioControlCalled: boolean
  audioControlError: string
  totalBytes: number
  chunks: number
  lastChunkBytes: number
  lastChunkAt: string
  noPcmTimeout: boolean
  lastServerAudioDebug: string
  lastVoiceError: string
  holdStartedAt?: string
  elapsedMs?: number
  maxDurationMs?: number
  remainingMs?: number
  stopReason?: string
  lastTranscript?: string
  normalizedTranscript?: string
  lastIntent?: string
  lastAnswer?: string
  fallbackUsed?: string
}

interface RuntimeCapabilities {
  mode: RuntimeMode
  label: string
  hasBridge: boolean
  canUseR1: boolean
  canUseG2Mic: boolean
  canRequestPhoneCamera: boolean
  canRequestPhoneMic: boolean
  cameraStrategy: string
  micStrategy: string
}

// g2Bookmarks 统一使用 glassNavigation.ts 中定义的 glassBookmarks
const g2Bookmarks = glassBookmarks

let flowStartedAt = 0
let timerId: number | undefined
let lastVisionSummary = ''
let lastVisionAnswer = ''
let lastVisionPrompt = ''
let pendingVisionPrompt = ''
let tradingPanelActive = false
let tradingSubPageIndex = 0 // 0=总览 1=价格 2=持仓 3=分布 4=归因 5=告警
let inTradingMenu = true // true=显示菜单 false=显示子页面
let lastTradingOverview: TradingReadonlyOverview | null = null
const TRADING_CACHE_TTL_MS = 15_000
let lastTradingFetchedAt = 0
let tradingRefreshPromise: Promise<TradingReadonlyOverview> | undefined
// 每个子页面独立缓存，只包含该页所需数据
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let tradingSubPageCache: Array<{ extendedData?: any; tradingState?: any } | null> = []
let switchingSubPage = false // 防止切换子页面时快速触发

// TTS 状态跟踪
let lastTtsMethod: 'minimax-tts' | 'browser-fallback' | 'none' | null = null
let lastTtsError: string | null = null
let lastTtsOk: boolean | null = null

function buildExtendedData(live: NonNullable<TradingReadonlyOverview['live']> | undefined) {
  return live ? {
    prices: live.whitelistPrices?.map((p) => ({ symbol: p.symbol, pair: p.pair, price: p.price, freshness: p.freshness })),
    positions: live.openPositionPairs?.map((p) => ({ pair: p.pair, pnl: p.pnl, notional: p.notional, share: p.share, maxLeverage: p.maxLeverage })),
    distribution: live.pairConcentration?.map((d) => ({ pair: d.pair, share: d.share * 100, pnl: d.pnl })),
    attribution: live.attribution ? {
      winRatePct: live.attribution.winRatePct,
      avgRealizedPnlPct: live.attribution.avgRealizedPnlPct,
      avgUnrealizedPnlPct: live.attribution.avgUnrealizedPnlPct,
      sampleCount: live.attribution.sampleCount,
    } : undefined,
    alerts: live.alarms?.map((a) => ({ level: a.level, message: a.message, action: a.action })),
    portsOnline: live.portsOnline,
    portsTotal: live.portsTotal,
    autopilotEnabled: live.autopilotEnabled,
    riskLevel: live.riskLevel,
    riskScore: live.riskScore,
    totalUnrealizedPnl: live.totalUnrealizedPnl,
    openPositions: live.openPositions,
  } : undefined
}

function buildTradingState(live: NonNullable<TradingReadonlyOverview['live']> | undefined) {
  return {
    online: live ? (live.portsOnline ?? 0) > 0 : false,
    heartbeat: live?.marketFlow?.summary ? 'OK' : '--',
    strategy: live?.autopilotEnabled ? '自动驾驶' : '手动',
    positions: live?.openPositions ?? '--',
    orders: live?.dataSources?.length ?? '--',
    pnl: live?.totalUnrealizedPnl != null ? `${live.totalUnrealizedPnl >= 0 ? '+' : ''}${live.totalUnrealizedPnl.toFixed(2)}` : '--',
    risk: live?.riskLevel ?? '--',
  }
}
let selectedControlIndex = 0
let voiceCameraReadyPromise: Promise<boolean> | undefined
let autoVoiceDetectionEnabled = false
let autoVoiceDetectionRunning = false
let lastSpeakText = ''
let lastSpokenText = ''
let lastSpokenAt = 0
let voiceInputAvailable = false
let lastControlEventAt = 0
let g2BookmarkIndex = 0
/** 手机网页当前激活的书签，独立于 g2BookmarkIndex（眼镜端 ring 导航） */
let phoneActiveBookmarkId: PhoneBookmarkId = 'vision'
let visionState: VisionState = 'idle'
let activeGlassPage: 'home' | 'vision' | 'voice' | 'trading' | 'settings' | 'diagnostics' = 'home'
/** 眼镜端异步操作 session ID，用于防止旧操作结果覆盖新页面状态 */
let glassOperationId = 0
/** 生成新的 session ID 并返回，用于标记当前异步操作的合法性 */
function startGlassOperation(): number {
  return ++glassOperationId
}
/** 检查给定的 session ID 是否仍然是当前最新操作，否者说明页面已切换应忽略 */
function isGlassOperationValid(id: number): boolean {
  return id === glassOperationId
}
/** 取消当前眼镜端异步操作，清空状态并可选显示提示 */
async function cancelCurrentGlassOperation(reason: string): Promise<void> {
  const bridge = getBridge()
  const renderer = createGlassRenderer(bridge)
  console.info('[P0 vision] operation cancelled:', reason)
  // 使当前 session 失效，阻止旧结果回写
  startGlassOperation()
  pendingCapturedImage = undefined
  uploadInFlight = false
  pendingVisionPrompt = ''
  const prevState = visionState
  visionState = 'idle'
  activeGlassPage = 'home'
  // 如果当时正在 preparing/uploading，取消后返回首页
  if (prevState === 'preparing' || prevState === 'uploading') {
    await safeGlassShow(renderer, 'home')
    await renderG2Bookmark()
  }
  setInteractionFeedback(`已取消：${reason}`)
  renderR1CameraDebug()
}
let voicePageState: VoiceDebugState['voicePageState'] = 'idle'
let pendingCapturedImage: CapturedImage | undefined
let lastR1InputSummary = 'none'
let lastCaptureAt = ''
let lastCapturedAt = 0
let lastUploadAt = ''
let lastUploadSource = ''
let lastVisionError = ''
let uploadInFlight = false
let stopActiveG2MicStream: (() => Promise<void>) | undefined
let stopActiveGlassMicProbe: (() => Promise<void>) | undefined
let activeG2PcmVoiceSession: ActiveG2PcmVoiceSession | undefined
let phoneHoldRecorder: ActivePhoneMicRecorder | undefined
let phoneHoldStartedAt = 0
let phoneHoldTimer: number | undefined
let phoneHoldMaxTimer: number | undefined
let phoneHoldStopping = false
let voiceProbeDebug: VoiceDebugState = {
  voicePageState: 'idle',
  micSource: 'none',
  wsStatus: 'idle',
  audioControlCalled: false,
  audioControlError: '',
  totalBytes: 0,
  chunks: 0,
  lastChunkBytes: 0,
  lastChunkAt: '--',
  noPcmTimeout: false,
  lastServerAudioDebug: '',
  lastVoiceError: '',
}
const deviceKindBySn = new Map<string, 'glasses' | 'ring'>()
const pendingBatteryBySn = new Map<string, number | undefined>()
let runtimeCapabilities: RuntimeCapabilities = detectRuntimeCapabilities(false)

async function main(): Promise<void> {
  installRuntimeErrorReporter(() => getAppConfig().apiBase)
  startWebClock()
  bindGlobalButtonFeedback()
  bindCriticalVisionEngineButton()
  // 初始化电量显示：优先从缓存恢复，避免长期显示 "--%"
  initBatteryDisplay()
  const bridge = await initBridge()
  runtimeCapabilities = detectRuntimeCapabilities(Boolean(bridge))
  void initHistoryStorage(bridge)
  updateWebConnectionFooter()

  if (bridge) {
    await bindDeviceBattery(bridge)
    await createGlassRenderer(bridge).init('home', getGlassHomeState())
    bridge.onEvenHubEvent((event: EvenHubEvent) => {
      void handleG2ControlEvent(event)
    })
  }

  if (bridge) await showGlassHome(bridge)
  else await showOnG2(bridge, initialText)
  document.querySelector<HTMLButtonElement>('#capture-button')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    // 只切换手机页面，不触发 G2 业务逻辑
    setPhoneActiveBookmark('vision')
  })
  const handleManualImageInput = (event: Event): void => {
    if (isFileInputRequestActive()) return
    const file = (event.currentTarget as HTMLInputElement | null)?.files?.[0]
    if (!file) {
      // 文件选择取消或没有选择文件，取消当前眼镜操作
      void cancelCurrentGlassOperation('file-input-cancelled')
      return
    }
    void unlockAudioPlayback()
    const source = (event.currentTarget as HTMLInputElement | null)?.id === 'album-fallback' ? 'web-album' : 'web-camera'
    void handleManualImageFile(file, source)
  }
  document.querySelector<HTMLInputElement>('#file-fallback')?.addEventListener('change', handleManualImageInput)
  document.querySelector<HTMLInputElement>('#album-fallback')?.addEventListener('change', handleManualImageInput)
  document.querySelector<HTMLElement>('#direct-camera-label')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    setInteractionFeedback('直接拍照 已触发')
    setVisionResultPanel('等待拍照', '正在打开手机相机...', '请在手机弹出的相机界面完成拍照，返回后会自动上传识别。')
  })
  document.querySelector<HTMLElement>('#album-camera-label')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    setInteractionFeedback('相册选图 已触发')
    setVisionResultPanel('等待选图', '正在打开手机相册...', '请选择一张照片，返回后会自动上传识别。')
  })
  document.querySelector<HTMLButtonElement>('#voice-button')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    // 只切换手机页面，不触发 G2 业务逻辑
    setPhoneActiveBookmark('voice')
  })
  document.querySelector<HTMLButtonElement>('#trading-button')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    // 只切换手机页面，不触发 G2 业务逻辑
    setPhoneActiveBookmark('trading')
  })
  document.querySelector<HTMLButtonElement>('#settings-button')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    // 切换到系统设置书签，同时显示眼镜设置页
    void enterSettingsPage()
  })
  document.querySelector<HTMLButtonElement>('#openclaw-button')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    // 只切换手机页面，不触发 G2 业务逻辑
    setPhoneActiveBookmark('openclaw')
  })
  document.querySelector<HTMLButtonElement>('#history-button')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    setPhoneActiveBookmark('history')
    renderHistory()
  })
  document.querySelector<HTMLButtonElement>('#refresh-trading-button')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    selectG2Bookmark('trading')
    void runTradingOverview()
  })
  bindCriticalVisionEngineButton()
  document.querySelector<HTMLButtonElement>('#vision-capture-action')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    selectG2Bookmark('vision')
    void runCaptureFlow()
  })
  document.querySelector<HTMLButtonElement>('#vision-replay-action')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    selectG2Bookmark('vision')
    if (lastSpeakText) void speakIfEnabled(lastSpeakText, true)
  })
  bindPhoneHoldVoiceButton()
  document.querySelector<HTMLButtonElement>('#voice-preset-vision')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    selectG2Bookmark('voice')
    void runAssistantQuestion('你好天禄，帮我看一下刚才识别的内容')
  })
  document.querySelector<HTMLButtonElement>('#voice-preset-trading')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    selectG2Bookmark('voice')
    void runAssistantQuestion('你好天禄，查看一下今天收益和风险怎么样')
  })
  document.querySelector<HTMLButtonElement>('#voice-manual-action')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    selectG2Bookmark('voice')
    setInteractionFeedback('手动发送 已聚焦')
    document.querySelector<HTMLTextAreaElement>('#text-question-input')?.focus()
    document.querySelector<HTMLElement>('.voice-panel')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  })
  document.querySelector<HTMLButtonElement>('#voice-diagnostic-action')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    selectG2Bookmark('voice')
    void startVoiceDiagnosticProbe()
  })
  document.querySelector<HTMLButtonElement>('#trading-refresh-action')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    selectG2Bookmark('trading')
    void runTradingOverview()
  })
  document.querySelector<HTMLButtonElement>('#connection-scan-shortcut')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    void enterSettingsPage()
    document.querySelector<HTMLButtonElement>('#connection-scan-button')?.click()
  })
  document.querySelector<HTMLButtonElement>('#permission-check-shortcut')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    void enterSettingsPage()
    document.querySelector<HTMLButtonElement>('#permission-check-button')?.click()
  })
  document.querySelector<HTMLButtonElement>('#trading-preset-status')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    selectG2Bookmark('trading')
    void runTradingOverview()
  })
  document.querySelector<HTMLButtonElement>('#trading-preset-prices')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    selectG2Bookmark('trading')
    if (lastTradingOverview) {
      const renderer = createGlassRenderer(getBridge())
      void showTradingSubPage(1, renderer)
    } else {
      void runTradingOverview().then(() => {
        const renderer = createGlassRenderer(getBridge())
        void showTradingSubPage(1, renderer)
      })
    }
  })
  document.querySelector<HTMLButtonElement>('#trading-preset-positions')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    selectG2Bookmark('trading')
    if (lastTradingOverview) {
      const renderer = createGlassRenderer(getBridge())
      void showTradingSubPage(2, renderer)
    } else {
      void runTradingOverview().then(() => {
        const renderer = createGlassRenderer(getBridge())
        void showTradingSubPage(2, renderer)
      })
    }
  })
  document.querySelector<HTMLButtonElement>('#trading-preset-risk')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    selectG2Bookmark('trading')
    if (lastTradingOverview) {
      const renderer = createGlassRenderer(getBridge())
      void showTradingSubPage(5, renderer)
    } else {
      void runTradingOverview().then(() => {
        const renderer = createGlassRenderer(getBridge())
        void showTradingSubPage(5, renderer)
      })
    }
  })
  document.querySelector<HTMLButtonElement>('#trading-preset-distribution')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    selectG2Bookmark('trading')
    if (lastTradingOverview) {
      const renderer = createGlassRenderer(getBridge())
      void showTradingSubPage(3, renderer)
    } else {
      void runTradingOverview().then(() => {
        const renderer = createGlassRenderer(getBridge())
        void showTradingSubPage(3, renderer)
      })
    }
  })
  document.querySelector<HTMLButtonElement>('#trading-preset-attribution')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    selectG2Bookmark('trading')
    if (lastTradingOverview) {
      const renderer = createGlassRenderer(getBridge())
      void showTradingSubPage(4, renderer)
    } else {
      void runTradingOverview().then(() => {
        const renderer = createGlassRenderer(getBridge())
        void showTradingSubPage(4, renderer)
      })
    }
  })
  document.querySelector<HTMLButtonElement>('#openclaw-record-action')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    void enterSettingsPage()
    void runOpenClawFlow()
  })
  document.querySelector<HTMLButtonElement>('#openclaw-preset-trading')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    void enterSettingsPage()
    void runOpenClawQuestion('请读取交易系统状态，汇总白名单价格、机器人、持仓、收益和风险，只读分析')
  })
  document.querySelector<HTMLButtonElement>('#openclaw-preset-memory')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    void enterSettingsPage()
    void runOpenClawQuestion('请读取天禄记忆，汇总当前 G2 视觉语音助手下一步最重要的问题')
  })
  document.querySelector<HTMLButtonElement>('#confirm-camera-button')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    const prompt = pendingVisionPrompt
    pendingVisionPrompt = ''
    hideConfirmCameraButton()
    if (prompt) void runCaptureFlow(prompt)
  })
  document.querySelector<HTMLButtonElement>('#text-question-button')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    const input = document.querySelector<HTMLTextAreaElement>('#text-question-input')
    const value = input?.value.trim() ?? ''
    if (value) void routeTextQuestionFromUserAction(value)
  })
  document.querySelector<HTMLButtonElement>('#vision-followup-button')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    const input = document.querySelector<HTMLTextAreaElement>('#vision-question-input')
    const value = input?.value.trim() ?? ''
    if (value) void askVisionFollowup(value, 'vision-followup-button')
    else setVisionImageInfo('请输入要追问图片的问题，例如：这是什么？文字写了什么？')
  })
  document.querySelector<HTMLButtonElement>('#replay-speech-button')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    if (lastSpeakText) void speakIfEnabled(lastSpeakText, true)
  })
  document.querySelector<HTMLButtonElement>('#voice-followup-button')?.addEventListener('click', () => {
    void unlockAudioPlayback()
    const input = document.querySelector<HTMLTextAreaElement>('#voice-followup-input')
    const value = input?.value.trim() ?? ''
    if (value) {
      if (input) input.value = ''
      void routeTextQuestionFromUserAction(value)
    } else {
      setVoiceStatus('请输入要继续追问的问题。')
    }
  })
  document.querySelector<HTMLTextAreaElement>('#text-question-input')?.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter' || event.shiftKey) return
    event.preventDefault()
    const input = event.currentTarget as HTMLTextAreaElement | null
    const value = input?.value.trim() ?? ''
    if (value) void routeTextQuestionFromUserAction(value)
  })
  document.querySelectorAll<HTMLButtonElement>('[data-clear-history]').forEach((button) => {
    button.addEventListener('click', () => {
      clearHistory()
      renderHistory()
    })
  })
  document.addEventListener('g2vva:history-replay', (event) => {
    const text = (event as CustomEvent<{ text?: string }>).detail?.text?.trim()
    if (!text) return
    void unlockAudioPlayback()
    void speakIfEnabled(text, true)
  })
  document.addEventListener('g2vva:history-followup', (event) => {
    const detail = (event as CustomEvent<{ kind?: string; answer?: string; detail?: string }>).detail
    void unlockAudioPlayback()
    if (detail?.kind === 'vision') {
      selectG2Bookmark('vision')
      if (detail.detail) lastVisionSummary = detail.detail
      if (detail.answer) lastVisionAnswer = detail.answer
      const input = document.querySelector<HTMLTextAreaElement>('#vision-question-input')
      if (input) {
        input.value = ''
        input.placeholder = '继续追问这张图：例如，它有什么风险？文字是什么意思？'
        input.focus()
      }
      setVisionImageInfo('已选中这条视觉历史，请在下方输入追问。')
      renderBookmarkChrome()
      return
    }

    selectG2Bookmark('voice')
    const input =
      document.querySelector<HTMLTextAreaElement>('#voice-followup-input') ??
      document.querySelector<HTMLTextAreaElement>('#text-question-input')
    if (input) {
      input.value = ''
      input.placeholder = '继续追问刚才回答的内容'
      input.focus()
    }
    setVoiceStatus('已选中历史回答，请继续输入追问。')
    renderBookmarkChrome()
  })
  bindConfigPanel()
  bindKeyboardControlFallback()
  // 初始化手机网页 UI 状态（单一真相源）
  syncPhoneBookmarkDom()
  renderControlFocus()
  renderHistory()
  await prepareVoiceInput()
  await renderG2Bookmark()
  stopAutoVoiceDetection()
}

async function bindDeviceBattery(bridge: NonNullable<ReturnType<typeof getBridge>>): Promise<void> {
  try {
    const device = await bridge.getDeviceInfo()
    if (device) updateDeviceBatteryFromInfo(device)
  } catch (error) {
    console.warn('Unable to read G2 battery level.', error)
  }

  bridge.onDeviceStatusChanged((status) => {
    updateDeviceBatteryFromStatus(status)
    void renderG2Bookmark()
  })
}

function updateDeviceBatteryFromInfo(device: DeviceInfo): void {
  const kind = inferDeviceKindFromInfo(device)
  const batteryLevel = readBatteryLevel(device.status) ?? readBatteryLevel(device)
  const kindSpecific = readKindSpecificBatteryLevels(device)
  deviceKindBySn.set(device.sn, kind)
  console.info('[G2 device info]', {
    sn: device.sn,
    model: device.model,
    kind,
    batteryLevel,
    kindSpecific,
    status: device.status?.toJson?.(),
    device: device.toJson?.(),
  })

  // 从任意来源提取完整快照并缓存
  const snapshot = extractBatterySnapshot(device)
  if (typeof snapshot.glasses === 'number') setDeviceBatteryLevels({ glasses: snapshot.glasses })
  if (typeof snapshot.ring === 'number') setDeviceBatteryLevels({ ring: snapshot.ring })
  if (typeof snapshot.glasses === 'number' || typeof snapshot.ring === 'number') {
    setBatteryCache(snapshot, 'getDeviceInfo')
    updateBatteryDebugPanel(getBatteryCache())
  }

  setDeviceBatteryLevels(kindSpecific)
  applyPendingBatteryFallback()
}

function updateDeviceBatteryFromStatus(status: DeviceStatus): void {
  const batteryLevel = readBatteryLevel(status)
  const kind = deviceKindBySn.get(status.sn) ?? inferDeviceKindFromStatus(status)
  const kindSpecific = readKindSpecificBatteryLevels(status)
  console.info('[G2 device status]', {
    sn: status.sn,
    inferredKind: kind ?? 'unknown',
    batteryLevel,
    kindSpecific,
    isWearing: status.isWearing,
    isCharging: status.isCharging,
    isInCase: status.isInCase,
    connectType: status.connectType,
    status: status.toJson?.(),
  })

  // 从状态事件提取完整快照并缓存
  const snapshot = extractBatterySnapshot(status)
  if (typeof snapshot.glasses === 'number') setDeviceBatteryLevels({ glasses: snapshot.glasses })
  if (typeof snapshot.ring === 'number') setDeviceBatteryLevels({ ring: snapshot.ring })
  if (typeof snapshot.glasses === 'number' || typeof snapshot.ring === 'number') {
    setBatteryCache(snapshot, 'onDeviceStatusChanged')
    updateBatteryDebugPanel(getBatteryCache())
  }

  setDeviceBatteryLevels(kindSpecific)
  if (!kind) {
    pendingBatteryBySn.set(status.sn, batteryLevel)
    applyPendingBatteryFallback()
    return
  }
  deviceKindBySn.set(status.sn, kind)
  setDeviceBatteryLevels({ [kind]: batteryLevel })
  applyPendingBatteryFallback()
}

function inferDeviceKindFromInfo(device: DeviceInfo): 'glasses' | 'ring' {
  if (device.isRing()) return 'ring'
  if (device.isGlasses()) return 'glasses'
  const deviceJson = getJsonObject(device)
  const text = [
    device.sn,
    String(device.model ?? ''),
    readLooseText(deviceJson, 'name'),
    readLooseText(deviceJson, 'deviceName'),
    readLooseText(deviceJson, 'type'),
    readLooseText(deviceJson, 'deviceType'),
  ].join(' ').toLowerCase()
  if (/(^|\b)(r1|ring|remote|controller)(\b|$)|戒指|遥控/.test(text)) return 'ring'
  return 'glasses'
}

function inferDeviceKindFromStatus(status: DeviceStatus): 'glasses' | 'ring' | undefined {
  const statusJson = getJsonObject(status)
  const sn = status.sn.toLowerCase()
  const text = [
    sn,
    readLooseText(statusJson, 'model'),
    readLooseText(statusJson, 'name'),
    readLooseText(statusJson, 'deviceName'),
    readLooseText(statusJson, 'type'),
    readLooseText(statusJson, 'deviceType'),
  ].join(' ').toLowerCase()
  if (/(^|\b)(r1|ring|remote|controller)(\b|$)|戒指|遥控/.test(text)) return 'ring'
  if (/(^|\b)(g2|glass|glasses)(\b|$)|眼镜/.test(text)) return 'glasses'
  const glassesSn = [...deviceKindBySn].find(([, kind]) => kind === 'glasses')?.[0]
  if (glassesSn && status.sn && status.sn !== glassesSn) return 'ring'
  if (typeof status.isWearing === 'boolean') return 'glasses'
  return undefined
}

function applyPendingBatteryFallback(): void {
  for (const [sn, battery] of pendingBatteryBySn) {
    if (deviceKindBySn.has(sn)) continue
    const knownKinds = new Set(deviceKindBySn.values())
    const glassesSn = [...deviceKindBySn].find(([, kind]) => kind === 'glasses')?.[0]
    if (!knownKinds.has('ring')) {
      deviceKindBySn.set(sn, 'ring')
      if (typeof battery === 'number') setDeviceBatteryLevels({ ring: battery })
      console.info('[G2 battery fallback] treating unknown device as R1 ring', { sn, glassesSn, battery })
    }
  }
}

/** 更新设置页电量调试面板 */
function updateBatteryDebugPanel(snapshot: BatterySnapshot): void {
  const el = document.querySelector('#battery-debug-info')
  if (!el) return
  const g2 = typeof snapshot.glasses === 'number' ? `${snapshot.glasses}%` : '未上报'
  const r1 = typeof snapshot.ring === 'number' ? `${snapshot.ring}%` : '未上报'
  el.textContent = [
    `G2：${g2}`,
    `R1：${r1}`,
    snapshot.source ? `来源：${snapshot.source}` : '',
    snapshot.updatedAt ? `更新时间：${snapshot.updatedAt}` : '',
  ]
    .filter(Boolean)
    .join('\n')
}

/** 初始化电量显示：优先从缓存恢复，避免页面刷新后长期显示 "--%" */
function initBatteryDisplay(): void {
  const cached = loadBatteryCache()
  if (typeof cached.glasses === 'number' || typeof cached.ring === 'number') {
    if (typeof cached.glasses === 'number') setDeviceBatteryLevels({ glasses: cached.glasses })
    if (typeof cached.ring === 'number') setDeviceBatteryLevels({ ring: cached.ring })
    updateBatteryDebugPanel(cached)
    console.info('[Battery cache] restored from localStorage', cached)
  }
}

function readKindSpecificBatteryLevels(source: unknown): { glasses?: number; ring?: number } {
  const candidates = collectBatteryObjects(source)
  const result: { glasses?: number; ring?: number } = {}
  for (const candidate of candidates) {
    result.glasses ??= readBatteryValueByKeys(candidate, [
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
    ])
    result.ring ??= readBatteryValueByKeys(candidate, [
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
    ])
  }
  return result
}

function collectBatteryObjects(source: unknown): Array<Record<string, unknown>> {
  const result: Array<Record<string, unknown>> = []
  const seen = new WeakSet<object>()
  const visit = (value: unknown, depth: number): void => {
    if (depth > 3 || typeof value !== 'object' || value === null || seen.has(value)) return
    seen.add(value)
    const record = value as Record<string, unknown>
    result.push(record)
    const json = getJsonObject(value)
    if (json && json !== value) visit(json, depth + 1)
    for (const key of [
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
    ]) {
      visit(record[key], depth + 1)
    }
  }
  visit(source, 0)
  return result
}

function readBatteryLevel(source: unknown): number | undefined {
  const direct = readBatteryValue(source)
  if (typeof direct === 'number') return direct
  const record = asRecord(source)
  const nestedStatus = record?.status
  const nested = readBatteryValue(nestedStatus)
  if (typeof nested === 'number') return nested
  const json = getJsonObject(source)
  const fromJson = readBatteryValue(json)
  if (typeof fromJson === 'number') return fromJson
  const jsonNested = readBatteryValue(json?.status)
  if (typeof jsonNested === 'number') return jsonNested
  return findBatteryValueDeep(source)
}

function readBatteryValue(source: unknown): number | undefined {
  const record = asRecord(source)
  if (!record) return undefined
  const batteryKeys = [
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
  return readBatteryValueByKeys(record, batteryKeys)
}

function readBatteryValueByKeys(source: unknown, keys: string[]): number | undefined {
  const record = asRecord(source)
  if (!record) return undefined
  for (const key of keys) {
    const value = readNumericValue(record[key])
    if (typeof value === 'number') return normalizeRawBattery(value)
  }
  return undefined
}

function findBatteryValueDeep(source: unknown, depth = 0, seen = new WeakSet<object>()): number | undefined {
  if (depth > 4 || typeof source !== 'object' || source === null) return undefined
  if (seen.has(source)) return undefined
  seen.add(source)
  const record = source as Record<string, unknown>

  for (const [key, raw] of Object.entries(record)) {
    if (!/(battery|power|charge|capacity|percent)/i.test(key)) continue
    const value = readNumericValue(raw)
    if (typeof value === 'number' && Number.isFinite(value)) return normalizeRawBattery(value)
  }

  for (const raw of Object.values(record)) {
    const value = findBatteryValueDeep(raw, depth + 1, seen)
    if (typeof value === 'number') return value
  }

  return undefined
}

function readNumericValue(raw: unknown): number | undefined {
  if (typeof raw === 'number' && Number.isFinite(raw)) return raw
  if (typeof raw === 'string') {
    const normalized = raw.trim()
    const exact = Number(normalized)
    if (Number.isFinite(exact)) return exact
    const match = normalized.match(/-?\d+(?:\.\d+)?/)
    if (!match) return undefined
    const parsed = Number(match[0])
    return Number.isFinite(parsed) ? parsed : undefined
  }
  return undefined
}

function normalizeRawBattery(value: number): number {
  const percent = value > 0 && value <= 1 ? value * 100 : value
  return Math.max(0, Math.min(100, Math.round(percent)))
}

function getJsonObject(source: unknown): Record<string, unknown> | undefined {
  const toJson = asRecord(source)?.toJson
  if (typeof toJson !== 'function') return undefined
  try {
    return asRecord(toJson.call(source))
  } catch {
    return undefined
  }
}

function readLooseText(source: unknown, key: string): string {
  const value = asRecord(source)?.[key]
  return typeof value === 'string' || typeof value === 'number' ? String(value) : ''
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : undefined
}

function createGlassRenderer(bridge = getBridge()): GlassRenderer {
  return new GlassRenderer(bridge, getGlassBatteryText, (content) => {
    const el = document.querySelector<HTMLPreElement>('#debug-log')
    if (el) el.textContent = content
  })
}

async function handleG2ControlEvent(event: EvenHubEvent): Promise<void> {
  const now = Date.now()
  const normalizedEvents = normalizeEvenInputEvent(event)
  if (event.audioEvent && normalizedEvents.length === 0) return

  for (const normalized of normalizedEvents) {
    lastR1InputSummary = formatInputEventForLog(normalized, `${getCurrentG2Bookmark().id}/${activeGlassPage}/${visionState}`)
    console.info('[G2 input]', lastR1InputSummary)
  }
  renderR1CameraDebug()

  const intent = getControlIntent(event)
  if (!intent) return
  if (intent !== 'double_click' && now - lastControlEventAt < 180) return
  lastControlEventAt = now
  setInteractionFeedback(`R1：${getIntentLabel(intent)}`)

  // Native iOS/Even camera or album UI may return focus without restoring the
  // glass page marker. If a captured image is pending, keep R1 bound to the
  // vision confirmation flow so a single click can upload reliably.
  if (pendingCapturedImage && visionState === 'captured') {
    activeGlassPage = 'vision'
    await handleVisionR1Intent(intent)
    return
  }

  if (activeGlassPage === 'diagnostics') {
    await handleDiagnosticsR1Intent(intent)
    return
  }

  // 交易子页面 R1 处理：↑↓ 切子页面，click 返回菜单，双击返回 HOME
  if (activeGlassPage === 'trading') {
    const bridge = getBridge()
    const renderer = createGlassRenderer(bridge)
    if (intent === 'double_click') {
      inTradingMenu = true
      activeGlassPage = 'home'
      await renderer.show('home')
      await renderG2Bookmark()
      return
    }
    if (intent === 'next') {
      tradingSubPageIndex = (tradingSubPageIndex + 1) % 6
      inTradingMenu = true
      await renderer.show('trading_menu', { activeIndex: tradingSubPageIndex, extendedData: getTradingMenuExtendedData(isTradingCacheFresh() ? undefined : '显示上次缓存') })
      return
    }
    if (intent === 'previous') {
      tradingSubPageIndex = (tradingSubPageIndex - 1 + 6) % 6
      inTradingMenu = true
      await renderer.show('trading_menu', { activeIndex: tradingSubPageIndex, extendedData: getTradingMenuExtendedData(isTradingCacheFresh() ? undefined : '显示上次缓存') })
      return
    }
    if (intent === 'click') {
      await showTradingSubPage(tradingSubPageIndex, renderer, { forceRefresh: !inTradingMenu })
      return
    }
    return
  }

  if (activeGlassPage === 'vision' && intent) {
    await handleVisionR1Intent(intent)
    return
  }

  if (activeGlassPage === 'voice' && intent) {
    await handleVoiceR1Intent(intent)
    return
  }

  if (intent === 'double_click') {
    await stopGlassMicProbeAndReturnHome()
    return
  }

  const direction = getControlDirection(event)
  if (direction) {
    moveControlFocus(direction)
    await announceFocusedControl()
    return
  }

  if (isClickEvent(event)) {
    await executeFocusedControl()
  }
}

async function runCaptureFlow(prompt?: string, preparedImage?: CapturedImage, options?: { source?: string }): Promise<void> {
  const bridge = getBridge()
  const renderer = createGlassRenderer(bridge)
  const button = document.querySelector<HTMLButtonElement>('#capture-button')
  const requestStartedAt = performance.now()
  const effectivePrompt = (prompt ?? getVisionQuestionInput()).trim()
  const opId = startGlassOperation() // 标记本次操作，异步回调需检查 session 合法性

  try {
    stopAutoVoiceDetection()
    tradingPanelActive = false
    button?.setAttribute('disabled', 'true')
    selectG2Bookmark('vision')
    setVisionResultPanel('识别中', '正在获取图片...', '请完成拍照或选择照片。')
    startFlow()
    setStage('capture', preparedImage ? '已自动抓拍，准备识别' : '等待拍照或选择照片', 8)
    const imagePromise = preparedImage ? Promise.resolve(preparedImage) : capturePhoto()
    await safeShowOnG2(
      bridge,
      formatForG2('正在识别', preparedImage ? '已自动抓拍\n正在请求 AI' : '请选择拍照或照片\n完成后自动识别'),
    )
    const image = await imagePromise
    const imageBytes = estimateBase64Bytes(image.imageBase64)
    if (!image.imageBase64 || imageBytes <= 0) throw new Error('没有获取到图片，请重新拍照。')
    setVisionImageInfo([
      `图片已获取：约 ${formatBytes(imageBytes)}`,
      `data length：${image.imageBase64.length}`,
      `capture：${new Date().toLocaleTimeString('zh-CN')}`,
    ].join('\n'))
    await safeGlassShow(renderer, 'vision_captured', { status: '照片已拍摄，正在识别' })
    console.info('[P0 vision] image ready', {
      dataUrlLength: image.imageBase64.length,
      estimatedBytes: imageBytes,
      prompt: effectivePrompt,
    })
    const thumbnailDataUrl = await createVisionPreviewDataUrl(image, 240, 240, 0.62)
    const imageDataUrl = createCapturedImageDataUrl(image)
    const captureHistory = addHistory({
      kind: 'vision',
      title: effectivePrompt ? '天禄看图' : '拍照识别',
      input: effectivePrompt || undefined,
      answer: '照片已采集，正在上传识别。',
      detail: `图片大小：约 ${formatBytes(imageBytes)}`,
      summary: '照片已采集',
      thumbnailDataUrl,
      imageDataUrl,
    })
    renderHistory()
    const g2PreviewBase64 = await createVisionPreviewBase64(image, 288, 144, 0.56)
    if (g2PreviewBase64) {
      await safeGlassImagePreview(renderer, g2PreviewBase64, '照片已采集')
    } else {
      await safeGlassShow(renderer, 'vision_captured', { status: '照片已拍摄，正在识别' })
    }

    setStage('compress', '图片已压缩，准备上传', 35)
    setStage('upload', '上传后端中', 52)
    const apiUrl = `${getAppConfig().apiBase.replace(/\/+$/, '')}/vision`
    setVisionImageInfo([
      `图片大小：约 ${formatBytes(imageBytes)}`,
      `上传接口：${apiUrl}`,
      '状态：正在上传',
    ].join('\n'))
    console.info('[P0 vision] upload start', {
	      apiUrl,
	      imageBase64Length: image.imageBase64.length,
	      estimatedBytes: imageBytes,
	      source: options?.source ?? 'web',
	      startedAt: new Date().toISOString(),
	    })
    setStage('vision', 'MiniMax 正在识别画面', 72)
    const config = getAppConfig()
    const location = await getLocationContext(config.enableLocationContext, { resolveAddress: true })
    const locationContext = formatLocationForPrompt(location)
    const capturedAt = new Date().toISOString()
    const recentVisionContext = [
      lastVisionPrompt ? `上次问题：${lastVisionPrompt}` : '',
      lastVisionSummary ? `上次画面：${lastVisionSummary}` : '',
      lastVisionAnswer ? `上次回答：${lastVisionAnswer}` : '',
    ].filter(Boolean).join('\n')
    const result = await recognizeImage(image, effectivePrompt || undefined, {
      capturedAt,
      locationContext,
      recentVisionContext,
    })
    const elapsedMs = Math.round(performance.now() - requestStartedAt)
    console.info('[P0 vision] upload success', {
      elapsedMs,
      answerLength: result.answer.length,
      descriptionLength: result.description.length,
      provider: result.provider,
    })
    lastVisionSummary = result.description
    lastVisionAnswer = result.answer
    lastVisionPrompt = effectivePrompt
    renderBookmarkChrome()
    updateHistoryItem(captureHistory.id, {
      answer: result.answer,
      detail: [
        result.description,
        locationContext ? `定位上下文：${locationContext}` : '',
      ].filter(Boolean).join('\n'),
      summary: result.description,
    })
    renderHistory()
    if (!prompt && effectivePrompt) clearVisionQuestionInput()

    setStage('speak', '识别完成，正在朗读', 92)
    setVisionResultPanel(
      `完成 · ${elapsedMs} ms · ${result.provider || 'vision api'}`,
      [`图片大小：约 ${formatBytes(imageBytes)}`, `answer length：${result.answer.length}`, '来源：vision api', locationContext].filter(Boolean).join('\n'),
      result.answer,
    )
    await safeGlassShow(renderer, 'reply', { answer: result.answer })

    await speakIfEnabled(result.answer, true)
    finishFlow('完成', 100)
    if (isGlassOperationValid(opId)) visionState = 'result'
  } catch (error) {
    if (!isGlassOperationValid(opId)) {
      // session 已被取消操作重置，仍返回首页避免 G2 停留中间状态
      activeGlassPage = 'home'
      await safeGlassShow(renderer, 'home')
      return
    }
    const message = formatVisionError(error)
    failFlow(message)
    setVisionResultPanel('失败', '视觉识别未完成', message)
    await safeGlassShow(renderer, 'error', { body: message })
    if (isGlassOperationValid(opId)) visionState = 'error'
  } finally {
    button?.removeAttribute('disabled')
    if (!pendingVisionPrompt) hideConfirmCameraButton()
    renderControlFocus()
  }
}

async function handleManualImageFile(file: File, source: 'web-album' | 'web-camera'): Promise<void> {
  const renderer = createGlassRenderer(getBridge())
  const sourceName = source === 'web-album' ? '相册选图' : '手机拍照'
  const opId = startGlassOperation()
  try {
    if (!isGlassOperationValid(opId)) return
    selectG2Bookmark('vision')
    activeGlassPage = 'vision'
    if (isGlassOperationValid(opId)) visionState = 'preparing'
    lastVisionError = ''
    pendingCapturedImage = undefined
    uploadInFlight = false
    setInteractionFeedback(`${sourceName}：正在读取`)
    setVisionResultPanel(
      `${sourceName} · 正在读取`,
      [`文件：${file.name || '手机照片'}`, `大小：${formatBytes(file.size)}`, '状态：正在压缩并上传识别'].join('\n'),
      '请稍候，照片返回后会直接进入 AI 识别。',
    )
    await safeGlassShow(renderer, 'vision_uploading')
    const image = await imageFileToCapturedImage(file)
    if (!isGlassOperationValid(opId)) return
    const imageBytes = estimateBase64Bytes(image.imageBase64)
    if (!image.imageBase64 || imageBytes <= 0) throw new Error('没有获取到图片，请重新拍照或重新选图。')
    lastCaptureAt = new Date().toLocaleTimeString('zh-CN')
    lastCapturedAt = Date.now()
    lastUploadSource = source
    setInteractionFeedback(`${sourceName}：已获取，正在上传`)
    setVisionResultPanel(
      `${sourceName} · 已获取`,
      [`图片大小：约 ${formatBytes(imageBytes)}`, `capture：${lastCaptureAt}`, `source：${source}`].join('\n'),
      '正在发送给天禄视觉识别...',
    )
    await runCaptureFlow(undefined, image, { source })
  } catch (error) {
    if (!isGlassOperationValid(opId)) return
    if (isGlassOperationValid(opId)) visionState = 'error'
    const message = formatVisionError(error)
    lastVisionError = message
    setInteractionFeedback(`${sourceName}：失败`)
    setVisionResultPanel(`${sourceName}失败`, '未完成上传识别', message)
    await safeGlassShow(renderer, 'error', { body: message })
  } finally {
    renderR1CameraDebug()
  }
}

async function safeShowOnG2(bridge: ReturnType<typeof getBridge>, content: string): Promise<void> {
  try {
    await showOnG2(bridge, content)
  } catch (error) {
    console.warn('[P0 vision] G2 display failed but web result continues.', error)
    void recordRuntimeError(() => getAppConfig().apiBase, {
      kind: 'g2-display',
      message: errorToRuntimeMessage(error),
      detail: `content=${content.slice(0, 500)}`,
      createdAt: new Date().toISOString(),
      page: location.href,
    })
    setVoiceStatus('G2 显示失败，但网页结果会继续生成。')
  }
}

async function safeGlassShow(
  renderer: GlassRenderer,
  screen: Parameters<GlassRenderer['show']>[0],
  state?: Parameters<GlassRenderer['show']>[1],
): Promise<void> {
  try {
    await renderer.show(screen, state)
  } catch (error) {
    console.warn('[P0 vision] GlassRenderer show failed but web result continues.', error)
    void recordRuntimeError(() => getAppConfig().apiBase, {
      kind: 'glass-show',
      message: errorToRuntimeMessage(error),
      detail: `screen=${String(screen)} state=${safeRuntimeJson(state)}`,
      createdAt: new Date().toISOString(),
      page: location.href,
    })
    setVoiceStatus('G2 显示失败，但网页结果已生成。')
  }
}

async function safeGlassImagePreview(renderer: GlassRenderer, imageBase64: string, caption: string): Promise<void> {
  try {
    await renderer.showImagePreview(imageBase64, caption)
  } catch (error) {
    console.warn('[P0 vision] G2 image preview failed; falling back to text confirmation.', error)
    void recordRuntimeError(() => getAppConfig().apiBase, {
      kind: 'glass-show',
      message: errorToRuntimeMessage(error),
      detail: `screen=vision_image_preview imageBase64Length=${imageBase64.length}`,
      createdAt: new Date().toISOString(),
      page: location.href,
    })
    await safeGlassShow(renderer, 'vision_captured', { status: '照片已拍摄，正在识别' })
  }
}

function errorToRuntimeMessage(error: unknown): string {
  return error instanceof Error ? `${error.name}: ${error.message}` : String(error)
}

function safeRuntimeJson(value: unknown): string {
  try {
    return JSON.stringify(value).slice(0, 800)
  } catch {
    return String(value).slice(0, 800)
  }
}

function setVisionResultPanel(meta: string, imageInfo: string, answer: string): void {
  const metaEl = document.querySelector('#vision-result-meta')
  const imageEl = document.querySelector('#vision-image-info')
  const answerEl = document.querySelector('#vision-result-answer')
  if (metaEl) metaEl.textContent = meta
  if (imageEl) imageEl.textContent = imageInfo
  if (answerEl) answerEl.textContent = answer
}

function setVisionImageInfo(text: string): void {
  const imageEl = document.querySelector('#vision-image-info')
  if (imageEl) imageEl.textContent = text
}

function getVisionQuestionInput(): string {
  return document.querySelector<HTMLTextAreaElement>('#vision-question-input')?.value.trim() ?? ''
}

function clearVisionQuestionInput(): void {
  const input = document.querySelector<HTMLTextAreaElement>('#vision-question-input')
  if (input) input.value = ''
}

function createCapturedImageDataUrl(image: CapturedImage): string | undefined {
  return image.imageBase64 ? `data:${image.mimeType};base64,${image.imageBase64}` : undefined
}

async function createVisionPreviewBase64(
  image: CapturedImage,
  maxWidth: number,
  maxHeight: number,
  quality: number,
): Promise<string | undefined> {
  const dataUrl = await createVisionPreviewDataUrl(image, maxWidth, maxHeight, quality)
  return dataUrl?.split(',')[1]
}

async function createVisionPreviewDataUrl(
  image: CapturedImage,
  maxWidth: number,
  maxHeight: number,
  quality: number,
): Promise<string | undefined> {
  if (!image.imageBase64) return undefined
  try {
    const sourceUrl = createCapturedImageDataUrl(image)
    if (!sourceUrl) return undefined
    const img = new Image()
    img.decoding = 'async'
    const loaded = new Promise<void>((resolve, reject) => {
      img.onload = () => resolve()
      img.onerror = () => reject(new Error('thumbnail image decode failed'))
    })
    img.src = sourceUrl
    await loaded
    const sourceWidth = img.naturalWidth || maxWidth
    const sourceHeight = img.naturalHeight || maxHeight
    const scale = Math.min(1, maxWidth / sourceWidth, maxHeight / sourceHeight)
    const width = Math.max(1, Math.round(sourceWidth * scale))
    const height = Math.max(1, Math.round(sourceHeight * scale))
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const context = canvas.getContext('2d')
    if (!context) return undefined
    context.drawImage(img, 0, 0, width, height)
    return canvas.toDataURL('image/jpeg', quality)
  } catch (error) {
    console.warn('[G2 history] preview image generation failed', error)
    return undefined
  }
}

async function askVisionFollowup(question: string, source = 'vision-followup'): Promise<void> {
  const trimmed = question.trim()
  if (!trimmed) return

  const bridge = getBridge()
  const renderer = createGlassRenderer(bridge)
  const contextParts = [
    lastVisionPrompt ? `上次看图问题：${lastVisionPrompt}` : '',
    lastVisionSummary ? `最近视觉描述：${lastVisionSummary}` : '',
    lastVisionAnswer ? `最近视觉回答：${lastVisionAnswer}` : '',
  ].filter(Boolean)

  if (contextParts.length === 0) {
    const message = '还没有可追问的视觉结果，请先拍照识别或从相册选图。'
    setVisionResultPanel('无法追问', '暂无最近视觉上下文', message)
    setVoiceStatus(message)
    await safeGlassShow(renderer, 'error', { body: message })
    return
  }

  try {
    selectG2Bookmark('vision')
    setVisionResultPanel('追问中', contextParts.join('\n'), `问题：${trimmed}\n天禄正在结合最近画面回答...`)
    await safeGlassShow(renderer, 'voice_transcript', { transcript: trimmed })
    const location = await getLocationContext(getAppConfig().enableLocationContext, { resolveAddress: true })
    const locationContext = formatLocationForPrompt(location)
    const response = await askAssistant(trimmed, contextParts.join('\n'), {
      capturedAt: new Date().toISOString(),
      locationContext,
    })
    const sanitizedAnswer = sanitizeDirectTianluAnswer(response.answer)
    const answer = isFallbackOnlyAnswer(sanitizedAnswer)
      ? `结合最近视觉结果：${lastVisionAnswer || lastVisionSummary}\n\n追问：${trimmed}`
      : sanitizedAnswer

    lastVisionAnswer = answer
    lastVisionPrompt = trimmed
    setVisionResultPanel(
      response.provider ? `追问完成 · ${response.provider}` : '追问完成',
      contextParts.join('\n'),
      answer,
    )
    setVoiceTranscript(`你：${trimmed}\n天禄：${answer}`)
    addHistory({
      kind: 'vision',
      title: '图片追问',
      input: trimmed,
      answer,
      detail: lastVisionSummary,
    })
    renderHistory()
    updateVoiceDebug({ voicePageState: 'answer', lastIntent: 'vision-followup', lastAnswer: answer, fallbackUsed: source })
    clearVisionQuestionInput()
    await safeGlassShow(renderer, 'reply', { answer })
    await speakIfEnabled(answer)
  } catch (error) {
    const message = `图片追问失败：${error instanceof Error ? error.message : String(error)}`
    setVisionResultPanel('追问失败', contextParts.join('\n'), message)
    setVoiceStatus(message)
    await safeGlassShow(renderer, 'error', { body: message })
  }
}

function renderR1CameraDebug(): void {
  const engine = getVisionEngineState()
  const pendingBytes = pendingCapturedImage?.imageBase64 ? estimateBase64Bytes(pendingCapturedImage.imageBase64) : 0
  const msSinceCaptured = lastCapturedAt ? Date.now() - lastCapturedAt : 0
  const metaEl = document.querySelector('#r1-camera-debug-meta')
  const bodyEl = document.querySelector('#r1-camera-debug')
  if (metaEl) metaEl.textContent = `state=${visionState} · engine=${engine.status}`
  if (!bodyEl) return
  const inputHint =
    lastR1InputSummary === 'none'
      ? getBridge()
        ? '未收到R1事件：请转动/点击R1，或检查插件是否在Even App内运行。'
        : '当前是网页预览模式：普通浏览器无法接收R1/G2输入。'
      : lastR1InputSummary
  bodyEl.textContent = [
    `r1VisionState: ${visionState}`,
    `visionEngine: ${engine.status}`,
    `runtime: ${runtimeCapabilities.label}`,
    `cameraStrategy: ${runtimeCapabilities.cameraStrategy}`,
    `videoSize: ${engine.videoWidth}x${engine.videoHeight}`,
    `startedAt: ${engine.startedAt ?? '--'}`,
    `pendingCapturedImage: ${pendingCapturedImage ? `yes (${formatBytes(pendingBytes)})` : 'no'}`,
    `msSinceLastCaptured: ${msSinceCaptured || '--'}`,
    `uploadInFlight: ${uploadInFlight ? 'yes' : 'no'}`,
    `lastInput: ${inputHint}`,
    `lastCaptureAt: ${lastCaptureAt || '--'}`,
    `lastUploadAt: ${lastUploadAt || '--'}`,
    `lastUploadSource: ${lastUploadSource || '--'}`,
    `lastVisionError: ${lastVisionError || engine.error || '--'}`,
  ].join('\n')
}

function estimateBase64Bytes(base64: string): number {
  const padding = base64.endsWith('==') ? 2 : base64.endsWith('=') ? 1 : 0
  return Math.max(0, Math.floor((base64.length * 3) / 4) - padding)
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

function formatVisionError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error)
  if (/NotAllowedError|Permission|permission|denied|权限/i.test(message)) return '相机不可用，请在手机 Even App 中允许相机权限。'
  if (/未选择照片|没有获取到图片|empty/i.test(message)) return '没有获取到图片，请重新拍照。'
  if (/Failed to fetch|NetworkError|Load failed|network/i.test(message)) {
    return '网络请求失败，请检查 https://g2-vision.tianlu2026.org。'
  }
  if (/Vision API failed|视觉请求失败|MiniMax VLM failed|MiniMax chat failed|internal_error/i.test(message)) {
    return `视觉识别接口不可用，请检查 G2 Bridge 后端。${message}`
  }
  return message
}

async function runVoiceFlow(): Promise<void> {
  stopAutoVoiceDetection()
  await startHoldToTalkSession({ mode: 'asr' })
}

async function startHoldToTalkSession(options: {
  strategy?: 'g2-pcm' | 'phone-media-recorder' | 'text'
  mode?: VoiceSessionMode
  maxDurationMs?: number
  mockText?: string
} = {}): Promise<void> {
  if (activeG2PcmVoiceSession || phoneHoldRecorder) return

  void unlockAudioPlayback()
  selectG2Bookmark('voice')
  activeGlassPage = 'voice'
  const bridge = getBridge()
  const strategy = options.strategy ?? getAdaptiveVoiceStrategy()
  const maxDurationMs = options.maxDurationMs ?? getVoiceRecordMaxMs()
  const mode = options.mode ?? 'asr'

  if (strategy === 'g2-pcm' && bridge) {
    await startG2HoldToTalkSession(bridge, mode, maxDurationMs, options.mockText)
    return
  }

  await startPhoneHoldVoiceCapture()
}

function getAdaptiveVoiceStrategy(): 'g2-pcm' | 'phone-media-recorder' {
  // Even 插件真机/模拟器里优先走 G2 原生麦克风；普通网页里走手机/耳机麦克风。
  return getBridge() ? 'g2-pcm' : 'phone-media-recorder'
}

function getAdaptiveVoiceHint(): string {
  return getAdaptiveVoiceStrategy() === 'g2-pcm'
    ? 'Even 插件模式：使用 G2 原生麦克风'
    : '网页模式：使用手机/耳机麦克风'
}

async function stopHoldToTalkSession(reason: StopReason): Promise<void> {
  if (activeG2PcmVoiceSession) {
    const session = activeG2PcmVoiceSession
    activeG2PcmVoiceSession = undefined
    setVoiceRecordingButtons(false)
    await session.stop(reason)
    voicePageState = reason === 'cancelled' ? 'idle' : 'finalizing'
    await createGlassRenderer(getBridge()).show(reason === 'cancelled' ? 'voice_menu' : 'voice_finalizing')
    return
  }

  if (phoneHoldRecorder) {
    await stopPhoneHoldVoiceCapture(reason === 'cancelled' ? 'cancel' : 'release')
  }
}

async function startG2HoldToTalkSession(
  bridge: NonNullable<ReturnType<typeof getBridge>>,
  mode: VoiceSessionMode,
  maxDurationMs: number,
  mockText?: string,
): Promise<void> {
  await stopActiveGlassMicProbe?.()
  stopActiveGlassMicProbe = undefined
  activeG2PcmVoiceSession = undefined

  const renderer = createGlassRenderer(bridge)
  voicePageState = 'recording'
  setVoiceStatus('正在听你说话。R1 再单触结束，最长 120 秒。')
  setVoiceTranscript('')
  setVoiceRecordingButtons(true)
  await renderer.show('voice_recording', { status: '0', pcmBytes: 0, chunks: 0 })

  activeG2PcmVoiceSession = await startG2PcmVoiceSession({
    bridge,
    mode,
    maxDurationMs,
    mockText,
    onStatus: setVoiceStatus,
    onDebug: (debug) => {
      applyG2PcmVoiceDebug(debug)
      if (debug.voiceState === 'recording' || debug.voiceState === 'starting') {
        setVoiceRecordingButtons(true, debug.elapsedMs ?? 0, debug.maxDurationMs ?? maxDurationMs)
      }
      void renderer.updateMainText(renderer.render('voice_recording', {
        status: String(Math.round((debug.elapsedMs ?? 0) / 1000)),
        pcmBytes: debug.totalBytes,
        chunks: debug.chunks,
      }))
    },
    onTranscript: (text, meta) => {
      activeG2PcmVoiceSession = undefined
      setVoiceRecordingButtons(false)
      voicePageState = 'transcribing'
      void handleTranscript(text, { source: 'g2-pcm', durationMs: meta?.durationMs, totalBytes: meta?.totalBytes, mode: meta?.mode })
    },
    onError: (error) => {
      activeG2PcmVoiceSession = undefined
      setVoiceRecordingButtons(false)
      voicePageState = 'error'
      setVoiceStatus(`语音错误：${error.message}`)
      updateVoiceDebug({ voicePageState: 'error', lastVoiceError: error.message })
      void renderer.show('voice_error', { body: error.message })
    },
    onMaxDuration: () => {
      setVoiceStatus('已达到 120 秒上限，正在结束录音。')
    },
  })
}

function applyG2PcmVoiceDebug(debug: G2PcmVoiceDebugState): void {
  voicePageState = mapG2DebugState(debug.voiceState)
  updateVoiceDebug({
    voicePageState,
    micSource: 'g2',
    wsStatus: debug.wsStatus,
    audioControlCalled: debug.audioControlCalled,
    audioControlError: debug.audioControlError,
    totalBytes: debug.totalBytes,
    chunks: debug.chunks,
    lastChunkBytes: debug.lastChunkBytes,
    lastChunkAt: debug.lastChunkAt || '--',
    noPcmTimeout: debug.voiceState === 'no_pcm',
    lastServerAudioDebug: debug.lastServerAudioDebug,
    lastVoiceError: debug.lastVoiceError,
    holdStartedAt: debug.holdStartedAt,
    elapsedMs: debug.elapsedMs,
    maxDurationMs: debug.maxDurationMs,
    remainingMs: debug.remainingMs,
    stopReason: debug.stopReason,
    lastTranscript: debug.lastTranscript,
  })
}

function mapG2DebugState(state: G2PcmVoiceDebugState['voiceState']): VoiceDebugState['voicePageState'] {
  if (state === 'recording' || state === 'starting') return 'recording'
  if (state === 'finalizing') return 'finalizing'
  if (state === 'transcribing') return 'transcribing'
  if (state === 'answer') return 'answer'
  if (state === 'no_pcm') return 'no_pcm'
  if (state === 'error') return 'error'
  return 'idle'
}

async function startVoiceDiagnosticProbe(): Promise<void> {
  const bridge = getBridge()
  if (!bridge) {
    setVoiceStatus('未检测到 G2 Bridge，语音诊断只能在 Even App 真机或 simulator 中运行。')
    return
  }
  await stopHoldToTalkSession('cancelled')
  const renderer = createGlassRenderer(bridge)
  activeGlassPage = 'voice'
  voicePageState = 'probe'
  setVoiceStatus('正在启动 G2 麦克风诊断，只统计 PCM，不做 ASR。')
  stopActiveGlassMicProbe = await startGlassMicProbe({
    bridge,
    renderer,
    mode: 'probe',
    onStatus: setVoiceStatus,
    onDebug: updateVoiceDebug,
  })
}

async function runG2MicWebSocketVoiceFlow(target: VoiceTarget = 'assistant'): Promise<void> {
  const bridge = getBridge()
  const button = document.querySelector<HTMLButtonElement>('#voice-button')
  if (!bridge) {
    setVoiceStatus('请在 Even App 真机或 simulator 中测试 G2 麦克风。')
    return
  }

  try {
    await stopActiveG2MicStream?.()
    stopActiveG2MicStream = undefined
    await stopActiveGlassMicProbe?.()
    stopActiveGlassMicProbe = undefined
    button?.setAttribute('disabled', 'true')
    activeGlassPage = 'voice'
    voicePageState = 'listening'
    setVoiceStatus('正在启动 G2 麦克风录音，静音后自动转文字。')
    setVoiceTranscript('')
    updateVoiceDebug({
      voicePageState: 'probe',
      micSource: 'g2',
      wsStatus: 'connecting',
      audioControlCalled: false,
      audioControlError: '',
      totalBytes: 0,
      chunks: 0,
      lastChunkBytes: 0,
      lastChunkAt: '--',
      noPcmTimeout: false,
      lastServerAudioDebug: '',
      lastVoiceError: '',
    })
    const renderer = createGlassRenderer(bridge)
    const stop = await startGlassMicProbe({
      bridge,
      renderer,
      mode: 'asr',
      onStatus: (text) => {
        setVoiceStatus(text)
      },
      onTranscript: (text) => {
        setVoiceTranscript(`听到：${text}`)
        void handleTranscript(text, { source: `g2-legacy-${target}`, mode: 'asr' })
      },
      onAnswer: (text) => {
        setVoiceStatus('天禄已回答。')
        setVoiceTranscript(`天禄：${text}`)
        addHistory({
          kind: 'voice',
          title: target === 'openclaw' ? 'OpenCLAW MicProbe' : 'G2 MicProbe',
          input: 'G2 PCM MicProbe',
          answer: text,
          detail: 'probe-audio',
        })
        renderHistory()
        void speakIfEnabled(text, true)
      },
      onDebug: updateVoiceDebug,
    })
    stopActiveGlassMicProbe = stop
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    updateVoiceDebug({ lastVoiceError: message })
    setVoiceStatus(`G2 语音连接失败：${message}`)
    await showOnG2(bridge, formatForG2('语音连接失败', message))
  } finally {
    button?.removeAttribute('disabled')
    renderControlFocus()
  }
}

async function runG2MicVoiceFlow(bridge: NonNullable<ReturnType<typeof getBridge>>): Promise<void> {
  const button = document.querySelector<HTMLButtonElement>('#voice-button')

  try {
    button?.setAttribute('disabled', 'true')
    setVoiceStatus('旧录音链路已停用，正在切换到 G2 PCM MicProbe。')
    setVoiceTranscript('')
    await runG2MicWebSocketVoiceFlow('assistant')
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    setVoiceStatus(message)
    await showOnG2(bridge, formatForG2('G2 麦克风失败', message))
  } finally {
    button?.removeAttribute('disabled')
    renderControlFocus()
  }
}

async function runBrowserVoiceFlow(prompt = '正在听，请说：你好天禄...'): Promise<void> {
  const bridge = getBridge()

  await stopActiveGlassMicProbe?.()
  stopActiveGlassMicProbe = undefined
  voicePageState = 'idle'
  setVoiceStatus(`${prompt} 正在切换手机/耳机麦克风兜底。`)
  setVoiceTranscript('')
  await runPhoneMicFallbackFlow()
  renderControlFocus()
}

async function runPhoneMicFallbackFlow(): Promise<void> {
  const bridge = getBridge()
  await stopActiveGlassMicProbe?.()
  stopActiveGlassMicProbe = undefined
  voicePageState = 'idle'
  setVoiceStatus('正在请求手机/蓝牙耳机麦克风兜底...')
  setVoiceTranscript('')

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
    const tracks = stream.getAudioTracks()
    const label = tracks[0]?.label || '手机/耳机麦克风'
    for (const track of stream.getTracks()) track.stop()
    const message = `手机/蓝牙耳机麦克风可用：${label}。当前真实 ASR 未配置，请先用文字输入完成问答。`
    setVoiceStatus(message)
    setVoiceTranscript('麦克风兜底已验证，可采集；等待真实 ASR 接入。')
    await showOnG2(bridge, formatForG2('手机麦克风可用', 'ASR 未配置\n请先用文字输入'))
  } catch (error) {
    const reason = classifyMicError(error)
    setVoiceStatus(`手机/蓝牙耳机麦克风失败：${reason.long}`)
    await showOnG2(bridge, formatForG2('麦克风失败', reason.short))
  }
}

function bindPhoneHoldVoiceButton(): void {
  document
    .querySelectorAll<HTMLButtonElement>('#voice-orb-action')
    .forEach(bindHoldToTalkButton)
}

function bindHoldToTalkButton(button: HTMLButtonElement): void {
  if (button.dataset.holdBound === 'true') return
  button.dataset.holdBound = 'true'
  button.style.touchAction = 'none'

  const start = (event: Event) => {
    event.preventDefault()
    setInteractionFeedback('开始录音，保持按住。松开后识别')
    void startHoldToTalkSession({ mode: 'asr' })
  }
  const stop = (event: Event) => {
    event.preventDefault()
    setInteractionFeedback('录音结束，正在转文字')
    void stopHoldToTalkSession('released')
  }

  if ('PointerEvent' in window) {
    button.addEventListener('pointerdown', (event) => {
      start(event)
      try {
        button.setPointerCapture(event.pointerId)
      } catch {}
    })
    button.addEventListener('pointerup', stop)
    button.addEventListener('pointercancel', (event) => {
      event.preventDefault()
      setInteractionFeedback('触摸被系统打断，录音仍继续；再次点击可结束')
    })
    button.addEventListener('lostpointercapture', () => {
      if (phoneHoldRecorder || activeG2PcmVoiceSession) {
        setInteractionFeedback('录音保持中，再次点击结束')
      }
    })
  } else {
    button.addEventListener('touchstart', start, { passive: false })
    button.addEventListener('touchend', stop, { passive: false })
    button.addEventListener('mousedown', start)
    button.addEventListener('mouseup', stop)
  }

  button.addEventListener('click', (event) => {
    event.preventDefault()
    setInteractionFeedback(`${getAdaptiveVoiceHint()}，按住说话，松开后发送`)
  })
}

function setVoiceRecordingButtons(recording: boolean, elapsedMs = 0, maxMs = getVoiceRecordMaxMs()): void {
  document.querySelectorAll<HTMLButtonElement>('#voice-orb-action').forEach((button) => {
    button.classList.toggle('is-recording', recording)
    button.setAttribute('aria-pressed', recording ? 'true' : 'false')
    const label = button.querySelector<HTMLElement>('.voice-orb-label')
    if (label) {
      label.textContent = recording
        ? `录音 ${(elapsedMs / 1000).toFixed(1)}s / ${(maxMs / 1000).toFixed(0)}s`
        : '按住说话'
    }
  })
}

function getVoiceRecordMaxMs(): number {
  const configured = Number(getAppConfig().g2RecordMs)
  if (!Number.isFinite(configured) || configured < 120000) return 120000
  return Math.min(120000, configured)
}

async function startPhoneHoldVoiceCapture(): Promise<void> {
  if (phoneHoldRecorder) return

  void unlockAudioPlayback()
  selectG2Bookmark('voice')
  await stopActiveGlassMicProbe?.()
  stopActiveGlassMicProbe = undefined
  voicePageState = 'listening'
  phoneHoldStartedAt = performance.now()
  phoneHoldStopping = false
  const maxMs = getVoiceRecordMaxMs()
  setVoiceRecordingButtons(true, 0, maxMs)

  const updateHoldStatus = (hint = '正在录音采集手机/耳机麦克风') => {
    const elapsed = Math.min(maxMs, performance.now() - phoneHoldStartedAt)
    setVoiceRecordingButtons(true, elapsed, maxMs)
    setVoiceStatus(`${hint}：${(elapsed / 1000).toFixed(1)}s / ${(maxMs / 1000).toFixed(0)}s，松开后发送。`)
    updateVoiceDebug({
      voicePageState: 'listening',
      micSource: 'phone',
      wsStatus: 'idle',
      audioControlCalled: false,
      totalBytes: 0,
      chunks: 0,
      lastChunkBytes: 0,
      lastChunkAt: '--',
      noPcmTimeout: false,
      lastVoiceError: '',
      lastServerAudioDebug: 'phone-media-recorder',
    })
  }

  try {
    phoneHoldRecorder = await startPhoneMicRecorder()
    updateHoldStatus()
    setVoiceTranscript('正在录音，松开后转文字。')
    phoneHoldTimer = window.setInterval(updateHoldStatus, 500)
    phoneHoldMaxTimer = window.setTimeout(() => {
      if (phoneHoldRecorder) void stopPhoneHoldVoiceCapture('release')
    }, maxMs)
  } catch (error) {
    const reason = classifyMicError(error)
    setVoiceStatus(`手机/耳机麦克风采集失败：${reason.long}`)
    updateVoiceDebug({
      lastVoiceError: reason.long,
      lastServerAudioDebug: 'phone-media-recorder-start-failed',
    })
    phoneHoldRecorder = undefined
    stopPhoneHoldUi()
  }
}

async function stopPhoneHoldVoiceCapture(reason: 'release' | 'cancel' | 'finished'): Promise<void> {
  if (phoneHoldStopping) return
  const recorder = phoneHoldRecorder
  if (!recorder) {
    stopPhoneHoldUi()
    return
  }

  phoneHoldStopping = true
  phoneHoldRecorder = undefined
  stopPhoneHoldUi()

  if (reason === 'cancel') {
    recorder.cancel()
    setVoiceStatus('语音采集已取消。')
    updateVoiceDebug({ voicePageState: 'idle', micSource: 'none' })
    phoneHoldStopping = false
    return
  }

  try {
    setVoiceStatus('语音已采集，正在上传转文字。')
    const recording = await recorder.stop()
    updateVoiceDebug({
      totalBytes: recording.sizeBytes,
      chunks: 1,
      lastChunkBytes: recording.sizeBytes,
      lastChunkAt: new Date().toLocaleTimeString(),
      lastServerAudioDebug: `${recording.mimeType} ${(recording.durationMs / 1000).toFixed(1)}s`,
      lastVoiceError: '',
    })
    setVoiceTranscript(`已录音：${Math.round(recording.sizeBytes / 1024)} KB，${(recording.durationMs / 1000).toFixed(1)} 秒。`)

    const result = await transcribePhoneAudio(recording)
    if (!result.text.trim()) {
      const message = getPhoneAsrPendingMessage(result.provider, recording.sizeBytes, recording.durationMs)
      setVoiceStatus(message)
      setVoiceTranscript(message)
      updateVoiceDebug({ lastVoiceError: message, lastServerAudioDebug: result.provider })
      return
    }

    setVoiceTranscript(`听到：${result.text}`)
    setVoiceStatus('语音已转文字，天禄正在处理。')
    await handleTranscript(result.text, {
      source: 'phone-media-recorder',
      durationMs: recording.durationMs,
      totalBytes: recording.sizeBytes,
      mode: 'asr',
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    setVoiceStatus(`手机/耳机语音采集失败：${message}`)
    updateVoiceDebug({ lastVoiceError: message })
  } finally {
    phoneHoldStopping = false
  }
}

function stopPhoneHoldUi(): void {
  if (phoneHoldTimer) {
    window.clearInterval(phoneHoldTimer)
    phoneHoldTimer = undefined
  }
  if (phoneHoldMaxTimer) {
    window.clearTimeout(phoneHoldMaxTimer)
    phoneHoldMaxTimer = undefined
  }
  setVoiceRecordingButtons(false)
}

async function handleTranscript(
  text: string,
  meta: { source?: string; durationMs?: number; totalBytes?: number; mode?: string } = {},
): Promise<void> {
  const original = text.trim()
  if (!original) {
    setVoiceStatus('没有识别到有效文字，请重试或使用手动发送。')
    return
  }

  const normalized = normalizeTianluTranscript(original)
  setVoiceTranscript(`听到：${original}\n处理：${normalized}`)
  setVoiceStatus('天禄正在处理语音内容...')
  updateVoiceDebug({
    voicePageState: 'transcribing',
    lastTranscript: original,
    normalizedTranscript: normalized,
    totalBytes: meta.totalBytes ?? voiceProbeDebug.totalBytes,
    lastServerAudioDebug: meta.source ?? voiceProbeDebug.lastServerAudioDebug,
  })
  await createGlassRenderer(getBridge()).show('voice_transcript', { transcript: normalized })
  await routeVoiceIntent(normalized || original)
}

async function routeVoiceIntent(text: string): Promise<void> {
  if (isTradingVoiceIntent(text)) {
    updateVoiceDebug({ lastIntent: 'trading' })
    await handleTradingVoiceIntent(text)
    return
  }

  if (isVisionVoiceIntent(text)) {
    updateVoiceDebug({ lastIntent: 'vision' })
    await handleVisionVoiceIntent(text)
    return
  }

  updateVoiceDebug({ lastIntent: 'general' })
  await handleGeneralAssistantIntent(text)
}

async function handleVisionVoiceIntent(text: string): Promise<void> {
  const bridge = getBridge()
  const renderer = createGlassRenderer(bridge)
  const opId = startGlassOperation()
  if (!isGlassOperationValid(opId)) return
  await renderer.show('voice_to_vision')
  if (!isGlassOperationValid(opId)) return

  if (lastVisionSummary && isRecentVisionReference(text)) {
    const answer = `基于最近视觉结果：${lastVisionSummary}`
    setVoiceStatus('已基于最近视觉结果回答。')
    setVoiceTranscript(`你：${text}\n天禄：${answer}`)
    addHistory({ kind: 'voice', title: '视觉语音问答', input: text, answer, detail: lastVisionSummary })
    renderHistory()
    updateVoiceDebug({ voicePageState: 'answer', lastIntent: 'vision', lastAnswer: answer })
    await renderer.show('voice_answer', { answer })
    await speakIfEnabled(answer)
    return
  }

  const captured = await tryAutoCaptureFromVoice(text, `你好天禄，${text}`)
  if (captured) return

  if (lastVisionSummary) {
    const answer = `自动看图未启动，先基于最近视觉结果回答：${lastVisionSummary}`
    setVoiceStatus('自动看图未启动，已改用最近视觉结果回答。')
    setVoiceTranscript(`你：${text}\n天禄：${answer}`)
    addHistory({ kind: 'voice', title: '视觉语音问答', input: text, answer, detail: lastVisionSummary })
    renderHistory()
    updateVoiceDebug({ voicePageState: 'answer', lastIntent: 'vision', lastAnswer: answer })
    await renderer.show('voice_answer', { answer })
    await speakIfEnabled(answer)
    return
  }

  const answer = '检测到你想让我看画面。请先进入视觉识别，或在手机端拍照/选图，识别后我会继续回答。'
  setVoiceStatus(answer)
  setVoiceTranscript(`你：${text}\n天禄：${answer}`)
  updateVoiceDebug({ voicePageState: 'answer', lastIntent: 'vision', lastAnswer: answer })
  await renderer.show('voice_answer', { answer })
  await speakIfEnabled(answer)
}

async function handleTradingVoiceIntent(text: string): Promise<void> {
  const bridge = getBridge()
  const renderer = createGlassRenderer(bridge)
  const opId = startGlassOperation()
  if (!isGlassOperationValid(opId)) return
  setVoiceStatus('正在读取实时交易只读数据...')
  setVoiceTranscript(`你：${text}\n天禄：正在读取实时交易状态`)
  await renderer.show('voice_transcript', { transcript: text })
  if (!isGlassOperationValid(opId)) return

  try {
    // 根据关键词路由到对应子页面
    const routedIndex = routeTradingQuery(text)
    const overview = await getTradingOverview()
    lastTradingOverview = overview
    const live = overview.live
    // 预填充所有子页面缓存
    tradingSubPageCache = [
      { tradingState: buildTradingState(live) },
      { extendedData: { prices: live?.whitelistPrices?.map((p) => ({ symbol: p.symbol, pair: p.pair, price: p.price, freshness: p.freshness })) } },
      { extendedData: { positions: live?.openPositionPairs?.map((p) => ({ pair: p.pair, pnl: p.pnl, notional: p.notional, share: p.share, maxLeverage: p.maxLeverage })), totalUnrealizedPnl: live?.totalUnrealizedPnl, openPositions: live?.openPositions } },
      { extendedData: { distribution: live?.pairConcentration?.map((d) => ({ pair: d.pair, share: d.share * 100, pnl: d.pnl })) } },
      { extendedData: { attribution: live?.attribution ? { winRatePct: live.attribution.winRatePct, avgRealizedPnlPct: live.attribution.avgRealizedPnlPct, avgUnrealizedPnlPct: live.attribution.avgUnrealizedPnlPct, sampleCount: live.attribution.sampleCount } : undefined } },
      { extendedData: { alerts: live?.alarms?.map((a) => ({ level: a.level, message: a.message, action: a.action })) } },
    ]
    const answer = formatScopedAnswer(text, routedIndex, live)
    renderPhoneTradingSubPage(routedIndex, tradingSubPageCache[routedIndex] ?? {})
    setVoiceStatus('交易只读状态已更新。')
    setVoiceTranscript(`你：${text}\n天禄：${answer}`)
    addHistory({
      kind: 'voice',
      title: '交易语音问答',
      input: text,
      answer,
    })
    addHistory({
      kind: 'trading',
      title: '语音触发交易只读',
      input: text,
      answer,
    })
    renderHistory()
    updateVoiceDebug({ voicePageState: 'answer', lastIntent: 'trading', lastAnswer: answer })
    activeGlassPage = 'trading'
    inTradingMenu = false
    tradingSubPageIndex = routedIndex
    await renderer.show('voice_answer', { answer })
    await speakIfEnabled(answer)
  } catch (error) {
    const message = `交易实时只读读取失败：${error instanceof Error ? error.message : String(error)}`
    setVoiceStatus(message)
    setVoiceTranscript(`你：${text}\n天禄：${message}`)
    updateVoiceDebug({ voicePageState: 'error', lastIntent: 'trading', lastVoiceError: message })
    await renderer.show('voice_error', { body: message })
  }
}

function routeTradingQuery(text: string): number {
  if (/白名单|价格|合约价格|交易价格|盘口|买入价|卖出价/.test(text)) return 1
  if (/持仓|盈亏|pnl|PnL|仓位|多头|空头|未平仓/.test(text)) return 2
  if (/分布|资金分布|占比|集中度|筹码/.test(text)) return 3
  if (/归因|胜率|均盈|均亏|订单归因|交易统计/.test(text)) return 4
  if (/告警|风控|警报|风险提示|预警/.test(text)) return 5
  return 0
}

function formatScopedAnswer(text: string, index: number, live: NonNullable<TradingReadonlyOverview['live']> | undefined): string {
  const answers: string[] = []
  switch (index) {
    case 1: { // 白名单价格
      const prices = live?.whitelistPrices ?? []
      if (!prices.length) return '当前白名单价格数据为空。'
      answers.push(`共 ${prices.length} 个白名单品种：`)
      for (const p of prices.slice(0, 5)) {
        answers.push(`${p.symbol} ${p.pair} $${p.price.toFixed(p.price < 1 ? 4 : 2)}`)
      }
      break
    }
    case 2: { // 持仓盈亏
      const positions = live?.openPositionPairs ?? []
      const totalPnl = live?.totalUnrealizedPnl
      const openPos = live?.openPositions ?? 0
      answers.push(`持仓 ${openPos} 个，未实现盈亏 ${totalPnl != null ? `${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(2)}` : '--'}`)
      for (const p of positions.slice(0, 4)) {
        answers.push(`${p.pair} ${p.pnl != null ? `${p.pnl >= 0 ? '+' : ''}${p.pnl.toFixed(2)}` : '--'}`)
      }
      break
    }
    case 3: { // 资金分布
      const dist = live?.pairConcentration ?? []
      if (!dist.length) return '当前资金分布数据为空。'
      for (const d of dist.slice(0, 5)) {
        answers.push(`${d.pair} ${(d.share * 100).toFixed(1)}%${d.pnl != null ? ` ${d.pnl >= 0 ? '+' : ''}$${d.pnl.toFixed(0)}` : ''}`)
      }
      break
    }
    case 4: { // 订单归因
      const attr = live?.attribution
      if (!attr) return '当前订单归因数据为空。'
      const wr = attr.winRatePct ?? 0
      const ar = attr.avgRealizedPnlPct ?? 0
      const au = attr.avgUnrealizedPnlPct ?? 0
      answers.push(`胜率 ${wr.toFixed(1)}%  均盈 ${ar >= 0 ? '+' : ''}${ar.toFixed(2)}%  均亏 ${au >= 0 ? '+' : ''}${au.toFixed(2)}%  ${attr.sampleCount ?? 0}单`)
      break
    }
    case 5: { // 风控告警
      const alerts = live?.alarms ?? []
      if (!alerts.length) return '当前无风控告警，仓位风险正常。'
      for (const a of alerts.slice(0, 4)) {
        answers.push(`${a.level === 'critical' || a.level === 'high' ? '⚠' : a.level === 'medium' ? '→' : '·'} ${a.message}`)
      }
      break
    }
    default: { // 运行状态（总览）
      const online = (live?.portsOnline ?? 0) > 0
      const strategy = live?.autopilotEnabled ? '自动驾驶' : '手动'
      const positions = live?.openPositions ?? '--'
      const orders = live?.dataSources?.length ?? '--'
      const pnl = live?.totalUnrealizedPnl
      const risk = live?.riskLevel ?? '--'
      answers.push(`运行${online ? '正常' : '需关注'}  策略：${strategy}  持仓：${positions}  挂单：${orders}  未实现盈亏：${pnl != null ? `${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}` : '--'}  风险：${risk}`)
      break
    }
  }
  return answers.join('\n')
}

async function handleGeneralAssistantIntent(text: string): Promise<void> {
  await runAssistantQuestion(`你好天禄，${text}`)
}

function buildFrontendGeneralFallback(question: string): string {
  if (/附近|周边|好玩|好吃|景点|古迹|旅游|南洋|南新世|南浔|南新/.test(question)) {
    return [
      '我现在没有拿到实时定位和联网搜索结果，只能先按通用口径回答。',
      '建议优先看：当地历史街区、博物馆/古迹、老街夜市、评分高的本地小吃店。',
      '吃的方面可按“本地特色菜、老字号、早餐小吃、夜市摊位”四类去找。',
      '如果你告诉我具体城市或把地图/街景拍给我，我可以继续帮你缩小到可执行路线。',
    ].join('\n')
  }

  return [
    '我没有拿到足够的实时外部资料，但可以先给出直接建议。',
    '请补充地点、对象或截图；如果是交易问题，请说“交易状态”或“持仓风险”。',
    '如果是看图问题，请说“看一下这是什么”，我会转到视觉识别流程。',
  ].join('\n')
}

function normalizeTianluTranscript(transcript: string): string {
  const normalized = transcript.replace(/[，。！？,.!?]/g, ' ').replace(/\s+/g, ' ').trim()
  return normalized
    .replace(/^(你好)?\s*(天禄|天路|添禄|天鹿|天录)\s*/, '')
    .trim() || normalized
}

function isVisionVoiceIntent(text: string): boolean {
  return /(?:帮我|你帮我)?(?:看看|看一下|看一看|看一眼|瞧一下|瞧一瞧|瞅一下|瞅一瞅|看这个|看这里|看前面)|(?:这是啥|这是什么|这是什么呀|这是什么东西)|(?:识别一下|识别这个|拍一下|拍照|读一下|读这段|屏幕内容|图片内容|前面是什么|看看屏幕|看看前面)/.test(text)
}

function isRecentVisionReference(text: string): boolean {
  return /刚才|最近|上次|之前|前面识别|刚刚识别|刚识别|上一张|上一次/.test(text)
}

function isTradingVoiceIntent(text: string): boolean {
  return /交易机器人|机器人运行|运行如何|状态如何|今天收益|收益|PnL|pnl|风险|持仓|挂单|交易状态|白名单|价格/.test(text)
}

async function runAssistantQuestion(transcript: string): Promise<void> {
  const bridge = getBridge()
  const renderer = createGlassRenderer(bridge)
  const question = extractTianluQuestion(transcript)
  const finalQuestion = question || transcript.trim()

  if (!finalQuestion) {
    const hint = '请输入或说出问题，例如：你好天禄，帮我看一下。'
    setVoiceStatus(hint)
    await showOnG2(bridge, formatForG2('未输入问题', hint))
    return
  }

  if (isVisionIntent(finalQuestion) && !isTradingVoiceIntent(finalQuestion)) {
    const autoCaptured = await tryAutoCaptureFromVoice(finalQuestion, transcript)
    if (autoCaptured) return

    setVoiceTranscript(`你：${transcript}\n天禄：正在打开相机看图`)
    setVoiceStatus('检测到看图意图，正在打开相机；拍照后会自动上传识别。')
    const input = document.querySelector<HTMLTextAreaElement>('#text-question-input')
    if (input) input.value = ''
    await showOnG2(bridge, formatForG2('天禄看图', '正在打开相机\n拍照后自动识别'))
    await runCaptureFlow(finalQuestion)
    return
  }

  setVoiceTranscript(`你：${transcript}`)
  setVoiceStatus('天禄思考中...')
  await renderer.show('voice_transcript', { transcript: finalQuestion })
  const shouldAttachLocation = !isTradingVoiceIntent(finalQuestion)
  const locationContext = shouldAttachLocation
    ? formatLocationForPrompt(await getLocationContext(getAppConfig().enableLocationContext, { resolveAddress: true }))
    : undefined
  const response = await askAssistant(finalQuestion, lastVisionSummary, {
    capturedAt: new Date().toISOString(),
    locationContext,
  })
  const sanitizedAnswer = sanitizeDirectTianluAnswer(response.answer)
  const answer = isFallbackOnlyAnswer(sanitizedAnswer) ? buildFrontendGeneralFallback(finalQuestion) : sanitizedAnswer
  const input = document.querySelector<HTMLTextAreaElement>('#text-question-input')
  if (input) input.value = ''
  addHistory({
    kind: 'voice',
    title: question ? '天禄语音问答' : '手动文本对话',
    input: transcript,
    answer,
    detail: [
      response.provider ? `来源：${response.provider}` : '',
      locationContext ? `实时定位上下文：${locationContext}` : '',
      lastVisionSummary ? `最近画面：${lastVisionSummary}` : '',
    ]
      .filter(Boolean)
      .join('\n') || undefined,
  })
  renderHistory()

  setVoiceStatus('天禄已回答')
  setVoiceTranscript(`你：${transcript}\n天禄：${answer}`)
  updateVoiceDebug({ voicePageState: 'answer', lastAnswer: answer })
  await renderer.show('reply', { answer })

  await speakIfEnabled(answer)
}

function sanitizeDirectTianluAnswer(answer: string): string {
  const original = answer.trim()
  if (!original) return '天禄没有拿到有效回答，请再问一次或换个说法。'

  const lines = original
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => !/telegram|电报|tg|第三方平台|稍后发送|完成后会传|完成後會傳|传到手机|發到手機|发到手机/i.test(line))

  let cleaned = lines.join('\n').trim()
  cleaned = cleaned
    .replace(/[🦞📱]/g, '')
    .replace(/(完成[后後]|稍后|稍後).{0,18}(Telegram|电报|TG|手机|第三方平台).*/gi, '')
    .replace(/(会|會|将|將).{0,10}(传|傳|发|發|发送|推送).{0,18}(Telegram|电报|TG|手机|第三方平台).*/gi, '')
    .trim()

  if (!cleaned || isInvalidTianluAnswer(cleaned)) {
    return '天禄没有拿到有效回答，请再问一次或换个说法。'
  }

  return cleaned
}

function isFallbackOnlyAnswer(answer: string): boolean {
  return /天禄没有拿到有效回答|请再问一次|换个说法/.test(answer)
}

function isInvalidTianluAnswer(answer: string): boolean {
  return /我已收到问题|收到问题|把结果直接显示|结果直接显示在这里|會把結果直接顯示在這裡|正在分析研究|完成后会传|完成後會傳|telegram|电报|tg|第三方平台/i.test(answer)
}

// 交易子页面辅助函数：显示6个交易分类页面
const TRADING_SUB_PAGES = ['trading_status', 'trading_prices', 'trading_positions', 'trading_distribution', 'trading_attribution', 'trading_alerts'] as const

function populateTradingCache(overview: TradingReadonlyOverview): void {
  lastTradingOverview = overview
  lastTradingFetchedAt = Date.now()
  const live = overview.live
  tradingSubPageCache = [
    { tradingState: buildTradingState(live) },
    { extendedData: { prices: live?.whitelistPrices?.map((p) => ({ symbol: p.symbol, pair: p.pair, price: p.price, freshness: p.freshness })) } },
    { extendedData: { positions: live?.openPositionPairs?.map((p) => ({ pair: p.pair, pnl: p.pnl, notional: p.notional, share: p.share, maxLeverage: p.maxLeverage })), totalUnrealizedPnl: live?.totalUnrealizedPnl, openPositions: live?.openPositions } },
    { extendedData: { distribution: live?.pairConcentration?.map((d) => ({ pair: d.pair, share: d.share * 100, pnl: d.pnl })) } },
    { extendedData: { attribution: live?.attribution ? { winRatePct: live.attribution.winRatePct, avgRealizedPnlPct: live.attribution.avgRealizedPnlPct, avgUnrealizedPnlPct: live.attribution.avgUnrealizedPnlPct, sampleCount: live.attribution.sampleCount } : undefined } },
    { extendedData: { alerts: live?.alarms?.map((a) => ({ level: a.level, message: a.message, action: a.action })) } },
  ]
}

function isTradingCacheFresh(): boolean {
  return Boolean(lastTradingOverview && Date.now() - lastTradingFetchedAt < TRADING_CACHE_TTL_MS)
}

async function refreshTradingOverviewCache(): Promise<TradingReadonlyOverview> {
  if (!tradingRefreshPromise) {
    tradingRefreshPromise = getTradingOverview()
      .then((overview) => {
        populateTradingCache(overview)
        return overview
      })
      .finally(() => {
        tradingRefreshPromise = undefined
      })
  }
  return tradingRefreshPromise
}

function getTradingMenuExtendedData(statusText?: string): { prices?: Array<{ symbol: string; pair: string; price: number; freshness?: string }>; statusText?: string } {
  const prices = lastTradingOverview?.live?.whitelistPrices?.map((p) => ({ symbol: p.symbol, pair: p.pair, price: p.price, freshness: p.freshness }))
  return { prices, statusText }
}

// 各子页面独立拉取数据
async function showTradingSubPage(index: number, renderer: GlassRenderer, options: { forceRefresh?: boolean } = {}): Promise<void> {
  const currentIndex = index
  if (switchingSubPage) return
  switchingSubPage = true
  tradingSubPageIndex = currentIndex
  inTradingMenu = false

  try {
    const screenId = TRADING_SUB_PAGES[currentIndex]!
    const hasCache = Boolean(tradingSubPageCache[currentIndex])

    if (!hasCache) {
      await renderer.show('trading_menu', { activeIndex: currentIndex, extendedData: getTradingMenuExtendedData('正在载入交易数据') })
      try {
        await refreshTradingOverviewCache()
      } catch {
        tradingSubPageCache[currentIndex] = {}
      }
    } else if (options.forceRefresh || !isTradingCacheFresh()) {
      const staleCache = tradingSubPageCache[currentIndex] ?? {}
      await showTradingScreen(renderer, screenId, staleCache, '显示上次缓存 · 刷新中')
      void refreshTradingOverviewCache().then(() => {
        if (activeGlassPage === 'trading' && tradingSubPageIndex === currentIndex) {
          void showTradingScreen(renderer, screenId, tradingSubPageCache[currentIndex] ?? {}, undefined)
          renderPhoneTradingSubPage(currentIndex, tradingSubPageCache[currentIndex] ?? {})
        }
      }).catch(() => undefined)
    }

    const cache = tradingSubPageCache[currentIndex] ?? {}
    await showTradingScreen(renderer, screenId, cache, undefined)

    // 更新手机网页面板
    renderPhoneTradingSubPage(currentIndex, cache)

    // 朗读AI评测话术
    const live = lastTradingOverview?.live
    const aiComment = formatScopedAnswer('', currentIndex, live)
    await speakIfEnabled(aiComment)
  } finally {
    switchingSubPage = false
  }
}

async function showTradingScreen(
  renderer: GlassRenderer,
  screenId: (typeof TRADING_SUB_PAGES)[number],
  cache: { extendedData?: any; tradingState?: any },
  statusText?: string,
): Promise<void> {
  const extendedData = { ...(cache.extendedData ?? {}), statusText }
  if (screenId === 'trading_status') {
    await renderer.show('trading_status', { trading: cache.tradingState, extendedData })
  } else {
    await renderer.show(screenId as 'trading_prices' | 'trading_positions' | 'trading_distribution' | 'trading_attribution' | 'trading_alerts', { extendedData })
  }
}

function renderPhoneTradingSubPage(index: number, cache: { extendedData?: any; tradingState?: any }): void {
  const hits = document.querySelector('#trading-hits')
  const summary = document.querySelector('#trading-summary')
  const mode = document.querySelector('#trading-mode')
  if (!hits || !summary) return
  if (mode) mode.textContent = '实时只读已开启'

  const labels = ['运行状态', '白名单价格', '持仓盈亏', '资金分布', '订单归因', '风控告警']
  summary.textContent = labels[index] ?? ''

  const data = cache.extendedData ?? cache.tradingState
  const NAMES = ['运行状态', '白名单价格', '持仓盈亏', '资金分布', '订单归因', '风控告警']

  // 生成 AI 评测话术
  const live = lastTradingOverview?.live
  const aiComment = formatScopedAnswer('', index, live)

  if (!data) {
    hits.innerHTML = `<div class="trading-hit"><strong>【${NAMES[index]}】</strong><br/><em>暂无数据，请先刷新。</em></div>`
    return
  }

  let html = `<div class="trading-hit"><strong>【${NAMES[index]}】</strong><br/><br/>`
  html += `<em>天禄点评：</em><br/>${aiComment.replace(/\n/g, '<br/>')}<br/><br/>`
  html += `<em>原始数据：</em><br/>`

  switch (index) {
    case 0: { // 运行状态
      const s = data as { online?: boolean; heartbeat?: string; strategy?: string; positions?: string; orders?: string; pnl?: string; risk?: string }
      html += `运行 ${s.online === false ? '需关注' : '正常'} &nbsp; 心跳：${s.heartbeat ?? '--'} &nbsp; 策略：${s.strategy ?? '--'}<br/>`
      html += `持仓：${s.positions ?? '--'} &nbsp; 挂单：${s.orders ?? '--'}<br/>`
      html += `未实现盈亏：${s.pnl ?? '--'} &nbsp; 风险：${s.risk ?? '--'}`
      break
    }
    case 1: { // 白名单价格
      const prices = (data as { prices?: Array<{ symbol: string; pair: string; price: number; freshness?: string }> }).prices ?? []
      if (!prices.length) { html += '暂无价格数据。'; break }
      for (const p of prices.slice(0, 8)) {
        html += `${p.symbol} ${p.pair} $${p.price.toFixed(p.price < 1 ? 4 : 2)}<br/>`
      }
      break
    }
    case 2: { // 持仓盈亏
      const positions = (data as { positions?: Array<{ pair: string; pnl?: number }> }).positions ?? []
      const totalPnl = (data as { totalUnrealizedPnl?: number }).totalUnrealizedPnl
      const openPos = (data as { openPositions?: number }).openPositions ?? 0
      html += `持仓 ${openPos} 个 · 未实现盈亏 ${totalPnl != null ? `${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(2)}` : '--'}<br/>`
      for (const p of positions.slice(0, 6)) {
        html += `${p.pair} ${p.pnl != null ? `${p.pnl >= 0 ? '+' : ''}$${p.pnl.toFixed(2)}` : '--'}<br/>`
      }
      break
    }
    case 3: { // 资金分布
      const dist = (data as { distribution?: Array<{ pair: string; share: number; pnl?: number }> }).distribution ?? []
      if (!dist.length) { html += '暂无分布数据。'; break }
      for (const d of dist.slice(0, 6)) {
        html += `${d.pair} ${d.share.toFixed(1)}%${d.pnl != null ? ` ${d.pnl >= 0 ? '+' : ''}$${d.pnl.toFixed(0)}` : ''}<br/>`
      }
      break
    }
    case 4: { // 订单归因
      const attr = (data as { attribution?: { winRatePct?: number; avgRealizedPnlPct?: number; avgUnrealizedPnlPct?: number; sampleCount?: number } }).attribution
      if (!attr) { html += '暂无归因数据。'; break }
      const wr = attr.winRatePct ?? 0, ar = attr.avgRealizedPnlPct ?? 0, au = attr.avgUnrealizedPnlPct ?? 0
      html += `胜率 ${wr.toFixed(1)}% &nbsp; 均盈 ${ar >= 0 ? '+' : ''}${ar.toFixed(2)}% &nbsp; 均亏 ${au >= 0 ? '+' : ''}${au.toFixed(2)}%<br/>`
      html += `样本 ${attr.sampleCount ?? 0} 单`
      break
    }
    case 5: { // 风控告警
      const alerts = (data as { alerts?: Array<{ level?: string; message?: string }> }).alerts ?? []
      if (!alerts.length) { html += '当前无告警，仓位风险正常。'; break }
      for (const a of alerts.slice(0, 5)) {
        const mark = a.level === 'critical' || a.level === 'high' ? '⚠' : a.level === 'medium' ? '→' : '·'
        html += `${mark} ${a.message ?? '无描述'}<br/>`
      }
      break
    }
  }
  html += '</div>'
  hits.innerHTML = html
}

async function runTradingOverview(): Promise<void> {
  const bridge = getBridge()
  const renderer = createGlassRenderer(bridge)
  const button = document.querySelector<HTMLButtonElement>('#trading-button')
  const refreshButton = document.querySelector<HTMLButtonElement>('#refresh-trading-button')

  try {
    stopAutoVoiceDetection()
    selectG2Bookmark('trading')
    activeGlassPage = 'trading'
    inTradingMenu = true
    tradingSubPageIndex = 0
    tradingPanelActive = true
    button?.setAttribute('disabled', 'true')
    refreshButton?.setAttribute('disabled', 'true')
    await renderer.show('trading_menu', {
      activeIndex: 0,
      extendedData: getTradingMenuExtendedData(lastTradingOverview ? '显示上次缓存 · 刷新中' : '正在载入交易数据'),
    })

    const overview = isTradingCacheFresh() ? lastTradingOverview! : await refreshTradingOverviewCache()
    const summary = formatTradingOverviewSummary(overview)
    setTradingMode(overview.mode === 'live-readonly' ? '实时只读已开启' : '记忆只读模式')
    setTradingSummary('数据已就绪，请选择分类查看')
    addHistory({
      kind: 'trading',
      title: '交易只读概览',
      input: '交易状态',
      answer: summary,
    })
    renderHistory()
    // Re-render glass with populated cache so price strip shows immediately
    if (lastTradingOverview?.live?.whitelistPrices?.length) {
      await renderer.show('trading_menu', {
        activeIndex: tradingSubPageIndex,
        extendedData: getTradingMenuExtendedData(),
      })
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    setTradingMode('刷新失败')
    setTradingSummary(message)
    await renderer.show('error', { body: message })
  } finally {
    button?.removeAttribute('disabled')
    refreshButton?.removeAttribute('disabled')
    renderControlFocus()
  }
}

async function runOpenClawFlow(): Promise<void> {
  const bridge = getBridge()
  stopAutoVoiceDetection()
  setVoiceStatus('正在进入 OpenCLAW / 天禄语音通道...')
  setVoiceTranscript('')
  await showOnG2(bridge, formatForG2('OpenCLAW', 'R1 已确认\n正在连接 G2 麦克风'))

  const status = await getOpenClawStatus().catch(() => undefined)
  if (!status?.enabled) {
    setVoiceStatus('OpenCLAW 当前未启用；仍会通过本地只读交易状态 fallback 回答。')
  }

  if (!bridge) {
    setVoiceStatus('浏览器调试模式：请在下方文字框输入 OpenCLAW 问题。')
    return
  }

  await runG2MicWebSocketVoiceFlow('openclaw')
}

async function runOpenClawBrowserVoiceFlow(prompt = '请对着手机说 OpenCLAW 问题。'): Promise<void> {
  const bridge = getBridge()
  setVoiceStatus(`${prompt} 当前版本已禁用浏览器麦克风主链路，请用 G2 MicProbe 或文字输入。`)
  setVoiceTranscript('')
  await showOnG2(bridge, formatForG2('OpenCLAW 语音', '请在 G2 真机测试 PCM\n浏览器麦克风不是主路径'))
  renderControlFocus()
}

async function runOpenClawQuestion(transcript: string): Promise<void> {
  const bridge = getBridge()
  const renderer = createGlassRenderer(bridge)
  const question = extractTianluQuestion(transcript) || transcript.trim()
  if (!question) {
    setVoiceStatus('请输入 OpenCLAW 问题。')
    return
  }

  setVoiceStatus('OpenCLAW 思考中...')
  setVoiceTranscript(`你：${transcript}`)
  await renderer.show('voice_transcript', { transcript: question })

  const response = await askOpenClaw(question, lastVisionSummary)
  addHistory({
    kind: 'openclaw',
    title: 'OpenCLAW 对话',
    input: transcript,
    answer: response.answer,
    detail: response.provider,
  })
  renderHistory()

  const input = document.querySelector<HTMLTextAreaElement>('#text-question-input')
  if (input) input.value = ''
  setVoiceStatus(`OpenCLAW 已回答：${response.provider}`)
  setVoiceTranscript(`你：${transcript}\nOpenCLAW：${response.answer}`)
  await renderer.show('reply', { answer: response.answer })
  await speakIfEnabled(response.answer)
}

async function executeFocusedControl(): Promise<void> {
  await unlockAudioPlayback()
  const control = getSelectableControls()[selectedControlIndex]
  if (!control) {
    await renderG2Bookmark()
    return
  }

  if (control.id === 'capture-button') {
    selectG2Bookmark('vision')
    await runDirectVisionCaptureFromR1('camera')
    return
  }
  if (control.id === 'voice-button') {
    await enterVoicePage({ autoStart: true })
    return
  }
  if (control.id === 'trading-button') {
    selectG2Bookmark('trading')
    await runTradingOverview()
    return
  }
  if (control.id === 'settings-button') {
    selectG2Bookmark('settings')
    await enterSettingsPage()
    return
  }
  if (control.id === 'openclaw-button') {
    setPhoneActiveBookmark('openclaw')
    return
  }
  if (control.id === 'history-button') {
    setPhoneActiveBookmark('history')
    renderHistory()
    return
  }
  if (control.id === 'vision-capture-action') {
    await runDirectVisionCaptureFromR1('camera')
    return
  }
  if (control.id === 'vision-replay-action' && lastSpeakText) {
    await speakIfEnabled(lastSpeakText, true)
    return
  }
  if (control.id === 'voice-diagnostic-action') {
    await startVoiceDiagnosticProbe()
    return
  }
  if (control.id === 'voice-preset-vision') {
    await runAssistantQuestion('你好天禄，帮我看一下刚才识别的内容')
    return
  }
  if (control.id === 'voice-preset-trading') {
    await runAssistantQuestion('你好天禄，查看一下今天收益和风险怎么样')
    return
  }
  if (control.id === 'trading-refresh-action') {
    await runTradingOverview()
    return
  }
  if (control.id === 'trading-preset-prices') {
    await runAssistantQuestion('查看白名单交易对的实时价格')
    return
  }
  if (control.id === 'trading-preset-risk') {
    await runAssistantQuestion('查看当前交易系统风险摘要和持仓盈亏')
    return
  }
  if (control.id === 'openclaw-record-action') {
    await runOpenClawFlow()
    return
  }
  if (control.id === 'openclaw-preset-trading') {
    await runOpenClawQuestion('请读取交易系统状态，汇总白名单价格、机器人、持仓、收益和风险，只读分析')
    return
  }
  if (control.id === 'openclaw-preset-memory') {
    await runOpenClawQuestion('请读取天禄记忆，汇总当前 G2 视觉语音助手下一步最重要的问题')
    return
  }
  if (control.id === 'refresh-trading-button') {
    await runTradingOverview()
    return
  }
  if (control.id === 'replay-speech-button') {
    await speakIfEnabled(lastSpeakText, true)
    return
  }
  if (control.id === 'confirm-camera-button') {
    const prompt = pendingVisionPrompt
    pendingVisionPrompt = ''
    hideConfirmCameraButton()
    if (prompt) await runCaptureFlow(prompt)
    return
  }
}

async function startAutoVoiceDetection(): Promise<void> {
  const bridge = getBridge()
  if (!bridge || autoVoiceDetectionRunning) return

  autoVoiceDetectionEnabled = true
  autoVoiceDetectionRunning = true
  setVoiceStatus('自动监听切换为 G2 MicProbe。请说：天禄，查看一下今天收益怎么样。')
  try {
    await runG2MicWebSocketVoiceFlow('assistant')
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    setVoiceStatus(`自动监听失败：${message}`)
    await showOnG2(bridge, formatForG2('自动监听失败', message))
  } finally {
    autoVoiceDetectionRunning = false
  }
}

function stopAutoVoiceDetection(): void {
  autoVoiceDetectionEnabled = false
}

async function prepareVoiceInput(): Promise<void> {
  const asr = await getAsrStatus().catch(() => undefined)
  voiceInputAvailable = true
  setVoiceStatus(
    asr?.available
      ? '语音问答已就绪。点击“呼叫天禄”后启动 G2 PCM MicProbe。'
      : '语音先走 G2 PCM MicProbe；真实 ASR 未就绪时用 probe mock 验证链路。',
  )
}

function disableAutoListenForNow(message: string): void {
  autoVoiceDetectionEnabled = false
  autoVoiceDetectionRunning = false

  const config = getAppConfig()
  if (config.autoListenOnStart) {
    const next = saveAppConfig({ ...config, autoListenOnStart: false })
    renderConfigPanel(next)
  }

  setVoiceStatus(message)
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

async function tryAutoCaptureFromVoice(prompt: string, transcript: string): Promise<boolean> {
  const bridge = getBridge()

  try {
    setVoiceTranscript(`你：${transcript}\n天禄：正在自动抓拍`)
    setVoiceStatus('天禄正在自动抓拍并识别...')
    await showOnG2(bridge, formatForG2('天禄看图', '正在自动抓拍\n拍后自动识别'))

    if (voiceCameraReadyPromise) await withTimeout(voiceCameraReadyPromise, 2500).catch(() => false)
    const image = await capturePreparedPhoto()
    if (!image) {
      setVoiceStatus('检测到看图意图，正在进入视觉识别流程。请按当前环境完成拍照或选图。')
      activeGlassPage = 'vision'
      selectG2Bookmark('vision')
      await showOnG2(bridge, formatForG2('天禄看图', '请完成拍照或选图\n完成后自动识别'))
      await runCaptureFlow(prompt, undefined, { source: 'voice-vision-intent' })
      return true
    }
    await runCaptureFlow(prompt, image, { source: 'voice-vision-intent' })
    return true
  } catch (error) {
    console.warn('Auto voice capture failed.', error)
    return false
  } finally {
    voiceCameraReadyPromise = undefined
  }
}

function withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error('timeout')), timeoutMs)
    promise.then(
      (value) => {
        window.clearTimeout(timer)
        resolve(value)
      },
      (error) => {
        window.clearTimeout(timer)
        reject(error)
      },
    )
  })
}

async function routeTextQuestionFromUserAction(transcript: string): Promise<void> {
  const input = document.querySelector<HTMLTextAreaElement>('#text-question-input')
  if (input) input.value = ''
  await handleTranscript(transcript, { source: 'manual' })
}

function bindCriticalVisionEngineButton(): void {
  const button = document.querySelector<HTMLButtonElement>('#vision-engine-button')
  if (!button || button.dataset.bound === 'true') return
  button.dataset.bound = 'true'
  button.addEventListener('click', () => {
    button.textContent = '正在启动视觉引擎...'
    void unlockAudioPlayback()
    selectG2Bookmark('vision')
    setVisionImageInfo('已收到启动指令，正在请求手机相机权限。')
    setVoiceStatus('正在启动天禄视觉引擎。')
    renderBookmarkChrome()
    void startVisionEngineFromPhoneButton().finally(() => {
      const engine = getVisionEngineState()
      button.textContent = engine.status === 'ready' ? '天禄视觉引擎已启动' : '启动天禄视觉引擎'
      button.disabled = engine.status === 'ready'
      renderR1CameraDebug()
    })
  })
}

function bindGlobalButtonFeedback(): void {
  if (document.body.dataset.feedbackBound === 'true') return
  document.body.dataset.feedbackBound = 'true'

  document.addEventListener(
    'pointerdown',
    (event) => {
      const control = getFeedbackControl(event.target)
      if (!control) return
      pulseControl(control)
      vibrateBriefly()
    },
    { capture: true },
  )

  document.addEventListener(
    'click',
    (event) => {
      const control = getFeedbackControl(event.target)
      if (!control) return
      setInteractionFeedback(`${getControlFeedbackLabel(control)} 已触发`)
    },
    { capture: true },
  )
}

function getFeedbackButton(target: EventTarget | null): HTMLButtonElement | null {
  if (!(target instanceof Element)) return null
  const button = target.closest('button')
  if (!(button instanceof HTMLButtonElement)) return null
  if (button.disabled) return null
  return button
}

function getFeedbackControl(target: EventTarget | null): HTMLElement | null {
  if (!(target instanceof Element)) return null
  const button = getFeedbackButton(target)
  if (button) return button
  const label = target.closest<HTMLElement>('#direct-camera-label, #album-camera-label')
  return label ?? null
}

function pulseButton(button: HTMLButtonElement): void {
  pulseControl(button)
}

function pulseControl(control: HTMLElement): void {
  control.classList.remove('button-feedback')
  void control.offsetWidth
  control.classList.add('button-feedback')
  window.setTimeout(() => control.classList.remove('button-feedback'), 420)
}

function vibrateBriefly(): void {
  try {
    navigator.vibrate?.(12)
  } catch {}
}

function getButtonFeedbackLabel(button: HTMLButtonElement): string {
  return getControlFeedbackLabel(button)
}

function getControlFeedbackLabel(control: HTMLElement): string {
  if (control.id === 'direct-camera-label') return '直接拍照/选择照片'
  if (control.id === 'album-camera-label') return '相册选图'
  if (!(control instanceof HTMLButtonElement)) return control.textContent?.replace(/\s+/g, ' ').trim() || control.id || '入口'
  if (control.id === 'connection-scan-button') return '一键扫描'
  if (control.id === 'connection-repair-button') return '一键修复'
  if (control.id === 'vision-engine-button') return '连续视觉流'
  return control.textContent?.replace(/\s+/g, ' ').trim() || control.id || '按钮'
}

function setInteractionFeedback(text: string): void {
  const statusTitle = document.querySelector('#status-title')
  if (statusTitle) statusTitle.textContent = text
  const toast = ensureInteractionToast()
  toast.textContent = text
  toast.classList.remove('show')
  void toast.offsetWidth
  toast.classList.add('show')
  window.setTimeout(() => toast.classList.remove('show'), 1300)
}

function ensureInteractionToast(): HTMLElement {
  const existing = document.querySelector<HTMLElement>('#interaction-feedback')
  if (existing) return existing
  const toast = document.createElement('div')
  toast.id = 'interaction-feedback'
  toast.setAttribute('role', 'status')
  document.body.appendChild(toast)
  return toast
}

main().catch((error) => {
  console.error(error)
})

async function speakIfEnabled(text: string, force = false): Promise<void> {
  lastSpeakText = text
  renderReplaySpeechButton()
  const normalizedText = text.trim()
  const now = Date.now()
  if (!force && normalizedText && normalizedText === lastSpokenText && now - lastSpokenAt < 3500) {
    setVoiceStatus('同一句回答已朗读，已跳过重复播报。')
    return
  }
  if (!force && !getAppConfig().autoSpeak) {
    setVoiceStatus('已生成回答，自动朗读已关闭。可点“重播朗读”。')
    return
  }

  try {
    stopAutoVoiceDetection()
    stopSpeechPlayback()
    lastSpokenText = normalizedText
    lastSpokenAt = now
    setVoiceStatus('正在请求 MiniMax 语音并朗读...')
    const tts = await requestTts(text)
    const played = await speakResponse(tts, text)
    lastTtsOk = played.ok
    lastTtsMethod = played.ok ? (played.method as 'minimax-tts' | 'browser-fallback') : null
    lastTtsError = played.ok ? null : (played.error ?? 'unknown')
    updateTtsStatusDisplay()
    if (played.ok) {
      setVoiceStatus(played.method === 'minimax-tts' ? 'MiniMax 语音朗读中。' : 'MiniMax 音频被系统拦截，已尝试系统朗读。')
      return
    }

    setVoiceStatus(`朗读被系统拦截：${played.error ?? 'unknown'}。请点”重播朗读”。`)
  } catch (error) {
    console.warn('TTS failed; using browser fallback.', error)
    const fallback = speakWithBrowser(text)
    lastTtsOk = fallback.ok
    lastTtsMethod = fallback.ok ? 'browser-fallback' : null
    lastTtsError = fallback.ok ? null : String(error instanceof Error ? error.message : error)
    updateTtsStatusDisplay()
    setVoiceStatus(
      fallback.ok
        ? 'MiniMax TTS 请求失败，已尝试系统朗读。'
        : `朗读失败：${error instanceof Error ? error.message : String(error)}。请点”重播朗读”。`,
    )
  }
}

async function playAudioUrl(audioUrl: string): Promise<void> {
  const audio = new Audio(audioUrl)
  await audio.play()
}

function updateTtsStatusDisplay(): void {
  const el = document.querySelector('#tts-status-debug')
  if (!el) return
  const config = getAppConfig()
  const source = lastTtsMethod === 'minimax-tts' ? 'MiniMax TTS 音频'
    : lastTtsMethod === 'browser-fallback' ? '系统朗读 fallback'
    : '—'
  const status = lastTtsOk === true ? '成功' : lastTtsOk === false ? '失败' : '—'
  el.textContent = `当前 voiceId：${config.ttsVoiceId}\n当前朗读来源：${source}\n最近朗读状态：${status}\n最近错误：${lastTtsError ?? '—'}`
}

async function testCurrentTts(): Promise<void> {
  const config = getAppConfig()
  setConfigStatus(`正在用 voiceId=${config.ttsVoiceId} 试听...`)
  updateTtsStatusDisplay()
  try {
    const tts = await requestTts('你好，我是天禄，很高兴为你服务。')
    const played = await speakResponse(tts, '你好，我是天禄，很高兴为你服务。')
    lastTtsOk = played.ok
    lastTtsMethod = played.ok ? (played.method as 'minimax-tts' | 'browser-fallback') : null
    lastTtsError = played.ok ? null : (played.error ?? 'unknown')
    updateTtsStatusDisplay()
    setConfigStatus(
      played.method === 'minimax-tts'
        ? `试听成功：MiniMax TTS 音频，voiceId=${config.ttsVoiceId}`
        : `试听结果：${played.method === 'browser-fallback' ? '已退回系统朗读' : '朗读失败'}，voiceId=${config.ttsVoiceId}`,
    )
  } catch (err) {
    lastTtsOk = false
    lastTtsMethod = null
    lastTtsError = String(err instanceof Error ? err.message : err)
    updateTtsStatusDisplay()
    setConfigStatus(`试听失败：${lastTtsError}，voiceId=${config.ttsVoiceId}`)
  }
}

function bindConfigPanel(): void {
  renderConfigPanel()

  document.querySelector<HTMLButtonElement>('#save-config-button')?.addEventListener('click', () => {
    const apiBase = document.querySelector<HTMLInputElement>('#config-api-base')?.value
    const ttsVoiceId = document.querySelector<HTMLInputElement>('#config-tts-voice')?.value
    const g2RecordMs = Number(document.querySelector<HTMLInputElement>('#config-record-ms')?.value)
    const autoSpeak = Boolean(document.querySelector<HTMLInputElement>('#config-auto-speak')?.checked)
    const autoListenOnStart = Boolean(document.querySelector<HTMLInputElement>('#config-auto-listen')?.checked)
    const enableLocationContext = Boolean(document.querySelector<HTMLInputElement>('#config-location-context')?.checked)
    const config = saveAppConfig({ apiBase, ttsVoiceId, g2RecordMs, autoSpeak, autoListenOnStart, enableLocationContext })
    renderConfigPanel(config)
    setConfigStatus('已保存，本机立即生效')
    if (config.autoListenOnStart) void startAutoVoiceDetection()
    else stopAutoVoiceDetection()
  })

  document.querySelector<HTMLButtonElement>('#reset-config-button')?.addEventListener('click', () => {
    const config = resetAppConfig()
    renderConfigPanel(config)
    setConfigStatus('已恢复默认配置')
  })
  document.querySelector<HTMLButtonElement>('#connection-scan-button')?.addEventListener('click', () => {
    void runConnectionDiagnostics(false)
  })
  document.querySelector<HTMLButtonElement>('#connection-repair-button')?.addEventListener('click', () => {
    void runConnectionDiagnostics(true)
  })
  document.querySelector<HTMLButtonElement>('#permission-check-button')?.addEventListener('click', () => {
    void runPermissionSelfCheck(false)
  })
  document.querySelector<HTMLButtonElement>('#permission-request-button')?.addEventListener('click', () => {
    void runPermissionSelfCheck(true)
  })
  document.querySelector<HTMLButtonElement>('#location-check-button')?.addEventListener('click', () => {
    void runLocationDiagnostics(false)
  })
  document.querySelector<HTMLButtonElement>('#location-request-button')?.addEventListener('click', () => {
    void runLocationDiagnostics(true)
  })
  document.querySelector<HTMLButtonElement>('#refresh-battery-button')?.addEventListener('click', async () => {
    const bridge = getBridge()
    if (bridge) {
      try {
        const device = await bridge.getDeviceInfo()
        if (device) {
          updateDeviceBatteryFromInfo(device)
          updateBatteryDebugPanel(getBatteryCache())
          setConfigStatus('电量已刷新')
        }
      } catch {
        setConfigStatus('电量刷新失败，请检查连接')
      }
    } else {
      setConfigStatus('G2 未连接，无法刷新电量')
    }
  })
  document.querySelector<HTMLButtonElement>('#test-tts-button')?.addEventListener('click', () => {
    void testCurrentTts()
  })
  updateTtsStatusDisplay()
}

function renderConfigPanel(config = getAppConfig()): void {
  const apiBase = document.querySelector<HTMLInputElement>('#config-api-base')
  const ttsVoice = document.querySelector<HTMLInputElement>('#config-tts-voice')
  const recordMs = document.querySelector<HTMLInputElement>('#config-record-ms')
  const autoSpeak = document.querySelector<HTMLInputElement>('#config-auto-speak')
  const autoListen = document.querySelector<HTMLInputElement>('#config-auto-listen')
  const locationContext = document.querySelector<HTMLInputElement>('#config-location-context')

  if (apiBase) apiBase.value = config.apiBase
  if (ttsVoice) ttsVoice.value = config.ttsVoiceId
  if (recordMs) recordMs.value = String(config.g2RecordMs)
  if (autoSpeak) autoSpeak.checked = config.autoSpeak
  if (autoListen) autoListen.checked = config.autoListenOnStart
  if (locationContext) locationContext.checked = config.enableLocationContext
  updateTtsStatusDisplay()
  updateLocationStatusDisplay()
}

function setConfigStatus(text: string): void {
  const el = document.querySelector('#config-status')
  if (el) el.textContent = text
}

async function updateLocationStatusDisplay(): Promise<void> {
  const el = document.querySelector('#location-status-debug')
  if (!el) return
  const config = getAppConfig()
  const permission = await getLocationPermissionState()
  el.textContent = [
    `定位开关：${config.enableLocationContext ? '开启' : '关闭'}`,
    `WebView API：${navigator.geolocation ? 'navigator.geolocation 可用' : '不可用'}`,
    `权限：${permission}`,
    '粗略地址：点击“检测定位”获取',
    '精度：—',
  ].join('\n')
}

async function runLocationDiagnostics(forceRequest: boolean): Promise<void> {
  const el = document.querySelector('#location-status-debug')
  const config = getAppConfig()
  const bridge = getBridge()
  const renderer = createGlassRenderer(bridge)

  if (!config.enableLocationContext) {
    const text = '定位开关：关闭\n处理：请先勾选“视觉识别和呼叫天禄加入实时定位”并保存。'
    if (el) el.textContent = text
    setConfigStatus('定位未开启')
    addHistory({
      kind: 'settings',
      title: '定位诊断',
      answer: '定位开关关闭',
      detail: text,
      summary: '定位未开启',
    })
    renderHistory()
    return
  }

  if (forceRequest) clearLocationCache()
  const startedAt = performance.now()
  const pending = [
    '定位：检测中',
    `WebView API：${navigator.geolocation ? 'navigator.geolocation 可用' : '不可用'}`,
    '正在请求手机系统定位权限，失败不会阻塞视觉/语音。',
  ].join('\n')
  if (el) el.textContent = pending
  setConfigStatus(forceRequest ? '正在请求实时定位...' : '正在检测定位能力...')
  await renderer.show('diagnostics', {
    diagnostics: {
      g2: bridge ? '已连接' : '未连接',
      r1: runtimeCapabilities.canUseR1 ? '可用' : '待检测',
      cam: '不检测',
      mic: '不检测',
      asr: '不检测',
      claw: '不检测',
      bot: '定位中',
    },
  })

  const location = await getLocationContext(true, { forceRefresh: forceRequest, resolveAddress: true })
  const elapsedMs = Math.round(performance.now() - startedAt)
  const display = `${formatLocationForDisplay(location)}\n耗时：${elapsedMs} ms\n用途：视觉识别与呼叫天禄，交易状态不使用定位。`
  if (el) el.textContent = display
  setConfigStatus(location.status === 'ready' ? '定位可用，已写入上下文' : '定位不可用，已显示失败原因')
  addHistory({
    kind: 'settings',
    title: '定位诊断',
    answer: location.status === 'ready' ? '定位可用' : '定位不可用',
    detail: display,
    summary: location.address || location.message || location.status,
  })
  renderHistory()
}

async function runPermissionSelfCheck(requestAccess: boolean): Promise<void> {
  const lines: string[] = []
  const bridge = getBridge()
  const renderer = createGlassRenderer(bridge)
  const statusEl = document.querySelector('#permission-status')

  const write = (text: string): void => {
    if (statusEl) statusEl.textContent = text
    setConfigStatus(requestAccess ? '正在请求设备权限...' : '正在检测设备权限...')
  }

  write('检测中...')
  runtimeCapabilities = detectRuntimeCapabilities(Boolean(bridge))
  lines.push(`运行环境：${runtimeCapabilities.label}`)
  lines.push(`相机策略：${runtimeCapabilities.cameraStrategy}`)
  lines.push(`麦克风策略：${runtimeCapabilities.micStrategy}`)
  lines.push(`安全上下文：${window.isSecureContext ? 'OK' : 'NO'}`)
  lines.push(`mediaDevices：${typeof navigator.mediaDevices?.getUserMedia === 'function' ? 'OK' : 'NO'}`)
  lines.push(`G2 Bridge：${bridge ? 'OK' : '未连接'}`)

  if (requestAccess) {
    if (isVisionEngineReady()) {
      const state = getVisionEngineState()
      lines.push(`相机：OK ${state.videoWidth}x${state.videoHeight}`)
    } else if (runtimeCapabilities.hasBridge) {
      lines.push('相机：SKIP Even 插件容器不能由诊断按钮代替真实拍照动作。请用“直接拍照/选择照片”。')
    } else {
      try {
        const state = await startVisionEngineFromPhoneGesture()
        lines.push(`相机：OK ${state.videoWidth}x${state.videoHeight}`)
      } catch (error) {
        const reason = classifyCameraError(error)
        lines.push(`相机：FAIL ${reason.long}`)
      }
    }

    if (runtimeCapabilities.hasBridge) {
      lines.push('手机/耳机麦克风：SKIP 插件内优先使用 G2 麦克风；手机/耳机麦克风只在手机网页真实点击时兜底。')
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
        for (const track of stream.getTracks()) track.stop()
        lines.push('手机/耳机麦克风：OK')
      } catch (error) {
        const reason = classifyMicError(error)
        lines.push(`手机/耳机麦克风：FAIL ${reason.long}`)
      }
    }

    if (bridge) {
      try {
        await bridge.audioControl(true)
        await bridge.audioControl(false)
        lines.push('G2 麦克风开关：OK')
      } catch (error) {
        lines.push(`G2 麦克风开关：FAIL ${formatShortError(error)}`)
      }
    }
  } else {
    const engine = getVisionEngineState()
    lines.push(`视觉引擎：${engine.status}${engine.videoWidth ? ` ${engine.videoWidth}x${engine.videoHeight}` : ''}`)
    lines.push(runtimeCapabilities.hasBridge ? '权限：Even 插件内不强行请求手机相机/麦克风' : '相机/麦克风：点“一键请求权限”检测')
  }

  const result = lines.join('\n')
  if (statusEl) statusEl.textContent = result
  setConfigStatus(requestAccess ? '权限请求完成，请查看自检结果' : '权限自检完成')
  setVoiceStatus(result)
  renderR1CameraDebug()
  await renderer.show('diagnostics', {
    diagnostics: {
      g2: runtimeCapabilities.hasBridge ? '已连接' : runtimeCapabilities.label,
      r1: runtimeCapabilities.canUseR1 ? (lastR1InputSummary === 'none' ? '待输入' : '已响应') : '不可用',
      cam: isVisionEngineReady() ? '已就绪' : getVisionEngineStatusText(),
      mic: result.includes('麦克风：OK') || result.includes('麦克风开关：OK') ? '检查通过' : '待检测',
      asr: '未配置',
      claw: '待检测',
      bot: '只读待检',
    },
  })
}

async function runConnectionDiagnostics(repair: boolean): Promise<void> {
  const bridge = getBridge()
  runtimeCapabilities = detectRuntimeCapabilities(Boolean(bridge))
  const renderer = createGlassRenderer(bridge)
  const statusEl = document.querySelector('#permission-status')
  const apiBase = getAppConfig().apiBase.replace(/\/+$/, '')
  const lines: string[] = []
  const diagnostics = {
    g2: runtimeCapabilities.hasBridge ? '已连接' : runtimeCapabilities.label,
    r1: runtimeCapabilities.canUseR1 ? (lastR1InputSummary === 'none' ? '待输入' : '已响应') : '不可用',
    cam: isVisionEngineReady() ? '已就绪' : getVisionEngineStatusText(),
    mic: '待检测',
    asr: '检测中',
    claw: '检测中',
    bot: '检测中',
  }

  const write = async (text: string): Promise<void> => {
    if (statusEl) statusEl.textContent = text
    setConfigStatus(repair ? '正在一键修复连接...' : '正在一键扫描连接...')
    await renderer.show('diagnostics', { diagnostics })
  }

  await write('正在扫描...')
  lines.push(`运行环境：${runtimeCapabilities.label}`)
  lines.push(`相机策略：${runtimeCapabilities.cameraStrategy}`)
  lines.push(`麦克风策略：${runtimeCapabilities.micStrategy}`)
  lines.push(`后端：${await checkHttpEndpoint(`${apiBase}/health`)}`)

  if (repair) {
    if (isVisionEngineReady()) {
      const state = getVisionEngineState()
      diagnostics.cam = `已就绪 ${state.videoWidth}x${state.videoHeight}`
      lines.push(`相机：OK ${state.videoWidth}x${state.videoHeight}`)
    } else if (runtimeCapabilities.hasBridge) {
      diagnostics.cam = '需手机点击'
      lines.push('相机：SKIP 诊断不再启动相机；视觉识别直接映射“拍照/选择照片”。')
    } else {
      try {
        const state = await startVisionEngineFromPhoneGesture()
        diagnostics.cam = `已就绪 ${state.videoWidth}x${state.videoHeight}`
        lines.push(`相机：OK ${state.videoWidth}x${state.videoHeight}`)
      } catch (error) {
        const reason = classifyCameraError(error)
        diagnostics.cam = `失败:${reason.short}`
        lines.push(`相机：FAIL ${reason.long}`)
      }
    }

    if (runtimeCapabilities.hasBridge) {
      diagnostics.mic = 'G2优先'
      lines.push('手机/耳机麦克风：SKIP Even 插件内不主动请求，避免容器权限误报；需要时由手机网页真实点击兜底。')
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
        for (const track of stream.getTracks()) track.stop()
        diagnostics.mic = '手机可用'
        lines.push('手机/耳机麦克风：OK')
      } catch (error) {
        const reason = classifyMicError(error)
        diagnostics.mic = `失败:${reason.short}`
        lines.push(`手机/耳机麦克风：FAIL ${reason.long}`)
      }
    }

    if (bridge) {
      try {
        await bridge.audioControl(true)
        await bridge.audioControl(false)
        diagnostics.mic = diagnostics.mic === '手机可用' ? 'G2/手机可用' : 'G2 可开'
        lines.push('G2 麦克风开关：OK')
      } catch (error) {
        lines.push(`G2 麦克风开关：FAIL ${formatShortError(error)}`)
      }
    }
  } else {
    lines.push(`视觉引擎：${getVisionEngineStatusText()}`)
    diagnostics.mic = bridge ? 'G2 待探测' : '未连接'
  }

  try {
    const asr = (await getAsrStatus()) as unknown as Record<string, unknown>
    const available = Boolean(asr.available)
    diagnostics.asr = available ? '已连接' : String(asr.reason ?? asr.provider ?? '未配置').slice(0, 12)
    lines.push(`ASR：${available ? 'OK' : diagnostics.asr}`)
  } catch (error) {
    diagnostics.asr = '检测失败'
    lines.push(`ASR：FAIL ${formatShortError(error)}`)
  }

  try {
    const claw = (await getOpenClawStatus()) as unknown as Record<string, unknown>
    const ok = Boolean(claw.ok ?? claw.available ?? claw.connected ?? claw.enabled)
    diagnostics.claw = ok ? '在线' : String(claw.status ?? claw.reason ?? '不可用').slice(0, 10)
    lines.push(`OpenClaw：${ok ? 'OK' : diagnostics.claw}`)
  } catch (error) {
    diagnostics.claw = '检测失败'
    lines.push(`OpenClaw：FAIL ${formatShortError(error)}`)
  }

  try {
    const trading = await getTradingOverview()
    diagnostics.bot = trading.mode === 'live-readonly' ? '实时只读' : '记忆只读'
    lines.push(`交易：OK ${diagnostics.bot}`)
  } catch (error) {
    diagnostics.bot = '检测失败'
    lines.push(`交易：FAIL ${formatShortError(error)}`)
  }

  const result = lines.join('\n')
  if (statusEl) statusEl.textContent = result
  setConfigStatus(repair ? '一键修复完成，请查看结果' : '一键扫描完成')
  setVoiceStatus(result)
  renderR1CameraDebug()
  await renderer.show('diagnostics', { diagnostics })
}

async function handleDiagnosticsR1Intent(intent: 'click' | 'double_click' | 'next' | 'previous'): Promise<void> {
  if (intent === 'click' || intent === 'next' || intent === 'double_click') {
    activeGlassPage = 'home'
    await renderG2Bookmark()
    return
  }
  if (intent === 'previous') {
    await runConnectionDiagnostics(true)
    return
  }
}

async function checkHttpEndpoint(url: string): Promise<string> {
  try {
    const startedAt = performance.now()
    const response = await fetch(url, { method: 'GET' })
    const elapsed = Math.round(performance.now() - startedAt)
    return response.ok ? `OK ${elapsed}ms` : `FAIL ${response.status}`
  } catch (error) {
    return `FAIL ${formatShortError(error)}`
  }
}

function getVisionEngineStatusText(): string {
  const state = getVisionEngineState()
  if (state.status === 'ready') return state.videoWidth ? `已就绪 ${state.videoWidth}x${state.videoHeight}` : '已就绪'
  if (state.status === 'idle') return '未启动'
  if (state.status === 'starting') return '启动中'
  if (state.status === 'stream_lost') return '视频丢失'
  if (state.status === 'failed') return state.error ? `失败:${classifyCameraError(state.error).short}` : '启动失败'
  return state.status
}

function detectRuntimeCapabilities(hasBridge: boolean): RuntimeCapabilities {
  const ua = navigator.userAgent || ''
  const isMobile = /iPhone|iPad|Android|Mobile/i.test(ua)
  const looksLikeEven = /Even|EvenApp|EvenHub|G2|Glasses/i.test(ua) || Boolean((window as unknown as Record<string, unknown>).EvenHub)
  const mode: RuntimeMode = hasBridge
    ? 'even-bridge'
    : looksLikeEven
      ? 'even-webview'
      : isMobile
        ? 'browser-mobile'
        : 'browser-desktop'

  if (mode === 'even-bridge') {
    return {
      mode,
      label: 'Even 插件模式',
      hasBridge: true,
      canUseR1: true,
      canUseG2Mic: true,
      canRequestPhoneCamera: true,
      canRequestPhoneMic: true,
      cameraStrategy: '手机点击启动视觉流，R1截帧',
      micStrategy: 'G2麦克风优先，手机/耳机兜底',
    }
  }

  if (mode === 'even-webview') {
    return {
      mode,
      label: 'Even WebView模式',
      hasBridge: false,
      canUseR1: false,
      canUseG2Mic: false,
      canRequestPhoneCamera: true,
      canRequestPhoneMic: true,
      cameraStrategy: '手机点击启动视觉流',
      micStrategy: '手机/耳机麦克风兜底',
    }
  }

  if (mode === 'browser-mobile') {
    return {
      mode,
      label: '手机网页预览',
      hasBridge: false,
      canUseR1: false,
      canUseG2Mic: false,
      canRequestPhoneCamera: true,
      canRequestPhoneMic: true,
      cameraStrategy: '网页按钮拍照/选图',
      micStrategy: '手机浏览器麦克风',
    }
  }

  return {
    mode,
    label: '桌面网页预览',
    hasBridge: false,
    canUseR1: false,
    canUseG2Mic: false,
    canRequestPhoneCamera: typeof navigator.mediaDevices?.getUserMedia === 'function',
    canRequestPhoneMic: typeof navigator.mediaDevices?.getUserMedia === 'function',
    cameraStrategy: '桌面摄像头/选图测试',
    micStrategy: '桌面麦克风测试',
  }
}

function classifyCameraError(error: unknown): { short: string; long: string } {
  const message = error instanceof Error ? `${error.name}: ${error.message}` : String(error)
  if (/user agent|platform in the current context|user activation|gesture|WKWebView|WebView|getUserMedia|secure context|安全上下文/i.test(message)) {
    return { short: '容器限制', long: `当前容器限制相机启动。请使用“直接拍照/选择照片”。${message}`.slice(0, 180) }
  }
  if (/NotAllowedError|Permission|denied|拒绝|权限/i.test(message)) {
    return { short: '权限拒绝', long: `权限拒绝。请在 iOS 设置和 Even App 内允许相机。${message}`.slice(0, 180) }
  }
  if (/NotFoundError|not found|找不到|No camera/i.test(message)) {
    return { short: '无相机', long: `未找到可用摄像头。${message}`.slice(0, 180) }
  }
  if (/NotReadableError|busy|占用|in use/i.test(message)) {
    return { short: '被占用', long: `摄像头可能被其它 App 占用。${message}`.slice(0, 180) }
  }
  if (/timeout|preview|视频流|尚未就绪/i.test(message)) {
    return { short: '流未就绪', long: `摄像头已请求但视频流没有就绪。${message}`.slice(0, 180) }
  }
  return { short: '未知原因', long: message.slice(0, 180) }
}

function classifyMicError(error: unknown): { short: string; long: string } {
  const message = error instanceof Error ? `${error.name}: ${error.message}` : String(error)
  if (/NotAllowedError|Permission|denied|拒绝|权限/i.test(message)) {
    return { short: '权限拒绝', long: `麦克风权限被拒绝。请在 iOS 设置和 Even App 内允许麦克风。${message}`.slice(0, 180) }
  }
  if (/NotFoundError|not found|No microphone|找不到/i.test(message)) {
    return { short: '无麦克风', long: `未找到可用手机/耳机麦克风。${message}`.slice(0, 180) }
  }
  if (/NotReadableError|busy|占用|in use/i.test(message)) {
    return { short: '被占用', long: `麦克风可能被其它 App 占用。${message}`.slice(0, 180) }
  }
  if (/secure context|安全上下文|getUserMedia|WebView|WKWebView/i.test(message)) {
    return { short: '容器限制', long: `当前容器限制麦克风启动。${message}`.slice(0, 180) }
  }
  return { short: '未知原因', long: message.slice(0, 180) }
}

function getIntentLabel(intent: 'click' | 'double_click' | 'next' | 'previous'): string {
  if (intent === 'click') return '单击确认'
  if (intent === 'double_click') return '双击'
  if (intent === 'next') return '下滑'
  return '上滑'
}

function formatShortError(error: unknown): string {
  if (!(error instanceof Error)) return String(error).slice(0, 80)
  return `${error.name}: ${error.message}`.slice(0, 100)
}

function bindKeyboardControlFallback(): void {
  window.addEventListener('keydown', (event) => {
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return
    if (event.key === 'ArrowDown' || event.key === 'ArrowRight') {
      event.preventDefault()
      moveControlFocus('next')
      void announceFocusedControl()
    }
    if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') {
      event.preventDefault()
      moveControlFocus('previous')
      void announceFocusedControl()
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      void executeFocusedControl()
    }
  })
}

function moveControlFocus(direction: 'next' | 'previous'): void {
  const controls = getSelectableControls()
  if (controls.length === 0) return
  const step = direction === 'next' ? 1 : -1
  selectedControlIndex = (selectedControlIndex + step + controls.length) % controls.length
  renderControlFocus()
}

function moveG2Bookmark(direction: 'next' | 'previous'): void {
  const step = direction === 'next' ? 1 : -1
  g2BookmarkIndex = (g2BookmarkIndex + step + g2Bookmarks.length) % g2Bookmarks.length
  focusControlById(getCurrentG2Bookmark().controlId)
}

function selectG2Bookmark(id: G2BookmarkId): void {
  // G2 书签只更新眼镜端 ring 导航状态，与手机网页状态完全分离
  const index = g2Bookmarks.findIndex((bookmark) => bookmark.id === id)
  if (index >= 0) g2BookmarkIndex = index
  focusControlById(getCurrentG2Bookmark().controlId)
}

function focusControlById(id: string): boolean {
  const controls = getSelectableControls()
  const index = controls.findIndex((control) => control.id === id)
  if (index < 0) return false
  selectedControlIndex = index
  renderControlFocus()
  return true
}

function renderControlFocus(): void {
  let controls = getSelectableControls()
  if (selectedControlIndex >= controls.length) selectedControlIndex = Math.max(0, controls.length - 1)
  syncBookmarkFromSelectedControl(controls[selectedControlIndex]?.id)
  controls = getSelectableControls()
  if (selectedControlIndex >= controls.length) selectedControlIndex = Math.max(0, controls.length - 1)

  for (const button of document.querySelectorAll<HTMLButtonElement>('button')) {
    button.classList.remove('r1-focused')
    button.removeAttribute('aria-current')
  }

  const selected = controls[selectedControlIndex]
  renderBookmarkChrome()
  if (!selected) return
  selected.button.classList.add('r1-focused')
  selected.button.setAttribute('aria-current', 'true')
  selected.button.scrollIntoView({ block: 'nearest', behavior: 'smooth' })

  // R1 滑动时同步手机网页书签状态，避免点击执行时对应面板被隐藏
  if (activeGlassPage === 'home') {
    const controlToBookmark: Record<string, PhoneBookmarkId> = {
      'capture-button': 'vision',
      'voice-button': 'voice',
      'trading-button': 'trading',
      'settings-button': 'openclaw',
    }
    const bookmarkId = controlToBookmark[selected.id]
    if (bookmarkId) setPhoneActiveBookmark(bookmarkId)
  }
}

function syncBookmarkFromSelectedControl(id: string | undefined): void {
  if (!id) return
  const bookmark = g2Bookmarks.find((item) => item.controlId === id)
  if (bookmark) {
    g2BookmarkIndex = g2Bookmarks.findIndex((item) => item.id === bookmark.id)
  }
}

function renderBookmarkChrome(): void {
  // 只更新 G2 连接状态 footer，不再管理手机网页书签状态
  updateWebConnectionFooter()
}

function updateWebConnectionFooter(): void {
  const footer = document.querySelector('#web-hud-footer')
  if (!footer) return
  const caps = runtimeCapabilities
  footer.textContent = caps.hasBridge
    ? `● ${caps.label} · R1 输入待测 · OpenClaw 在线`
    : `● ${caps.label} · R1/G2 输入不可用 · ${caps.cameraStrategy}`
}

function getBookmarkCardDescription(id: PhoneBookmarkId): string {
  if (id === 'vision') {
    if (lastVisionSummary) return `最近识别：${lastVisionSummary.slice(0, 56)}`
    return '拍照识别画面，结果显示到眼镜并朗读。'
  }

  if (id === 'voice') {
    const voice = document.querySelector('#voice-status')?.textContent?.trim()
    return voice ? voice.slice(0, 64) : '呼叫天禄进行语音问答，不可用时可用文字输入。'
  }

  if (id === 'openclaw') {
    return '连接诊断、权限自检、配置保存'
  }

  if (id === 'history') {
    return '查看视觉、语音、交易、OpenCLAW 和全部历史记录。'
  }

  const tradingMode = document.querySelector('#trading-mode')?.textContent?.trim()
  const trading = document.querySelector('#trading-summary')?.textContent?.trim()
  if (trading && trading !== '点击”交易状态”查看白名单价格、机器人、持仓和风险的只读入口。') {
    return `${tradingMode || '交易只读'}：${trading.split('\n')[0]?.slice(0, 52) || '已刷新'}`
  }
  return '查看白名单价格、机器人、持仓和风险，只读不交易。'
}

// 手机网页和 G2 眼镜端状态已分离，phoneActiveBookmark 由 phoneUiState.ts 单独管理
// 此函数仅供 G2 ring 导航使用（更新 g2BookmarkIndex），不再触碰手机状态
function updateActiveBookmarkLayout(): void {
  // G2 ring 导航不覆盖手机书签状态
}

async function announceFocusedControl(): Promise<void> {
  renderControlFocus()
  const bridge = getBridge()
  const selected = getSelectableControls()[selectedControlIndex]
  if (!selected) return
  setVoiceStatus(`R1 已选择：${selected.label}。单击执行，上下滑动切换。`)
  activeGlassPage = 'home'
  await showGlassHome(bridge)
}

async function renderG2Bookmark(): Promise<void> {
  const bookmark = getCurrentG2Bookmark()
  focusControlById(bookmark.controlId)
  const bridge = getBridge()
  setVoiceStatus(`R1 书签：${bookmark.title}。${bookmark.action}，上下滑动切换。`)
  activeGlassPage = 'home'
  await showGlassHome(bridge)
}

async function showGlassHome(bridge = getBridge()): Promise<void> {
  await createGlassRenderer(bridge).show('home', getGlassHomeState())
}

function getGlassHomeState(): {
  selectedIndex: number
  tabs: Array<{ title: string; subtitle?: string }>
  actions: Array<{ label: string; disabled?: boolean }>
} {
  return {
    selectedIndex: g2BookmarkIndex,
    tabs: getG2TabItems(),
    actions: getG2ActionItems(),
  }
}

function getG2TabItems(): Array<{ title: string; subtitle: string }> {
  return g2Bookmarks.map((bookmark) => {
    if (bookmark.id === 'vision') return { title: bookmark.title, subtitle: '拍照' }
    if (bookmark.id === 'voice') return { title: bookmark.title, subtitle: '语音' }
    if (bookmark.id === 'trading') return { title: bookmark.title, subtitle: '只读' }
    return { title: bookmark.title, subtitle: '设置' }
  })
}

function getG2ActionItems(): Array<{ label: string; disabled?: boolean }> {
  const bookmark = getCurrentG2Bookmark().id
  if (bookmark === 'vision') {
    return [
      { label: '直接拍照' },
      { label: '相册选图' },
    ]
  }
  if (bookmark === 'voice') return [{ label: '按住语音对话' }]
  if (bookmark === 'trading') {
    return [
      { label: '刷新状态' },
      { label: '白名单价格' },
      { label: '持仓评测' },
      { label: 'L5资金流' },
    ]
  }
  return [{ label: '连接诊断' }]
}

async function executeCurrentG2Bookmark(): Promise<void> {
  await unlockAudioPlayback()
  const bookmark = getCurrentG2Bookmark()
  focusControlById(bookmark.controlId)
  if (bookmark.id === 'vision') {
    await runDirectVisionCaptureFromR1('camera')
    return
  }
  if (bookmark.id === 'voice') {
    await enterVoicePage({ autoStart: true })
    return
  }
  if (bookmark.id === 'trading') {
    await runTradingOverview()
  }
}

async function enterSettingsPage(): Promise<void> {
  // 更新手机网页 UI - 使用单一真相源
  setPhoneActiveBookmark('openclaw')
  activeGlassPage = 'settings'
  await createGlassRenderer(getBridge()).show('settings', {
    settings: {
      microphone: 'G2/手机',
      camera: '手机后置',
      openclaw: '已连接',
      trading: '只读',
    },
  })
  setConfigStatus('设置诊断已打开：网页可点一键扫描/修复，R1 单击扫描、上滑修复、下滑返回。')
}

async function runR1CaptureFlow(): Promise<void> {
  await handleVisionR1Intent('click')
}

async function runDirectVisionCaptureFromR1(source: 'camera' | 'album' = 'camera'): Promise<void> {
  const bridge = getBridge()
  const renderer = createGlassRenderer(bridge)
  const sourceLabel = source === 'album' ? '相册选图' : '直接拍照'
  activeGlassPage = 'vision'
  visionState = 'preparing'
  pendingCapturedImage = undefined
  uploadInFlight = false
  lastVisionError = ''
  setInteractionFeedback(`R1 已触发${sourceLabel}`)
  setVisionResultPanel('等待拍照', `R1 已触发网页“${sourceLabel}”。请在手机弹窗里完成操作。`, '完成拍照或选图返回后，会自动上传给 AI 识别。')
  setVoiceStatus(`R1 已映射到网页${sourceLabel}。完成后自动上传识别。`)
  await safeGlassShow(renderer, 'vision_preparing')
  renderR1CameraDebug()

  try {
    const image = source === 'album' ? await selectPhotoFromAlbum() : await capturePhoto()
    const imageBytes = estimateBase64Bytes(image.imageBase64)
    if (!image.imageBase64 || imageBytes <= 0) throw new Error('没有获取到图片，请重新拍照。')
    lastCaptureAt = new Date().toLocaleTimeString('zh-CN')
    lastCapturedAt = Date.now()
    visionState = 'uploading'
    lastUploadSource = source === 'album' ? 'r1-album-auto-upload' : 'r1-camera-auto-upload'
    setInteractionFeedback(`${source === 'album' ? '已选图' : '已拍照'}，自动上传识别`)
    setVisionResultPanel(
      `${source === 'album' ? '已选图' : '已拍照'} · 正在识别`,
      [`图片大小：约 ${formatBytes(imageBytes)}`, `capture：${lastCaptureAt}`, `source：${lastUploadSource}`].join('\n'),
      '正在自动发送给天禄视觉识别...',
    )
    await safeGlassShow(renderer, 'vision_uploading')
    await runCaptureFlow(undefined, image, { source: lastUploadSource })
  } catch (error) {
    visionState = 'error'
    const message = formatVisionError(error)
    lastVisionError = message
    setVisionResultPanel('拍照失败', '未获取到图片', message)
    setVoiceStatus(message)
    await safeGlassShow(renderer, 'error', { body: message })
  } finally {
    renderR1CameraDebug()
  }
}

async function enterVisionPage(): Promise<void> {
  await runDirectVisionCaptureFromR1()
}

async function startVisionEngineFromPhoneButton(): Promise<void> {
  const renderer = createGlassRenderer(getBridge())
  try {
    visionState = 'preparing'
    activeGlassPage = 'vision'
    lastVisionError = ''
    setVisionImageInfo('正在打开手机直接拍照 / 选择照片。')
    setVoiceStatus('正在打开手机直接拍照 / 选择照片。')
    await renderer.show('vision_preparing')
    const state = await startVisionEngineFromPhoneGesture()
    visionState = 'camera_ready'
    setVisionImageInfo(`连续视觉流已就绪：${state.videoWidth}x${state.videoHeight}。`)
    setVoiceStatus('连续视觉流已就绪。')
    await renderer.show('vision_ready')
  } catch (error) {
    visionState = 'error'
    const message = error instanceof Error ? error.message : String(error)
    lastVisionError = message
    setVisionImageInfo(`直接拍照/连续流启动失败：${message}`)
    setVoiceStatus(`直接拍照/连续流启动失败：${message}`)
    await renderer.show('error', { body: `直接拍照失败\n${message}` })
  } finally {
    renderR1CameraDebug()
  }
}

async function enterVoicePage(options: { autoStart?: boolean } = {}): Promise<void> {
  const bridge = getBridge()
  if (activeG2PcmVoiceSession || phoneHoldRecorder) {
    activeGlassPage = 'voice'
    setVoiceStatus(bridge ? 'G2 正在录音。R1 单击结束并识别。' : '正在录音。松开后结束并识别。')
    return
  }

  await stopActiveGlassMicProbe?.()
  stopActiveGlassMicProbe = undefined
  activeG2PcmVoiceSession = undefined
  voicePageState = 'idle'
  activeGlassPage = 'voice'
  setVoiceStatus(
    options.autoStart && bridge
      ? '呼叫天禄已打开，正在启动 G2 录音。R1 单击结束并识别。'
      : '呼叫天禄已打开。请按住圆形按钮说话，松开后识别。',
  )
  updateVoiceDebug({
    voicePageState: 'idle',
    micSource: bridge ? 'g2' : 'none',
    wsStatus: 'idle',
    audioControlCalled: false,
    audioControlError: '',
    totalBytes: 0,
    chunks: 0,
    lastChunkBytes: 0,
    lastChunkAt: '--',
    noPcmTimeout: false,
    lastServerAudioDebug: '',
    lastVoiceError: '',
  })
  if (options.autoStart && bridge) {
    await startHoldToTalkSession({ strategy: 'g2-pcm', mode: 'asr' })
    return
  }

  await createGlassRenderer(bridge).show('voice_menu')
}

async function handleVoiceR1Intent(intent: 'click' | 'double_click' | 'next' | 'previous'): Promise<void> {
  if (intent === 'double_click' || intent === 'next') {
    await stopHoldToTalkSession('cancelled')
    await stopGlassMicProbeAndReturnHome()
    return
  }

  if (intent === 'previous') {
    await startVoiceDiagnosticProbe()
    return
  }

  if (voicePageState === 'recording' || voicePageState === 'listening') {
    await stopHoldToTalkSession('clicked_stop')
    return
  }

  if (voicePageState === 'finalizing' || voicePageState === 'transcribing') {
    setVoiceStatus('语音正在识别处理中，请稍候。')
    return
  }

  await startHoldToTalkSession({ mode: 'asr' })
}

async function stopGlassMicProbeAndReturnHome(): Promise<void> {
  await stopActiveGlassMicProbe?.()
  stopActiveGlassMicProbe = undefined
  await activeG2PcmVoiceSession?.stop('cancelled')
  activeG2PcmVoiceSession = undefined
  voicePageState = 'idle'
  activeGlassPage = 'home'
  stopAutoVoiceDetection()
  updateVoiceDebug({
    voicePageState: 'idle',
    wsStatus: 'closed',
  })
  await renderG2Bookmark()
}

async function returnFromVisionToHome(): Promise<void> {
  pendingCapturedImage = undefined
  uploadInFlight = false
  visionState = 'idle'
  activeGlassPage = 'home'
  lastCapturedAt = 0
  setVoiceStatus('已退出视觉识别，R1 可继续选择书签。')
  renderR1CameraDebug()
  await renderG2Bookmark()
}

async function handleVisionR1Intent(intent: 'click' | 'double_click' | 'next' | 'previous'): Promise<void> {
  const bridge = getBridge()
  const renderer = createGlassRenderer(bridge)

  // preparing/uploading 状态下：R1 next/double_click/click 均可取消并返回
  if (visionState === 'preparing' || visionState === 'uploading') {
    if (intent === 'next' || intent === 'double_click' || intent === 'click') {
      await cancelCurrentGlassOperation(visionState === 'preparing' ? '相机准备中取消' : '上传中取消')
      return
    }
    // R1 previous 在 preparing/uploading 时也取消
    if (intent === 'previous') {
      await cancelCurrentGlassOperation('R1 上滑取消')
      return
    }
    return
  }

  console.info('[R1 vision intent]', {
    intent,
    visionState,
    pendingCapturedImage: Boolean(pendingCapturedImage),
    msSinceLastCaptured: lastCapturedAt ? Date.now() - lastCapturedAt : null,
    uploadInFlight,
  })

  if (intent === 'previous') {
    if (visionState === 'captured') {
      await captureVisionFrame(renderer, 'R1 上滑已重新拍照。再次单触上传，下滑取消。')
    } else if (visionState === 'camera_ready') {
      setVoiceStatus('R1 单击拍照，下滑返回。')
      await renderer.show('vision_ready')
    } else if (visionState === 'result' || visionState === 'error') {
      setVoiceStatus(visionState === 'result' ? '识别已完成。单击重播，双击返回主菜单。' : '视觉错误。单击重试，下滑返回。')
    } else {
      setVoiceStatus('视觉识别页内上滑暂不切换菜单。')
    }
    return
  }

  if (intent === 'next') {
    if (visionState === 'captured') {
      pendingCapturedImage = undefined
      uploadInFlight = false
      lastCapturedAt = 0
      visionState = 'camera_ready'
      await renderer.show('vision_ready')
      setVoiceStatus('已取消当前照片，摄像头保持待命。')
      renderR1CameraDebug()
    } else if (visionState === 'camera_ready' || visionState === 'result' || visionState === 'error') {
      await returnFromVisionToHome()
    } else {
      setVoiceStatus('视觉识别页内下滑返回首页。')
      await returnFromVisionToHome()
    }
    return
  }

  if (intent === 'double_click' || intent === 'click') {
    if (visionState === 'captured' && pendingCapturedImage && intent === 'double_click') {
      await uploadPendingVisionImage(renderer, 'R1 双击确认，正在发送图片给天禄...', 'r1-double-confirm')
      return
    }

    await returnFromVisionToHome()
    return
  }

  if (visionState === 'result') {
    if (lastSpeakText) {
      setVoiceStatus('正在重播识别结果。双击可返回主菜单。')
      await speakIfEnabled(lastSpeakText, true)
    } else {
      setVoiceStatus('暂无可重播内容。双击返回主菜单。')
    }
    return
  }

  if (visionState === 'idle' || visionState === 'error') {
    await enterVisionPage()
    return
  }

  if (visionState === 'camera_ready' || visionState === 'captured') {
    await returnFromVisionToHome()
    return
  }

  if (visionState === 'captured' && pendingCapturedImage) {
    await uploadPendingVisionImage(renderer, 'R1 单触确认，正在发送图片给天禄...', 'r1-single-confirm')
    return
  }

  if (visionState === 'camera_ready') {
    await captureVisionFrame(renderer, 'R1 已截帧。再次单触上传；上滑重拍，下滑取消。')
    return
  }
}

async function uploadPendingVisionImage(renderer: GlassRenderer, statusText: string, source = 'r1-single-confirm'): Promise<void> {
  if (!pendingCapturedImage) {
    setVoiceStatus('当前没有可上传的照片，请先拍照或选择照片。')
    await renderer.show('vision_ready')
    return
  }
  if (uploadInFlight) {
    setVoiceStatus('图片正在发送中，请稍候。')
    return
  }

  uploadInFlight = true
  visionState = 'uploading'
  await renderer.show('vision_uploading')
  setVoiceStatus(statusText)
  lastUploadAt = new Date().toLocaleTimeString('zh-CN')
  lastUploadSource = source
  renderR1CameraDebug()
  try {
    await runCaptureFlow(undefined, pendingCapturedImage, { source })
    const finishedState = String(visionState)
    if (finishedState !== 'error') {
      pendingCapturedImage = undefined
      visionState = 'result'
      lastCapturedAt = 0
    }
  } finally {
    uploadInFlight = false
    renderR1CameraDebug()
  }
}

async function captureVisionFrame(renderer: GlassRenderer, statusText: string): Promise<boolean> {
  try {
    if (!isVisionEngineReady()) {
      throw new Error('相机未就绪，请先进入视觉识别打开手机拍照。')
    }
    const image = await captureFrameFromVisionEngine()
    pendingCapturedImage = {
      imageBase64: image.imageBase64,
      mimeType: image.mimeType,
    }
    lastCaptureAt = new Date().toLocaleTimeString('zh-CN')
    lastCapturedAt = Date.now()
    visionState = 'captured'
    await renderer.show('vision_captured')
    setVoiceStatus(statusText)
    setVisionImageInfo([
      `R1 截帧：${image.width}x${image.height}`,
      `data length：${image.dataUrl.length}`,
      `capture：${lastCaptureAt}`,
    ].join('\n'))
    renderR1CameraDebug()
    return true
  } catch (error) {
    visionState = 'error'
    const message = error instanceof Error ? error.message : String(error)
    lastVisionError = message
    await renderer.show('error', { body: message })
    setVoiceStatus(message)
    renderR1CameraDebug()
    return false
  }
}

async function executeG2PrimaryAction(): Promise<void> {
  const selected = getSelectableControls()[selectedControlIndex]
  if (selected && !g2Bookmarks.some((bookmark) => bookmark.controlId === selected.id)) {
    await executeFocusedControl()
    return
  }

  await executeCurrentG2Bookmark()
}

function getCurrentG2Bookmark(): (typeof g2Bookmarks)[number] {
  return g2Bookmarks[g2BookmarkIndex] ?? g2Bookmarks[0]
}

function formatG2Bookmark(bookmark: (typeof g2Bookmarks)[number]): string {
  const page = `${g2BookmarkIndex + 1}/${g2Bookmarks.length}`
  const body = getG2BookmarkBody(bookmark.id)
  return formatForG2(`${bookmark.title}  ${page}`, `${body}\n\n${bookmark.action}\n上下滑动切换书签`)
}

function getG2BookmarkBody(id: G2BookmarkId): string {
  if (id === 'vision') {
    if (lastVisionSummary) return `最近识别：${lastVisionSummary.slice(0, 120)}`
    const engine = getVisionEngineState()
    if (engine.status === 'ready') return '连续视觉流就绪\nR1可截帧拍照'
    return 'R1单击映射网页\n直接拍照/选图'
  }

  if (id === 'voice') {
    const voice = document.querySelector('#voice-status')?.textContent?.trim()
    return voice || '子菜单：G2 语音测试 / 问刚才画面 / 问今日收益'
  }

  if (id === 'settings') {
    return '设备电量 / 连接诊断\n权限状态 / 语音配置'
  }

	const trading = document.querySelector('#trading-summary')?.textContent?.trim()
	return trading || '子菜单：刷新状态 / 白名单价格 / 持仓评测 / L5资金流'
}

function getSelectableControls(): Array<{ id: string; label: string; button: HTMLButtonElement }> {
  // 眼镜首页 ring 导航：只限于 4 个主书签，禁止跳到手机端辅助按钮
  const mainBookmarkIds = ['capture-button', 'voice-button', 'trading-button', 'settings-button']
  const isOnHome = activeGlassPage === 'home'
  const ids = isOnHome
    ? mainBookmarkIds
    : [
        'capture-button',
        'voice-button',
        'trading-button',
        'openclaw-button',
        'history-button',
        'trading-refresh-action',
        'trading-preset-prices',
        'trading-preset-risk',
        'connection-scan-shortcut',
        'permission-check-shortcut',
        tradingPanelActive ? 'refresh-trading-button' : '',
        lastSpeakText ? 'replay-speech-button' : '',
        pendingVisionPrompt ? 'confirm-camera-button' : '',
      ].filter(Boolean)

  return ids
    .map((id) => {
      const button = document.querySelector<HTMLButtonElement>(`#${id}`)
      if (!button || button.hidden || button.disabled || !isVisibleControl(button)) return undefined
      return {
        id,
        label: getControlLabel(id, button),
        button,
      }
    })
    .filter((item): item is { id: string; label: string; button: HTMLButtonElement } => Boolean(item))
}

function isVisibleControl(button: HTMLButtonElement): boolean {
  return button.getClientRects().length > 0 && window.getComputedStyle(button).visibility !== 'hidden'
}

function getControlLabel(id: string, button: HTMLButtonElement): string {
  if (id === 'capture-button') return '拍照识别'
  if (id === 'voice-button') return '呼叫天禄'
  if (id === 'trading-button') return '交易状态'
  if (id === 'settings-button') return '系统设置'
  if (id === 'openclaw-button') return 'OpenCLAW 对话'
  if (id === 'history-button') return '历史记录'
  if (id === 'vision-capture-action') return '拍照识别'
  if (id === 'vision-replay-action') return '重播识别结果'
  if (id === 'voice-orb-action') return '按住说话'
  if (id === 'voice-manual-action') return '手动发送'
  if (id === 'voice-diagnostic-action') return '语音诊断'
  if (id === 'voice-preset-vision') return '问刚才画面'
  if (id === 'voice-preset-trading') return '问今日收益'
  if (id === 'trading-refresh-action') return '刷新交易只读'
  if (id === 'trading-preset-prices') return '查看白名单价格'
  if (id === 'trading-preset-risk') return '查看风险摘要'
  if (id === 'openclaw-record-action') return '语音问 OpenCLAW'
  if (id === 'openclaw-preset-trading') return 'OpenCLAW 交易状态'
  if (id === 'openclaw-preset-memory') return 'OpenCLAW 读取记忆'
  if (id === 'refresh-trading-button') return '刷新交易状态'
  if (id === 'connection-scan-shortcut') return '连接扫描'
  if (id === 'permission-check-shortcut') return '权限自检'
  if (id === 'replay-speech-button') return '重播朗读'
  if (id === 'confirm-camera-button') return '确认打开摄像头'
  return button.textContent?.trim() || id
}

function startFlow(): void {
  flowStartedAt = performance.now()
  window.clearInterval(timerId)
  timerId = window.setInterval(updateElapsed, 100)
  setProgress(0)
  for (const step of document.querySelectorAll('#steps li')) {
    step.className = ''
  }
  updateElapsed()
}

function setStage(step: StepId, title: string, progress: number): void {
  document.querySelector('#status-title')!.textContent = title
  setProgress(progress)

  const currentIndex = stepOrder.indexOf(step)
  for (const item of document.querySelectorAll<HTMLLIElement>('#steps li')) {
    const itemStep = item.dataset.step as StepId
    const itemIndex = stepOrder.indexOf(itemStep)
    item.className = itemIndex < currentIndex ? 'done' : itemIndex === currentIndex ? 'active' : ''
  }
}

function finishFlow(title: string, progress: number): void {
  document.querySelector('#status-title')!.textContent = title
  setProgress(progress)
  for (const item of document.querySelectorAll<HTMLLIElement>('#steps li')) {
    item.className = 'done'
  }
  window.clearInterval(timerId)
  updateElapsed()
}

function failFlow(message: string): void {
  document.querySelector('#status-title')!.textContent = '识别失败'
  const log = document.querySelector<HTMLPreElement>('#debug-log')
  if (log) log.textContent = formatForG2('识别失败', message)
  for (const item of document.querySelectorAll<HTMLLIElement>('#steps li.active')) {
    item.className = 'failed'
  }
  window.clearInterval(timerId)
  updateElapsed()
}

function setProgress(value: number): void {
  const bar = document.querySelector<HTMLDivElement>('#progress-bar')
  if (bar) bar.style.width = `${Math.max(0, Math.min(100, value))}%`
}

function updateElapsed(): void {
  const el = document.querySelector('#status-time')
  if (!el || !flowStartedAt) return
  el.textContent = `${((performance.now() - flowStartedAt) / 1000).toFixed(1)}s`
}

function extractTianluQuestion(transcript: string): string {
  const normalized = transcript.replace(/[，。！？,.!?]/g, ' ').replace(/\s+/g, ' ').trim()
  const wakePattern = /(你好)?\s*(天禄|天路|添禄|天鹿|天录)\s*/
  const match = normalized.match(wakePattern)
  if (!match || match.index === undefined) return ''

  return normalized.slice(match.index + match[0].length).trim() || '请根据当前画面和上下文，给我一个简短帮助。'
}

function isVisionIntent(question: string): boolean {
  return /看一下|看一看|看看|瞅一瞅|瞅一下|瞅瞅|瞧一瞧|瞧一下|看到|看见|识别|拍照|画面|前面|这里|这个|这是什么|读一下|帮我看|帮我瞅|帮我瞧|帮我识别|帮我读/.test(question)
}

function formatTradingOverviewSummary(overview: Awaited<ReturnType<typeof getTradingOverview>>): string {
  const mode = overview.mode === 'live-readonly' ? '实时只读' : '记忆只读'
  const live = overview.live
  if (live && !live.error) {
    const topPair = live.pairConcentration?.[0]
    const prices = live.whitelistPrices?.map((item) => `${item.symbol} ${formatTradingPrice(item.price)}`).join(' / ')
    const openPairs = live.openPositionPairs?.map((item) => formatOpenPairForSpeech(item)).join('；')
    const assessment = buildPositionAssessment(overview)
    const dataSources = live.dataSources?.length
      ? `数据源：${live.dataSources.map((source) => `${source.baseUrl}${source.ok ? ` 持仓${source.openPositions ?? '-'} / 对${source.pairCount ?? '-'}` : ` 失败 ${source.error ?? ''}`}`).join('；')}。`
      : ''
    const botSummary = live.botSummary
      ? `机器人：${live.botSummary.online ?? live.portsOnline ?? '-'} / ${live.botSummary.total ?? live.portsTotal ?? '-'} 在线；MacA ${live.botSummary.macA ?? '-'}，MacB ${live.botSummary.macB ?? '-'}；自动驾驶${live.autopilotEnabled ? '开启' : '关闭'}。`
      : `机器人：${live.portsOnline ?? '-'} / ${live.portsTotal ?? '-'} 在线；自动驾驶${live.autopilotEnabled ? '开启' : '关闭'}。`
    const flow = live.marketFlow?.summary ? `L5资金流：${live.marketFlow.summary}。` : ''
    const attribution = live.attribution
      ? `归因：样本${live.attribution.sampleCount ?? '-'}，胜率${formatPercent(live.attribution.winRatePct)}，已实现${formatSignedPercent(live.attribution.avgRealizedPnlPct)}。`
      : ''
    const aiAssessment = live.aiAssessment?.summary
      ? `${live.aiAssessment.provider || 'AI'}评测：${live.aiAssessment.summary}。`
      : ''
    const sixPoints = live.aiAssessment?.summaryPoints?.length
      ? `六项摘要：${live.aiAssessment.summaryPoints.slice(0, 6).join(' ')}`
      : ''
    return [
      `${mode}，禁止交易执行。`,
      dataSources,
      prices ? `白名单价格：${prices}` : '',
      botSummary,
      openPairs ? `持仓交易对：${openPairs}。` : '',
      `持仓：${live.openPositions ?? '-'} 个；名义 ${formatMoney(live.totalNotional)}；浮盈亏 ${formatMoney(live.totalUnrealizedPnl)}。`,
      `风险：${live.riskLevel ?? '-'} ${live.riskScore ?? '-'} 分。`,
      `浮盈亏：${formatMoney(live.totalUnrealizedPnl)}，名义仓位 ${formatMoney(live.totalNotional)}。`,
      topPair ? `最高集中：${topPair.pair} ${(topPair.share * 100).toFixed(1)}%。` : '',
      flow,
      attribution,
      sixPoints,
      aiAssessment,
      live.alarms?.[0]?.message ? `警报：${live.alarms[0].message}` : '',
      assessment ? `评测：${assessment}` : '',
    ]
      .filter(Boolean)
      .join('\n')
  }

  if (live?.error) {
    return [`${mode}，实时接口暂不可用。`, live.error, '未使用备份历史报告。请检查公网控制台实时接口。'].join('\n')
  }

  return [`${mode}模式，禁止下单/平仓。`, `可查价格、机器人、持仓、盈亏。`, '数据只取公网实时控制台，不读取备份报告。'].join('\n')
}

function buildPositionAssessment(overview: Awaited<ReturnType<typeof getTradingOverview>>): string {
  const live = overview.live
  if (!live || live.error) return '实时数据不足，暂按记忆只读口径观察。'
  const riskScore = Number(live.riskScore ?? 0)
  const topShare = Number(live.pairConcentration?.[0]?.share ?? 0)
  const alarms = live.alarms?.filter((alarm) => alarm.message).map((alarm) => alarm.message).slice(0, 2) ?? []
  const pnl = Number(live.totalUnrealizedPnl ?? 0)
  const parts: string[] = []

  if (riskScore >= 80 || /danger|high|危险/i.test(String(live.riskLevel ?? ''))) {
    parts.push('风险偏高，只读建议减小新增风险暴露，先处理警报。')
  } else if (riskScore >= 55 || /warning|warn|警/i.test(String(live.riskLevel ?? ''))) {
    parts.push('风险中等，建议观察集中度和止损有效性。')
  } else {
    parts.push('整体风险正常，可继续观察。')
  }

  if (topShare >= 0.45 && live.pairConcentration?.[0]) {
    parts.push(`${live.pairConcentration[0].pair} 集中度偏高。`)
  }
  if (pnl < 0) parts.push('当前浮亏，优先复核亏损仓位。')
  if (alarms.length > 0) parts.push(`警报：${alarms.join('；')}`)

  return parts.join(' ')
}

function formatOpenPairForSpeech(pair: NonNullable<NonNullable<Awaited<ReturnType<typeof getTradingOverview>>['live']>['openPositionPairs']>[number]): string {
  const side = [
    typeof pair.long === 'number' ? `多${pair.long}` : '',
    typeof pair.short === 'number' ? `空${pair.short}` : '',
  ]
    .filter(Boolean)
    .join('/')
  const pnl = typeof pair.pnl === 'number' ? `盈亏${formatMoney(pair.pnl)}` : ''
  const price = typeof pair.currentPrice === 'number' ? `现价${formatTradingPrice(pair.currentPrice)}` : ''
  return [pair.pair, side, price, pnl].filter(Boolean).join(' ')
}

function formatMoney(value: number | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '-'
  return value.toFixed(2)
}

function formatTradingPrice(value: number): string {
  if (!Number.isFinite(value)) return '-'
  if (value >= 1000) return value.toFixed(1)
  if (value >= 10) return value.toFixed(2)
  return value.toFixed(5)
}

function formatPercent(value: number | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '-'
  return `${value.toFixed(1)}%`
}

function formatSignedPercent(value: number | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '-'
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
}

function formatPriceSource(item: NonNullable<NonNullable<Awaited<ReturnType<typeof getTradingOverview>>['live']>['whitelistPrices']>[number]): string {
  const status = item.freshness === 'stale' ? '旧' : item.freshness === 'fallback' ? '兜底' : '实时'
  const time = item.updatedAt ? new Date(item.updatedAt).toLocaleTimeString('zh-CN', { hour12: false }) : ''
  return [item.sourceLayer ?? item.source, status, time].filter(Boolean).join(' · ')
}

function renderTradingOverview(overview: Awaited<ReturnType<typeof getTradingOverview>>, summary: string): void {
  setTradingMode(overview.mode === 'live-readonly' ? '实时只读已开启' : '记忆只读模式')
  setTradingSummary(summary)

  const hits = document.querySelector('#trading-hits')
  if (!hits) return
  const live = overview.live
  const sections: HTMLElement[] = []
  if (live && !live.error) {
    if (live.dataSources?.length) {
      const sourceCard = document.createElement('div')
      sourceCard.className = 'trading-hit trading-live-card'
      sourceCard.textContent = [
        '交易数据源',
        ...live.dataSources.map((source) =>
          source.ok
            ? `${source.baseUrl} · OK · 持仓${source.openPositions ?? '-'} · 交易对${source.pairCount ?? '-'}`
            : `${source.baseUrl} · FAIL · ${source.error ?? '未知错误'}`,
        ),
      ].join('\n')
      sections.push(sourceCard)
    }

	    const prices = document.createElement('div')
	    prices.className = 'trading-hit trading-live-card'
	    const priceLines = live.whitelistPrices?.length
	      ? live.whitelistPrices.map((item) => `${item.symbol} ${formatTradingPrice(item.price)} · ${formatPriceSource(item)}`).join('\n')
	      : '暂无白名单实时价格，请检查公网 9099 的 /api/prices/realtime。'
	    prices.textContent = `白名单实时价格\n${priceLines}`
	    sections.push(prices)

	    const bots = document.createElement('div')
	    bots.className = 'trading-hit trading-live-card'
	    bots.textContent = [
	      '机器人在线',
	      live.botSummary
	        ? `总计 ${live.botSummary.online ?? live.portsOnline ?? '-'} / ${live.botSummary.total ?? live.portsTotal ?? '-'} 在线`
	        : `总计 ${live.portsOnline ?? '-'} / ${live.portsTotal ?? '-'} 在线`,
	      live.botSummary ? `MacA ${live.botSummary.macA ?? '-'} · MacB ${live.botSummary.macB ?? '-'}` : '',
	      `自动驾驶：${live.autopilotEnabled ? '开启' : '关闭'}`,
	    ]
	      .filter(Boolean)
	      .join('\n')
	    sections.push(bots)

    const assessment = document.createElement('div')
    assessment.className = 'trading-hit trading-live-card'
    assessment.textContent = [
      '整体持仓评测',
      buildPositionAssessment(overview),
      `持仓 ${live.openPositions ?? '-'} · 名义 ${formatMoney(live.totalNotional)} · 浮盈亏 ${formatMoney(live.totalUnrealizedPnl)}`,
      live.pairConcentration?.length
        ? `集中度 ${live.pairConcentration.map((item) => `${item.pair} ${(item.share * 100).toFixed(1)}%`).join(' / ')}`
        : '暂无集中度数据',
    ].join('\n')
    sections.push(assessment)

	    if (live.openPositionPairs?.length) {
      const positionPairs = document.createElement('div')
      positionPairs.className = 'trading-hit trading-live-card'
      positionPairs.textContent = [
        '真实持仓交易对',
        ...live.openPositionPairs.map((item) =>
          [
            `${item.pair}`,
            `数量${item.count ?? '-'}`,
            typeof item.long === 'number' || typeof item.short === 'number' ? `多${item.long ?? 0}/空${item.short ?? 0}` : '',
            typeof item.currentPrice === 'number' ? `现价${formatTradingPrice(item.currentPrice)}` : '',
            typeof item.pnl === 'number' ? `PnL ${formatMoney(item.pnl)}` : '',
            typeof item.share === 'number' ? `占比${(item.share * 100).toFixed(1)}%` : '',
            item.source ? `源${item.source.replace(/^https?:\/\//, '')}` : '',
          ]
            .filter(Boolean)
            .join(' · '),
        ),
      ].join('\n')
	      sections.push(positionPairs)
	    }

	    if (live.marketFlow) {
	      const flow = document.createElement('div')
	      flow.className = 'trading-hit trading-live-card'
	      flow.textContent = [
	        'M1-M5 / L5 资金流',
	        live.marketFlow.summary || '暂无资金流摘要',
	        `交易对：${live.marketFlow.pairCount ?? '-'} · 来源：${live.marketFlow.source ?? '/api/l5/fund_flow_v2'}`,
	      ].join('\n')
	      sections.push(flow)
	    }

	    if (live.attribution) {
	      const attribution = document.createElement('div')
	      attribution.className = 'trading-hit trading-live-card'
	      attribution.textContent = [
	        '真实订单归因',
	        `样本：${live.attribution.sampleCount ?? '-'}`,
	        `胜率：${formatPercent(live.attribution.winRatePct)} · 已实现：${formatSignedPercent(live.attribution.avgRealizedPnlPct)} · 未实现：${formatSignedPercent(live.attribution.avgUnrealizedPnlPct)}`,
	        `来源：${live.attribution.source ?? '/api/l5/daily_attribution?hours=24'}`,
	      ].join('\n')
	      sections.push(attribution)
	    }

	    if (live.aiAssessment) {
	      const ai = document.createElement('div')
	      ai.className = 'trading-hit trading-live-card'
	      ai.textContent = [
	        `${live.aiAssessment.provider || 'AI'} 持仓评测`,
	        ...(live.aiAssessment.summaryPoints?.length ? [`六项摘要\n${live.aiAssessment.summaryPoints.slice(0, 7).join('\n')}`] : []),
	        live.aiAssessment.summary,
	        ...(live.aiAssessment.suggestions?.length ? [`建议：${live.aiAssessment.suggestions.slice(0, 4).join('；')}`] : []),
	        `来源：${live.aiAssessment.source ?? 'realtime-assessment'}`,
	      ].join('\n')
	      sections.push(ai)
	    }
	  } else if (live?.error) {
    const error = document.createElement('div')
    error.className = 'trading-hit trading-live-card'
    error.textContent = `实时数据同步失败\n${live.error}`
    sections.push(error)
  }

  hits.replaceChildren(...sections)
}

function setTradingMode(text: string): void {
  const el = document.querySelector('#trading-mode')
  if (el) el.textContent = text
  renderBookmarkChrome()
}

function setTradingSummary(text: string): void {
  const el = document.querySelector('#trading-summary')
  if (el) el.textContent = text
  renderBookmarkChrome()
}

function getAsrPendingMessage(provider: string): string {
  if (provider.includes('minimax-asr-not-configured')) {
    return 'G2 麦克风已收到声音，但当前语音转文字服务还没接通。正在切换到手机语音或文字输入。'
  }

  if (provider.includes('minimax-asr-missing-key')) {
    return '语音转文字服务暂不可用。请先使用手机语音或文字输入。'
  }

  if (provider.includes('minimax-asr-empty-audio')) {
    return 'G2 麦克风没有收到有效音频，请靠近眼镜麦克风再试一次。'
  }

  return '暂时没有识别出文字，请再点“呼叫天禄”重试，或使用文字输入。'
}

function getPhoneAsrPendingMessage(provider: string, sizeBytes: number, durationMs = 0): string {
  const sizeKb = Math.max(1, Math.round(sizeBytes / 1024))
  const seconds = Math.max(0.1, durationMs / 1000).toFixed(1)
  if (provider.includes('unsupported-format')) {
    return `已采集手机/耳机麦克风音频 ${sizeKb} KB、${seconds} 秒，但当前 ASR 不支持该录音格式。`
  }

  if (provider.includes('not-configured') || provider === 'not-configured') {
    return `已采集手机/耳机麦克风音频 ${sizeKb} KB、${seconds} 秒，但后端 ASR 未配置，暂时不能转文字。`
  }

  if (provider.includes('missing-key')) {
    return `已采集手机/耳机麦克风音频 ${sizeKb} KB、${seconds} 秒，但 ASR 密钥缺失，暂时不能转文字。`
  }

  return `已采集手机/耳机麦克风音频 ${sizeKb} KB、${seconds} 秒，但 ASR 没有返回文字。请贴近麦克风说话，或延长按住时间后重试。`
}

function setVoiceStatus(text: string): void {
  const el = document.querySelector('#voice-status')
  if (el) el.textContent = text
  keepActiveVoicePanelIfNeeded()
  renderBookmarkChrome()
  keepActiveVoicePanelIfNeeded()
}

function updateVoiceDebug(next: Partial<typeof voiceProbeDebug>): void {
  voiceProbeDebug = { ...voiceProbeDebug, ...next }
  const el = document.querySelector('#voice-debug')
  if (!el) return
  el.textContent = [
    `voicePageState: ${voiceProbeDebug.voicePageState}`,
    `micSource: ${voiceProbeDebug.micSource}`,
    `wsStatus: ${voiceProbeDebug.wsStatus}`,
    `audioControlCalled: ${voiceProbeDebug.audioControlCalled ? 'true' : 'false'}`,
    `audioControlError: ${voiceProbeDebug.audioControlError || '--'}`,
    `totalBytes: ${voiceProbeDebug.totalBytes}`,
    `chunks: ${voiceProbeDebug.chunks}`,
    `lastChunkBytes: ${voiceProbeDebug.lastChunkBytes}`,
    `lastChunkAt: ${voiceProbeDebug.lastChunkAt}`,
    `noPcmTimeout: ${voiceProbeDebug.noPcmTimeout ? 'true' : 'false'}`,
    `lastServerAudioDebug: ${voiceProbeDebug.lastServerAudioDebug || '--'}`,
    `lastVoiceError: ${voiceProbeDebug.lastVoiceError || '--'}`,
    `holdStartedAt: ${voiceProbeDebug.holdStartedAt || '--'}`,
    `elapsedMs: ${voiceProbeDebug.elapsedMs ?? 0}`,
    `maxDurationMs: ${voiceProbeDebug.maxDurationMs ?? getAppConfig().g2RecordMs}`,
    `remainingMs: ${voiceProbeDebug.remainingMs ?? 0}`,
    `stopReason: ${voiceProbeDebug.stopReason || '--'}`,
    `lastTranscript: ${voiceProbeDebug.lastTranscript || '--'}`,
    `normalizedTranscript: ${voiceProbeDebug.normalizedTranscript || '--'}`,
    `lastIntent: ${voiceProbeDebug.lastIntent || '--'}`,
    `lastAnswer: ${voiceProbeDebug.lastAnswer || '--'}`,
    `fallbackUsed: ${voiceProbeDebug.fallbackUsed || '--'}`,
  ].join('\n')
}

function keepActiveVoicePanelIfNeeded(): void {
  if (activeGlassPage !== 'voice') return
  // 保持语音面板激活，使用单一真相源
  setPhoneActiveBookmark('voice')
  const voiceBookmarkIndex = g2Bookmarks.findIndex((bookmark) => bookmark.id === 'voice')
  if (voiceBookmarkIndex >= 0) g2BookmarkIndex = voiceBookmarkIndex
}

function setVoiceTranscript(text: string): void {
  const el = document.querySelector('#voice-transcript')
  if (el) el.textContent = text
}

function renderReplaySpeechButton(): void {
  const button = document.querySelector<HTMLButtonElement>('#replay-speech-button')
  if (!button) return
  button.hidden = !lastSpeakText
}

function showConfirmCameraButton(prompt: string): void {
  pendingVisionPrompt = prompt
  const button = document.querySelector<HTMLButtonElement>('#confirm-camera-button')
  if (!button) return
  button.hidden = false
  button.textContent = '确认打开摄像头'
  const controls = getSelectableControls()
  const confirmIndex = controls.findIndex((control) => control.id === 'confirm-camera-button')
  if (confirmIndex >= 0) selectedControlIndex = confirmIndex
  renderControlFocus()
}

function hideConfirmCameraButton(): void {
  const button = document.querySelector<HTMLButtonElement>('#confirm-camera-button')
  if (button) button.hidden = true
  renderControlFocus()
}
