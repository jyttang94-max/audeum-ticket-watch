
import asyncio
import json
import os
import re
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.async_api import async_playwright

URL = "https://audeum.org/booking"
STATE_FILE = Path("state/audeum_state_v4.json")
OUTPUT = Path("inspection_v4")
OUTPUT.mkdir(exist_ok=True)
STATE_FILE.parent.mkdir(exist_ok=True)

MAX_MONTHS = 3
KST = ZoneInfo("Asia/Seoul")


def load_previous():
    if not STATE_FILE.exists():
        return None
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_json(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def send_email(changes):
    sender = os.environ["NAVER_EMAIL"]
    password = os.environ["NAVER_PASSWORD"]
    recipients = [
        address.strip()
        for address in os.environ["ALERT_EMAIL"].split(",")
        if address.strip()
    ]
    host = os.environ.get("SMTP_HOST", "smtp.naver.com")

    changes.sort(
        key=lambda item: (
            item["date"].endswith(""),
            datetime.strptime(item["date"], "%Y-%m-%d").weekday() != 5,
            item["date"],
            item["time"],
        )
    )

    lines = [
        "오디움 《정음: 소리의 여정》 예약 상태 변경 감지",
        "",
        "이전에 매진이었던 회차에서 매진 표시가 사라지고",
        "예약 회차 선택 요소가 확인되었습니다.",
        "실제 예약 완료 가능 여부는 예약 페이지에서 확인해 주세요.",
        "",
    ]

    for item in changes:
        weekday = "월화수목금토일"[
            datetime.strptime(item["date"], "%Y-%m-%d").weekday()
        ]
        priority = " ★ 토요일" if weekday == "토" else ""
        lines.append(
            f"• {item['date']}({weekday}) "
            f"{item['time']}{priority}"
        )

    lines.extend([
        "",
        f"예약 페이지: {URL}",
        "",
        "※ 자동 예약은 진행하지 않았습니다.",
        "※ 예약 가능 상태는 확인 시점 이후 변경될 수 있습니다.",
    ])

    message = EmailMessage()
    message["Subject"] = (
        f"[오디움 취소표 감지] {len(changes)}개 회차 상태 변경"
    )
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.set_content("\n".join(lines))

    with smtplib.SMTP_SSL(host, 465, timeout=30) as smtp:
        smtp.login(sender, password)
        smtp.send_message(message)

    print(f"이메일 발송 완료: 수신자 {len(recipients)}명")


async def available_dates(page):
    return await page.locator(
        "#datepicker_reserve td[data-handler='selectDay'] a[data-date]"
    ).evaluate_all("""
        links => links.map(a => {
            const td = a.closest("td");
            const y = Number(td.dataset.year);
            const m = Number(td.dataset.month) + 1;
            const d = Number(a.dataset.date);
            return [
                y,
                String(m).padStart(2, "0"),
                String(d).padStart(2, "0")
            ].join("-");
        })
    """)


async def read_slots(page):
    return await page.locator(".time-slots").evaluate_all("""
        elements => elements.map(el => ({
            date: el.querySelector("spectate_date")
                ?.textContent.trim() || "",
            time: el.querySelector("spectate_time")
                ?.textContent.trim() || "",
            sold_out: el.classList.contains("disabled-time-slots")
                || el.innerText.includes("매진"),
            has_selection_element: !!el.querySelector("label"),
            has_reservation_id: !!el.querySelector("seq_reserve")
                ?.textContent.trim(),
            text: el.innerText.trim()
        }))
    """)


async def inspect():
    found = {}
    errors = []
    today = datetime.now(KST).date().isoformat()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            viewport={"width": 1440, "height": 1000},
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
                state="visible", timeout=30000
            )
            await exhibition.click()

            await page.locator(
                "#datepicker_reserve .ui-datepicker-calendar"
            ).wait_for(timeout=30000)

            for month_index in range(MAX_MONTHS):
                dates = await available_dates(page)

                for day in dates:
                    if day < today or day in {
                        key.split("|")[0] for key in found
                    }:
                        continue

                    try:
                        year, month, day_number = day.split("-")
                        selector = (
                            "#datepicker_reserve "
                            f"td[data-year='{year}']"
                            f"[data-month='{int(month)-1}'] "
                            f"a[data-date='{int(day_number)}']"
                        )

                        await page.locator(selector).click()

                        await page.wait_for_function(
                            """date => {
                                const nodes = [...document.querySelectorAll(
                                    ".time-slots spectate_date"
                                )];
                                return nodes.some(
                                    el => el.textContent.trim() === date
                                );
                            }""",
                            arg=day,
                            timeout=15000,
                        )

                        await page.wait_for_timeout(600)
                        slots = await read_slots(page)

                        valid = [
                            item for item in slots
                            if item["date"] == day
                            and re.fullmatch(
                                r"\d{1,2}:\d{2}", item["time"]
                            )
                        ]

                        if not valid:
                            raise RuntimeError("회차 정보를 찾지 못함")

                        for item in valid:
                            key = f"{day}|{item['time']}"

                            if item["sold_out"]:
                                status = "sold_out"
                            elif (
                                item["has_selection_element"]
                                and item["has_reservation_id"]
                            ):
                                status = "candidate"
                            else:
                                status = "unknown"

                            found[key] = {
                                "date": day,
                                "time": item["time"],
                                "status": status,
                            }

                        print(f"{day}: {len(valid)}개 회차 확인")

                    except Exception as exc:
                        errors.append(f"{day}: {exc}")
                        print(f"확인 실패: {day}: {exc}")

                if month_index < MAX_MONTHS - 1:
                    next_button = page.locator(
                        "#datepicker_reserve .ui-datepicker-next"
                    )

                    if await next_button.count() == 0:
                        break

                    if "ui-state-disabled" in (
                        await next_button.get_attribute("class") or ""
                    ):
                        break

                    await next_button.click()
                    await page.wait_for_timeout(700)

        finally:
            await browser.close()

    return found, errors


async def main():
    previous = load_previous()
    current, errors = await inspect()

    save_json(OUTPUT / "current.json", current)
    save_json(OUTPUT / "errors.json", errors)

    print("확인한 회차:", len(current))
    print("오류:", len(errors))

    if errors or not current:
        raise RuntimeError(
            "검사 결과가 불완전하여 상태 저장과 알림을 중단합니다."
        )

    changes = []

    if previous is not None:
        for key, item in current.items():
            old = previous.get(key, {}).get("status")

            if old == "sold_out" and item["status"] == "candidate":
                changes.append(item)

    save_json(OUTPUT / "changes.json", changes)

    # 알림 발송에 실패하면 상태 파일을 갱신하지 않아
    # 다음 실행에서 다시 시도할 수 있도록 합니다.
    if changes:
        print("취소표 후보 발견:", len(changes))
        send_email(changes)
    elif previous is None:
        print("첫 실행: 비교 기준을 생성합니다.")
    else:
        print("새로운 취소표 후보 없음")

    save_json(STATE_FILE, current)
    print("상태 저장 완료")


if __name__ == "__main__":
    asyncio.run(main())
