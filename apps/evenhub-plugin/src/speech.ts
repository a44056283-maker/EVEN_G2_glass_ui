import type { TtsResponse } from '@g2vva/shared'

type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance

interface SpeechRecognitionResultItem {
  transcript: string
}

interface SpeechRecognitionResult {
  readonly length: number
  item(index: number): SpeechRecognitionResultItem
  [index: number]: SpeechRecognitionResultItem
}

interface SpeechRecognitionEvent extends Event {
  readonly results: {
    readonly length: number
    item(index: number): SpeechRecognitionResult
    [index: number]: SpeechRecognitionResult
  }
}

interface SpeechRecognitionErrorEvent extends Event {
  readonly error: string
}

interface SpeechRecognitionInstance extends EventTarget {
  lang: string
  continuous: boolean
  interimResults: boolean
  maxAlternatives: number
  start(): void
  stop(): void
  abort?(): void
  onresult: ((event: SpeechRecognitionEvent) => void) | null
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null
  onend: (() => void) | null
}

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor
    webkitSpeechRecognition?: SpeechRecognitionConstructor
    webkitAudioContext?: typeof AudioContext
  }
}

export interface SpeechPlaybackResult {
  ok: boolean
  method: 'minimax-tts' | 'browser-fallback' | 'none'
  error?: string
}

let audioUnlocked = false
let audioContext: AudioContext | undefined
let activeAudio: HTMLAudioElement | undefined

export async function unlockAudioPlayback(): Promise<boolean> {
  if (audioUnlocked) return true

  try {
    const AudioContextConstructor = window.AudioContext ?? window.webkitAudioContext
    if (AudioContextConstructor) {
      audioContext ??= new AudioContextConstructor()
      if (audioContext.state === 'suspended') await audioContext.resume()
    }

    if ('speechSynthesis' in window) window.speechSynthesis.resume()

    audioUnlocked = true
    return true
  } catch {
    return false
  }
}

export function stopSpeechPlayback(): void {
  if ('speechSynthesis' in window) window.speechSynthesis.cancel()
  if (activeAudio) {
    activeAudio.pause()
    activeAudio.currentTime = 0
    activeAudio = undefined
  }
}

export async function speakResponse(tts: TtsResponse, fallbackText: string): Promise<SpeechPlaybackResult> {
  const text = tts.fallbackText ?? fallbackText

  if (tts.audioBase64) {
    const played = await playAudioDataUrl(`data:${tts.mimeType ?? 'audio/mpeg'};base64,${tts.audioBase64}`)
    if (played.ok) return played

    const fallback = speakWithBrowser(text)
    if (fallback.ok) return fallback

    return {
      ok: false,
      method: 'none',
      error: played.error ?? fallback.error,
    }
  }

  return speakWithBrowser(text)
}

export function speakWithBrowser(text: string): SpeechPlaybackResult {
  if (!text.trim()) return { ok: false, method: 'none', error: 'empty-text' }
  if (!('speechSynthesis' in window)) return { ok: false, method: 'none', error: 'speechSynthesis-unavailable' }

  stopSpeechPlayback()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = navigator.language || 'zh-CN'
  utterance.rate = 1
  window.speechSynthesis.speak(utterance)
  return { ok: true, method: 'browser-fallback' }
}

async function playAudioDataUrl(dataUrl: string): Promise<SpeechPlaybackResult> {
  try {
    await unlockAudioPlayback()
    stopSpeechPlayback()
    const audio = new Audio(dataUrl)
    activeAudio = audio
    audio.preload = 'auto'
    audio.setAttribute('playsinline', 'true')
    await audio.play()
    return { ok: true, method: 'minimax-tts' }
  } catch (error) {
    return {
      ok: false,
      method: 'none',
      error: error instanceof Error ? error.message : String(error),
    }
  }
}

export interface ListenOnceOptions {
  maxMs?: number
  signal?: AbortSignal
  onInterim?: (text: string) => void
}

export function listenOnce(options: ListenOnceOptions = {}): Promise<string> {
  const SpeechRecognition = window.SpeechRecognition ?? window.webkitSpeechRecognition
  if (!SpeechRecognition) {
    return Promise.reject(new Error('当前浏览器不支持语音识别，请在 iPhone Safari 或 Even App WebView 中测试。'))
  }

  return new Promise((resolve, reject) => {
    const recognition = new SpeechRecognition()
    let settled = false
    let transcript = ''
    let timer: number | undefined

    recognition.lang = 'zh-CN'
    recognition.continuous = false
    recognition.interimResults = true
    recognition.maxAlternatives = 1

    const finish = (fn: () => void) => {
      if (settled) return
      settled = true
      if (timer) window.clearTimeout(timer)
      options.signal?.removeEventListener('abort', abort)
      fn()
    }

    const abort = () => {
      try {
        recognition.stop()
      } catch {}
    }

    recognition.onresult = (event) => {
      const pieces: string[] = []
      for (let index = 0; index < event.results.length; index += 1) {
        const result = event.results.item(index)
        const text = result.item(0).transcript.trim()
        if (text) pieces.push(text)
      }
      transcript = pieces.join(' ').trim()
      if (transcript) options.onInterim?.(transcript)
    }

    recognition.onerror = (event) => {
      finish(() => reject(new Error(`语音识别失败：${event.error}`)))
    }

    recognition.onend = () => {
      finish(() => {
        if (transcript) resolve(transcript)
        else reject(new Error('没有听清，请靠近手机麦克风再说一次。'))
      })
    }

    options.signal?.addEventListener('abort', abort)
    if (options.maxMs && options.maxMs > 0) {
      timer = window.setTimeout(() => {
        try {
          recognition.stop()
        } catch {}
      }, options.maxMs)
    }

    recognition.start()
  })
}

export async function canOpenMicrophone(): Promise<boolean> {
  if (typeof navigator.mediaDevices?.getUserMedia !== 'function') return false

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
    for (const track of stream.getTracks()) track.stop()
    return true
  } catch {
    return false
  }
}

export async function getBrowserMicrophoneLabel(): Promise<string> {
  if (typeof navigator.mediaDevices?.enumerateDevices !== 'function') return '手机/蓝牙耳机麦克风'

  try {
    const devices = await navigator.mediaDevices.enumerateDevices()
    const input = devices.find((device) => device.kind === 'audioinput' && device.label)
    if (!input?.label) return '手机/蓝牙耳机麦克风'
    if (/airpods|bluetooth|蓝牙|headset|耳机/i.test(input.label)) return `蓝牙耳机麦克风：${input.label}`
    return `手机麦克风：${input.label}`
  } catch {
    return '手机/蓝牙耳机麦克风'
  }
}
