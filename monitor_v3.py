
import asyncio
import json
import re
from datetime import date
from pathlib import Path
from playwright.async_api import async_playwright

URL = "https://audeum.org/booking"
OUT = Path("inspection")
OUT.mkdir(exist_ok=True)

# 현재 달부터 최대 3개월의 예약 달력을 확인
MAX_MONTHS = 3


async def read_dates(page):
    return await page.locator(
        "#datepicker_reserve td[data-handler='selectDay'] a[data-date]"
    ).evaluate_all("""
        links => links.map(a => ({
            day: a.getAttribute("data-date"),
            month: a.closest("td").getAttribute("data-month"),
            year: a.closest("td").getAttribute("data-year")
        }))
    """)


async def read_slots(page):
    return await page.locator(".time-slots").evaluate_all("""
        nodes => nodes.map(el => ({
            date: el.querySelector("spectate_date")?.textContent.trim() || "",
            time: el.querySelector("spectate_time")?.textContent.trim() || "",
            sold_out: el.classList.contains("disabled-time-slots"),
            sold_out_text: el.innerText.includes("매진"),
            classes: el.className,
            text: el.innerText.trim()
        }))
    """)


async def main():
    results = []
    errors = []

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
            await exhibition.click()

            await page.locator(
                "#datepicker_reserve .ui-datepicker-calendar"
            ).wait_for(timeout=30000)

            today = date.today().isoformat()
            seen = set()

            for month_index in range(MAX_MONTHS):
                dates = await read_dates(page)
                print(
                    f"달력 {month_index + 1}: "
                    f"선택 가능한 날짜 {len(dates)}개"
                )

                for item in dates:
                    year = int(item["year"])
                    month = int(item["month"]) + 1
                    day = int(item["day"])
                    day_string = f"{year:04d}-{month:02d}-{day:02d}"

                    if day_string < today or day_string in seen:
                        continue

                    seen.add(day_string)

                    try:
                        selector = (
                            "#datepicker_reserve "
                            f"td[data-year='{year}']"
                            f"[data-month='{month - 1}'] "
                            f"a[data-date='{day}']"
                        )

                        await page.locator(selector).click()
                        await page.wait_for_timeout(1500)

                        slots = await read_slots(page)
                        valid_slots = [
                            slot for slot in slots
                            if slot["date"] == day_string
                            and re.fullmatch(
                                r"\d{1,2}:\d{2}",
                                slot["time"]
                            )
                        ]

                        if not valid_slots:
                            errors.append(
                                f"{day_string}: 회차 정보를 확인하지 못함"
                            )
                            continue

                        for slot in valid_slots:
                            # 매진이 아니라는 이유만으로
                            # 예약 가능하다고 단정하지 않음
                            slot["status"] = (
                                "sold_out"
                                if slot["sold_out"] or slot["sold_out_text"]
                                else "needs_verification"
                            )
                            results.append(slot)

                        print(
                            day_string,
                            len(valid_slots),
                            "개 회차 확인"
                        )

                    except Exception as exc:
                        errors.append(
                            f"{day_string}: {type(exc).__name__}: {exc}"
                        )

                if month_index < MAX_MONTHS - 1:
                    next_button = page.locator(
                        "#datepicker_reserve .ui-datepicker-next"
                    )
                    if await next_button.count() == 0:
                        break

                    await next_button.click()
                    await page.wait_for_timeout(1200)

            results.sort(
                key=lambda x: (x["date"], x["time"])
            )

            (OUT / "slots.json").write_text(
                json.dumps(
                    results, ensure_ascii=False, indent=2
                ),
                encoding="utf-8",
            )

            (OUT / "errors.json").write_text(
                json.dumps(
                    errors, ensure_ascii=False, indent=2
                ),
                encoding="utf-8",
            )

            await page.screenshot(
                path=str(OUT / "booking.png"),
                full_page=True,
            )

            print("총 확인 회차:", len(results))
            print("확인 실패 날짜:", len(errors))
            print("V3 정보 수집 완료")

        finally:
            await browser.close()


asyncio.run(main())
