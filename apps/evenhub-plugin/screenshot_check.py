from playwright.sync_api import sync_playwright
import json

screenshot_path = '/Users/luxiangnan/Desktop/EVEN G2视觉和语音对讲系统/g2-vision-voice-assistant/docs/gpt-advisor/screenshots/phone_ui_check.png'
url = 'http://192.168.13.104:5173'

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 430, "height": 932})  # iPhone 14 Pro size

    print(f"Navigating to {url}...")
    page.goto(url, wait_until='networkidle', timeout=15000)
    print("Page loaded, waiting for network idle...")

    # Take screenshot
    page.screenshot(path=screenshot_path, full_page=False)
    print(f"Screenshot saved to {screenshot_path}")

    # Check CSS properties
    print("\n--- CSS/DOM Checks ---")
    checks = [
        "getComputedStyle(document.querySelector('.bookmark-panel')).display",
        "getComputedStyle(document.querySelector('.bookmark-tabs')).display",
        "getComputedStyle(document.querySelector('.status-panel')).display",
        "getComputedStyle(document.querySelector('.vision-result-panel')).display",
        "document.querySelector('#app').dataset.activeBookmark"
    ]

    for check in checks:
        try:
            result = page.evaluate(check)
            print(f"{check} => {result}")
        except Exception as e:
            print(f"{check} => ERROR: {e}")

    browser.close()
    print("\nDone!")