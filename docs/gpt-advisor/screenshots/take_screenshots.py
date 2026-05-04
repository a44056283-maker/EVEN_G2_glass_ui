import asyncio
from playwright.async_api import async_playwright

SCREENSHOTS_DIR = '/Users/luxiangnan/Desktop/EVEN G2视觉和语音对讲系统/g2-vision-voice-assistant/docs/gpt-advisor/screenshots'

DOM_CHECK_SCRIPT = """
() => {
  return {
    activeBookmark: document.querySelector('#app').dataset.activeBookmark,
    kicker: document.querySelector('#bookmark-kicker')?.textContent,
    title: document.querySelector('#bookmark-title')?.textContent,
    visiblePanels: Array.from(document.querySelectorAll('[style*="display: grid"], [style*="display:flex"]')).map(el => el.className).slice(0,10),
    statusPanelDisplay: getComputedStyle(document.querySelector('.status-panel')).display,
    configPanelDisplay: getComputedStyle(document.querySelector('.config-panel')).display,
    visionResultPanelDisplay: getComputedStyle(document.querySelector('.vision-result-panel')).display,
  }
}
"""

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
        )

        page = await context.new_page()

        print('Navigating to http://192.168.13.104:5173...')
        await page.goto('http://192.168.13.104:5173', wait_until='networkidle')

        # Screenshot 1: Normal load
        print('\n=== Screenshot 1: Normal Load ===')
        dom_state_1 = await page.evaluate(DOM_CHECK_SCRIPT)
        print('DOM State:', dom_state_1)
        await page.screenshot(path=f'{SCREENSHOTS_DIR}/ui_normal.png', full_page=True)
        print('Saved: ui_normal.png')

        # Click "视觉识别" tab (id="capture-button")
        print('\n=== Clicking "视觉识别" tab ===')
        await page.click('#capture-button')
        await page.wait_for_timeout(1000)

        # Screenshot 2: Vision tab
        print('\n=== Screenshot 2: Vision Tab ===')
        dom_state_2 = await page.evaluate(DOM_CHECK_SCRIPT)
        print('DOM State:', dom_state_2)
        await page.screenshot(path=f'{SCREENSHOTS_DIR}/ui_vision_tab.png', full_page=True)
        print('Saved: ui_vision_tab.png')

        # Click "设置" tab (id="openclaw-button")
        print('\n=== Clicking "设置" tab ===')
        await page.click('#openclaw-button')
        await page.wait_for_timeout(1000)

        # Screenshot 3: Settings tab
        print('\n=== Screenshot 3: Settings Tab ===')
        dom_state_3 = await page.evaluate(DOM_CHECK_SCRIPT)
        print('DOM State:', dom_state_3)
        await page.screenshot(path=f'{SCREENSHOTS_DIR}/ui_settings_tab.png', full_page=True)
        print('Saved: ui_settings_tab.png')

        await browser.close()
        print('\nDone!')

if __name__ == '__main__':
    asyncio.run(main())
