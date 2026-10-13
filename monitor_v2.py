
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
            viewport={"width": 1440, "height": 1100},
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )

        try:
            await page.goto(
                URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            exhibition = page.locator(
                ".exhibition-item.exhibition"
            ).filter(has_text="정음")

            await exhibition.wait_for(
                state="visible",
                timeout=30000,
            )

            print("정음 전시 항목 확인")

            await exhibition.click()
            print("전시 선택 완료")

            try:
                await page.locator(
                    ".exhibition-date-wrapper"
                ).locator(
                    "button, input, a, [class*='calendar']"
                ).first.wait_for(timeout=20000)

                print("날짜 화면 요소 확인")

            except Exception:
                print("날짜 화면 로딩 여부 추가 확인 필요")

            await page.wait_for_timeout(3000)

            await page.screenshot(
                path=str(OUTPUT / "booking.png"),
                full_page=True,
            )

            html = await page.content()

            (OUTPUT / "page.html").write_text(
                html,
                encoding="utf-8",
            )

            data = await page.locator(
                ".exhibition-date-wrapper"
            ).evaluate_all(
                """elements => elements.map(el => ({
                    text: el.innerText,
                    html: el.outerHTML.slice(0, 30000)
                }))"""
            )

            (OUTPUT / "elements.json").write_text(
                json.dumps(
                    data,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            print("예약 달력 화면 정보 수집 완료")

        finally:
            await browser.close()


asyncio.run(main())
