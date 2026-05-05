import type {
  AskResponse,
  AsrStatusResponse,
  OpenClawStatusResponse,
  TradingReadonlyOverview,
  TranscribeResponse,
  TtsResponse,
  AskRequest,
  VisionRequest,
  VisionResponse,
} from '@g2vva/shared'
import type { CapturedImage } from './camera'
import { getAppConfig } from './config'
import type { G2MicRecording } from './g2-mic'
import { formatLocationForPrompt, getLocationContext } from './locationContext'
import type { PhoneMicRecording } from './voice/phoneMicRecorder'

const jsonHeaders = { 'Content-Type': 'text/plain;charset=UTF-8' }

export type RecognizeImageOptions = Pick<VisionRequest, 'capturedAt' | 'locationContext' | 'recentVisionContext'>
export type AskAssistantOptions = Pick<AskRequest, 'capturedAt' | 'locationContext'>

export async function recognizeImage(image: CapturedImage, prompt?: string, options: RecognizeImageOptions = {}): Promise<VisionResponse> {
  const config = getAppConfig()
  const locationContext = options.locationContext ?? await safeGetLocationContext(config.enableLocationContext)
  const payload: VisionRequest = {
    ...image,
    prompt,
    capturedAt: options.capturedAt ?? new Date().toISOString(),
    locationContext,
    recentVisionContext: options.recentVisionContext,
    locale: navigator.language || 'zh-CN',
  }

  const response = await fetch(`${getApiBase()}/vision`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const detail = await readError(response)
    throw new Error(`Vision API failed: ${response.status}${detail ? ` ${detail}` : ''}`)
  }
  return response.json()
}

export async function requestTts(text: string): Promise<TtsResponse> {
  const config = getAppConfig()
  const response = await fetch(`${getApiBase()}/tts`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({
      text,
      voiceId: config.ttsVoiceId,
      locale: navigator.language || 'zh-CN',
    }),
  })

  if (!response.ok) {
    const detail = await readError(response)
    throw new Error(`TTS API failed: ${response.status}${detail ? ` ${detail}` : ''}`)
  }
  return response.json()
}

export async function askAssistant(
  question: string,
  lastVisionSummary?: string,
  options: AskAssistantOptions = {},
): Promise<AskResponse> {
  const response = await fetch(`${getApiBase()}/ask`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({
      question,
      lastVisionSummary,
      capturedAt: options.capturedAt,
      locationContext: options.locationContext,
      locale: navigator.language || 'zh-CN',
    }),
  })

  if (!response.ok) {
    const detail = await readError(response)
    throw new Error(`Ask API failed: ${response.status}${detail ? ` ${detail}` : ''}`)
  }
  return response.json()
}

export async function askOpenClaw(question: string, lastVisionSummary?: string): Promise<AskResponse> {
  const response = await fetch(`${getApiBase()}/openclaw/ask`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({
      question,
      lastVisionSummary,
      locale: navigator.language || 'zh-CN',
    }),
  })

  if (!response.ok) {
    const detail = await readError(response)
    throw new Error(`OpenCLAW API failed: ${response.status}${detail ? ` ${detail}` : ''}`)
  }
  return response.json()
}

export async function getOpenClawStatus(): Promise<OpenClawStatusResponse> {
  const response = await fetch(`${getApiBase()}/openclaw/status`)

  if (!response.ok) {
    const detail = await readError(response)
    throw new Error(`OpenCLAW status API failed: ${response.status}${detail ? ` ${detail}` : ''}`)
  }
  return response.json()
}

export async function transcribeG2Audio(recording: G2MicRecording): Promise<TranscribeResponse> {
  const response = await fetch(`${getApiBase()}/transcribe`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({
      audioBase64: recording.audioBase64,
      sampleRate: recording.sampleRate,
      channels: recording.channels,
      format: recording.format,
      locale: navigator.language || 'zh-CN',
    }),
  })

  if (!response.ok) {
    const detail = await readError(response)
    throw new Error(`Transcribe API failed: ${response.status}${detail ? ` ${detail}` : ''}`)
  }
  return response.json()
}

export async function transcribePhoneAudio(recording: PhoneMicRecording): Promise<TranscribeResponse> {
  const response = await fetch(`${getApiBase()}/transcribe`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({
      audioBase64: recording.audioBase64,
      sampleRate: recording.sampleRate,
      channels: recording.channels,
      format: recording.format,
      mimeType: recording.mimeType,
      durationMs: recording.durationMs,
      source: 'phone',
      locale: navigator.language || 'zh-CN',
    }),
  })

  if (!response.ok) {
    const detail = await readError(response)
    throw new Error(`Transcribe API failed: ${response.status}${detail ? ` ${detail}` : ''}`)
  }
  return response.json()
}

export async function getAsrStatus(): Promise<AsrStatusResponse> {
  const response = await fetch(`${getApiBase()}/asr/status`)

  if (!response.ok) {
    const detail = await readError(response)
    throw new Error(`ASR status API failed: ${response.status}${detail ? ` ${detail}` : ''}`)
  }
  return response.json()
}

export async function getTradingOverview(): Promise<TradingReadonlyOverview> {
  const response = await fetch(`${getApiBase()}/trading/overview`)

  if (!response.ok) {
    const detail = await readError(response)
    throw new Error(`Trading API failed: ${response.status}${detail ? ` ${detail}` : ''}`)
  }
  return response.json()
}

async function readError(response: Response): Promise<string> {
  try {
    return await response.text()
  } catch {
    return ''
  }
}

function getApiBase(): string {
  return getAppConfig().apiBase
}

async function safeGetLocationContext(enabled: boolean): Promise<string | undefined> {
  if (!enabled) return undefined

  try {
    return formatLocationForPrompt(await getLocationContext(true))
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    console.warn('Location context unavailable; continuing vision request.', error)
    return `定位状态：${message || 'error'}。定位失败不影响识图。`
  }
}
