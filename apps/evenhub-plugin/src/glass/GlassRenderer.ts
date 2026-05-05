import {
  type CreateStartUpPageContainer,
  type EvenAppBridge,
  ImageContainerProperty,
  ImageRawDataUpdate,
  ImageRawDataUpdateResult,
  RebuildPageContainer,
  TextContainerProperty,
  TextContainerUpgrade,
} from '@evenrealities/even_hub_sdk'
import { renderGlassScreen, type GlassScreenId, type GlassScreenState } from './glassScreens'
import { sanitizeForG2Text } from './glassText'
import { GlassColor, GLASS_H, GLASS_MAIN_CONTAINER_ID, GLASS_MAIN_CONTAINER_NAME, GLASS_W } from './glassTheme'

type PreviewImagePayload = {
  label: string
  data: number[] | string
}

export class GlassRenderer {
  private currentContent = ''
  private imageQueue: Promise<void> = Promise.resolve()

  constructor(
    private readonly bridge: EvenAppBridge | undefined,
    private readonly getBatteryText: () => string,
    private readonly onDebug?: (content: string) => void,
  ) {}

  async init(screen: GlassScreenId = 'home', state: Omit<GlassScreenState, 'battery'> = {}): Promise<void> {
    if (!this.bridge) return
    await this.bridge.createStartUpPageContainer(this.buildStartup(screen, state))
  }

  buildStartup(screen: GlassScreenId, state: Omit<GlassScreenState, 'battery'> = {}): CreateStartUpPageContainer {
    return this.buildPage(screen, state) as CreateStartUpPageContainer
  }

  async show(screen: GlassScreenId, state: Omit<GlassScreenState, 'battery'> = {}): Promise<void> {
    const page = this.buildPage(screen, state)
    this.publishDebug(page.textObject?.[0]?.content ?? '')
    if (!this.bridge) return
    await this.bridge.rebuildPageContainer(page)
  }

  async updateMainText(content: string): Promise<void> {
    const nextContent = sanitizeForG2Text(content)
    this.publishDebug(nextContent)
    if (!this.bridge) return
    await this.bridge.textContainerUpgrade(
      new TextContainerUpgrade({
        containerID: GLASS_MAIN_CONTAINER_ID,
        containerName: GLASS_MAIN_CONTAINER_NAME,
        contentOffset: 0,
        contentLength: Math.max(this.currentContent.length, nextContent.length),
        content: nextContent,
      }),
    )
  }

  async update(content: string): Promise<void> {
    await this.updateMainText(content)
  }

  async showError(message: string): Promise<void> {
    await this.show('error', { body: message })
  }

  async showImagePreview(imageBase64: string, caption = '照片已采集'): Promise<void> {
    const content = sanitizeForG2Text(`${caption}\n正在预览，随后自动识别\nR1 上滑重拍  下滑取消`, { maxLines: 4, maxChars: 160 })
    this.publishDebug(`${content}\n[image-preview ${imageBase64.length} chars]`)
    if (!this.bridge) return

    const imageContainerId = 2
    const imageContainerName = 'preview'
    const text = new TextContainerProperty({
      xPosition: 0,
      yPosition: 198,
      width: GLASS_W,
      height: 78,
      borderWidth: 0,
      borderColor: GlassColor.Bright,
      borderRadius: 0,
      paddingLength: 0,
      containerID: GLASS_MAIN_CONTAINER_ID,
      containerName: GLASS_MAIN_CONTAINER_NAME,
      content,
      isEventCapture: 1,
    })
    const image = new ImageContainerProperty({
      xPosition: 144,
      yPosition: 34,
      width: 288,
      height: 144,
      containerID: imageContainerId,
      containerName: imageContainerName,
    })

    await this.bridge.rebuildPageContainer(new RebuildPageContainer({
      containerTotalNum: 2,
      textObject: [text],
      imageObject: [image],
    }))

    this.imageQueue = this.imageQueue
      .catch(() => undefined)
      .then(() => this.updatePreviewImage(imageContainerId, imageContainerName, imageBase64))
    await this.imageQueue
  }

  private async updatePreviewImage(containerID: number, containerName: string, imageBase64: string): Promise<void> {
    const payloads = await this.createPreviewPayloads(imageBase64)
    const results: string[] = []

    for (const payload of payloads) {
      const updateResult = await this.tryUpdatePreviewImage(containerID, containerName, payload.data)
      results.push(`${payload.label}=${String(updateResult.result)}`)
      if (updateResult.ok) return
    }

    throw new Error(`G2 image preview failed: ${results.join('; ')}`)
  }

  private async tryUpdatePreviewImage(
    containerID: number,
    containerName: string,
    imageData: number[] | string,
  ): Promise<{ ok: boolean; result: unknown }> {
    const result = await this.bridge!.updateImageRawData(new ImageRawDataUpdate({
      containerID,
      containerName,
      imageData,
    }))
    return {
      ok: ImageRawDataUpdateResult.isSuccess(ImageRawDataUpdateResult.normalize(result)),
      result,
    }
  }

  private async createPreviewPayloads(imageBase64: string): Promise<PreviewImagePayload[]> {
    const payloads: PreviewImagePayload[] = []

    for (const preset of [
      { label: 'gray288Bytes', width: 288, height: 144, quality: 0.46 },
      { label: 'gray192Bytes', width: 192, height: 96, quality: 0.42 },
    ]) {
      const dataUrl = await this.createGrayPreviewDataUrl(imageBase64, preset.width, preset.height, preset.quality)
      if (!dataUrl) continue
      const base64 = dataUrl.split(',')[1]
      if (!base64) continue

      payloads.push({ label: preset.label, data: this.base64ToNumberArray(base64) })
      payloads.push({ label: preset.label.replace('Bytes', 'Base64'), data: base64 })
      payloads.push({ label: preset.label.replace('Bytes', 'DataUrl'), data: dataUrl })
    }

    payloads.push({ label: 'originalBase64', data: imageBase64 })
    payloads.push({ label: 'originalDataUrl', data: `data:image/jpeg;base64,${imageBase64}` })
    return payloads
  }

  private async createGrayPreviewDataUrl(
    imageBase64: string,
    maxWidth: number,
    maxHeight: number,
    quality: number,
  ): Promise<string | undefined> {
    try {
      const image = await this.loadPreviewImage(`data:image/jpeg;base64,${imageBase64}`)
      const sourceWidth = image.naturalWidth || maxWidth
      const sourceHeight = image.naturalHeight || maxHeight
      const scale = Math.min(1, maxWidth / sourceWidth, maxHeight / sourceHeight)
      const width = Math.max(20, Math.min(maxWidth, Math.round(sourceWidth * scale)))
      const height = Math.max(20, Math.min(maxHeight, Math.round(sourceHeight * scale)))
      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      const context = canvas.getContext('2d', { willReadFrequently: true })
      if (!context) return undefined

      context.fillStyle = '#ffffff'
      context.fillRect(0, 0, width, height)
      context.drawImage(image, 0, 0, width, height)

      const imageData = context.getImageData(0, 0, width, height)
      const pixels = imageData.data
      for (let index = 0; index < pixels.length; index += 4) {
        const gray = pixels[index] * 0.299 + pixels[index + 1] * 0.587 + pixels[index + 2] * 0.114
        const contrasted = Math.max(0, Math.min(255, (gray - 128) * 1.18 + 128))
        pixels[index] = contrasted
        pixels[index + 1] = contrasted
        pixels[index + 2] = contrasted
        pixels[index + 3] = 255
      }
      context.putImageData(imageData, 0, 0)

      return canvas.toDataURL('image/jpeg', quality)
    } catch (error) {
      console.warn('[G2 preview] grayscale SDK payload generation failed', error)
      return undefined
    }
  }

  private loadPreviewImage(dataUrl: string): Promise<HTMLImageElement> {
    return new Promise((resolve, reject) => {
      const image = new Image()
      image.decoding = 'async'
      image.onload = () => resolve(image)
      image.onerror = () => reject(new Error('G2 preview image decode failed'))
      image.src = dataUrl
    })
  }

  private base64ToNumberArray(base64: string): number[] {
    const binary = atob(base64)
    const bytes = new Array<number>(binary.length)
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index)
    }
    return bytes
  }

  render(screen: GlassScreenId, state: Omit<GlassScreenState, 'battery'> = {}): string {
    return renderGlassScreen(screen, { ...state, battery: this.getBatteryText() })
  }

  private buildPage(screen: GlassScreenId, state: Omit<GlassScreenState, 'battery'>): RebuildPageContainer {
    const content = this.render(screen, state)
    const text = new TextContainerProperty({
      xPosition: 0,
      yPosition: 0,
      width: GLASS_W,
      height: GLASS_H,
      borderWidth: 0,
      borderColor: GlassColor.Bright,
      borderRadius: 0,
      paddingLength: 0,
      containerID: GLASS_MAIN_CONTAINER_ID,
      containerName: GLASS_MAIN_CONTAINER_NAME,
      content,
      isEventCapture: 1,
    })

    this.currentContent = content
    return new RebuildPageContainer({
      containerTotalNum: 1,
      textObject: [text],
    })
  }

  private publishDebug(content: string): void {
    this.currentContent = content
    this.onDebug?.(content)
  }
}
