
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

URL = "https://audeum.org/booking"
OUTPUT = Path("inspection")
OUTPUT.mkdir(exist_ok=True)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            viewport={"width": 1440, "height": 1000},
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )

        await page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=60000,
        )
        await page.wait_for_timeout(5000)

        await page.screenshot(
            path=str(OUTPUT / "booking.png"),
            full_page=True,
        )

        data = await page.locator(
            "button, input, [role='button']"
        ).evaluate_all(
            """elements => elements.map(el => ({
                tag: el.tagName,
                text: (el.innerText || el.value || "").trim(),
                disabled: el.disabled || false,
                ariaDisabled: el.getAttribute("aria-disabled"),
                className: String(el.className || ""),
                outerHTML: el.outerHTML.slice(0, 1200)
            }))"""
        )

        (OUTPUT / "elements.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        (OUTPUT / "page.html").write_text(
            await page.content(),
            encoding="utf-8",
        )

        print("예약 페이지:", page.url)
        print("수집한 화면 요소:", len(data))
        print("검사용 파일 저장 완료")

        await browser.close()


asyncio.run(main())
