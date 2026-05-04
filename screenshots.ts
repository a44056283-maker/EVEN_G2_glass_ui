import { chromium } from 'playwright';

const URL = 'http://192.168.13.104:5173';
const VIEWPORT = { width: 390, height: 844 }; // iPhone 14 Pro

async function main() {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: 3,
    isMobile: true,
    hasTouch: true,
  });
  const page = await context.newPage();

  // Screenshot 1: Initial state
  console.log('Navigating to', URL);
  await page.goto(URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: 'screenshot-1-initial.png', fullPage: false });
  console.log('Saved: screenshot-1-initial.png');

  // Find and click the "设置" tab
  console.log('Looking for "设置" bookmark tab...');

  // Try multiple strategies to find the tab
  const tabs = await page.locator('[role="tab"], .tab, button, a').all();
  console.log(`Found ${tabs.length} tab-like elements`);

  // Try clicking by text
  try {
    await page.locator('text=设置').first().click({ timeout: 5000 });
    console.log('Clicked "设置" tab');
  } catch (e) {
    console.log('Could not find "设置" by text, trying other methods...');
    // Try aria-label or title
    try {
      await page.locator('[aria-label="设置"]').click({ timeout: 3000 });
    } catch (e2) {
      // Try the 4th tab position
      await page.locator('[role="tab"]:nth-child(4)').click({ timeout: 3000 });
    }
  }

  await page.waitForTimeout(1500);
  await page.screenshot({ path: 'screenshot-2-settings.png', fullPage: false });
  console.log('Saved: screenshot-2-settings.png');

  // Report what we see
  console.log('\n--- UI Observations ---');

  // Check tab count
  const tabCount = await page.locator('[role="tab"]').count();
  console.log(`Bookmark tabs visible: ${tabCount}`);

  // Check for "书签 4 / 4" text
  const bookmarkText = await page.locator('text=书签').count();
  console.log(`"书签 X / X" elements found: ${bookmarkText > 0 ? 'Yes' : 'No'}`);

  // Check for connection panel
  const connectionPanel = await page.locator('text=连接, text=配置, text=连接状态').count();
  console.log(`Connection/config panel visible: ${connectionPanel > 0 ? 'Yes' : 'No'}`);

  // Check for any visible clipping or overflow
  const bodyContent = await page.locator('body').evaluate(el => ({
    scrollWidth: el.scrollWidth,
    scrollHeight: el.scrollHeight,
    clientWidth: el.clientWidth,
    clientHeight: el.clientHeight,
    overflowX: window.getComputedStyle(el).overflowX,
    overflowY: window.getComputedStyle(el).overflowY
  }));
  console.log('Body overflow:', bodyContent);

  await browser.close();
  console.log('\nDone!');
}

main().catch(console.error);
