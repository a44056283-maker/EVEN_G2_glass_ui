const { chromium } = require('playwright');

const SCREENSHOTS_DIR = '/Users/luxiangnan/Desktop/EVEN G2视觉和语音对讲系统/g2-vision-voice-assistant/docs/gpt-advisor/screenshots';

const DOM_CHECK_SCRIPT = `
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
`;

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 3,
    isMobile: true,
    hasTouch: true,
  });

  const page = await context.newPage();

  console.log('Navigating to http://192.168.13.104:5173...');
  await page.goto('http://192.168.13.104:5173', { waitUntil: 'networkidle' });

  // Screenshot 1: Normal load
  console.log('\n=== Screenshot 1: Normal Load ===');
  const domState1 = await page.evaluate(DOM_CHECK_SCRIPT);
  console.log('DOM State:', JSON.stringify(domState1, null, 2));
  await page.screenshot({ path: `${SCREENSHOTS_DIR}/ui_normal.png`, fullPage: true });
  console.log('Saved: ui_normal.png');

  // Click "视觉识别" tab (id="capture-button")
  console.log('\n=== Clicking "视觉识别" tab ===');
  await page.click('#capture-button');
  await page.waitForTimeout(1000);

  // Screenshot 2: Vision tab
  console.log('\n=== Screenshot 2: Vision Tab ===');
  const domState2 = await page.evaluate(DOM_CHECK_SCRIPT);
  console.log('DOM State:', JSON.stringify(domState2, null, 2));
  await page.screenshot({ path: `${SCREENSHOTS_DIR}/ui_vision_tab.png`, fullPage: true });
  console.log('Saved: ui_vision_tab.png');

  // Click "设置" tab (id="openclaw-button")
  console.log('\n=== Clicking "设置" tab ===');
  await page.click('#openclaw-button');
  await page.waitForTimeout(1000);

  // Screenshot 3: Settings tab
  console.log('\n=== Screenshot 3: Settings Tab ===');
  const domState3 = await page.evaluate(DOM_CHECK_SCRIPT);
  console.log('DOM State:', JSON.stringify(domState3, null, 2));
  await page.screenshot({ path: `${SCREENSHOTS_DIR}/ui_settings_tab.png`, fullPage: true });
  console.log('Saved: ui_settings_tab.png');

  await browser.close();
  console.log('\nDone!');
}

main().catch(err => {
  console.error('Error:', err);
  process.exit(1);
});
