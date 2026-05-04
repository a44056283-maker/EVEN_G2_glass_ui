import {
  type CreateStartUpPageContainer,
  type EvenAppBridge,
  RebuildPageContainer,
  TextContainerProperty,
  TextContainerUpgrade,
} from '@evenrealities/even_hub_sdk'
import { renderGlassScreen, type GlassScreenId, type GlassScreenState } from './glassScreens'
import { sanitizeForG2Text } from './glassText'
import { GlassColor, GLASS_H, GLASS_MAIN_CONTAINER_ID, GLASS_MAIN_CONTAINER_NAME, GLASS_W } from './glassTheme'

export class GlassRenderer {
  private currentContent = ''

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
