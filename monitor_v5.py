
import asyncio
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

from monitor_v4 import inspect, save_json

URL = "https://audeum.org/booking"
KST = ZoneInfo("Asia/Seoul")

STATE_FILE = Path("state_v5/audeum_state_v5.json")
OUTPUT = Path("inspection_v5")

STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.mkdir(parents=True, exist_ok=True)


def load_previous():
    if not STATE_FILE.exists():
        return None

    import json
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def is_saturday(item):
    return datetime.strptime(
        item["date"], "%Y-%m-%d"
    ).weekday() == 5


def send_email(changes):
    sender = os.environ["NAVER_EMAIL"]
    password = os.environ["NAVER_PASSWORD"]
    host = os.environ.get("SMTP_HOST", "smtp.naver.com")

    recipients = [
        email.strip()
        for email in os.environ["ALERT_EMAIL"].split(",")
        if email.strip()
    ]

    if not recipients:
        raise RuntimeError("이메일 수신자가 없습니다.")

    changes.sort(
        key=lambda item: (
            not is_saturday(item),
            item["date"],
            item["time"],
        )
    )

    saturday_count = sum(is_saturday(item) for item in changes)

    lines = [
        "오디움 《정음: 소리의 여정》",
        "예약 가능 후보가 감지되었습니다.",
        "",
        f"감지된 회차: {len(changes)}개",
        f"토요일 회차: {saturday_count}개",
        "",
    ]

    for item in changes:
        date = item["date"]
        time = item["time"]

        weekday = "월화수목금토일"[
            datetime.strptime(date, "%Y-%m-%d").weekday()
        ]

        priority = " ★ 토요일 우선" if weekday == "토" else ""

        kind = (
            "신규 회차"
            if item["change_type"] == "new_candidate"
            else "매진 상태 변경"
        )

        lines.append(
            f"• {date}({weekday}) {time}"
            f"{priority} [{kind}]"
        )

    lines.extend([
        "",
        f"예약 페이지: {URL}",
        "",
        "※ 예약 가능이 확정된 것은 아닙니다.",
        "※ 매진 표시가 사라지고 회차 선택 요소가",
        "   확인된 경우를 후보로 분류합니다.",
        "※ 실제 예약 가능 여부는 사이트에서 확인하세요.",
        "※ 자동 예약은 진행하지 않습니다.",
    ])

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = (
        f"[오디움 예약 후보] {len(changes)}개 회차 감지"
        + (" ★ 토요일 포함" if saturday_count else "")
    )
    msg.set_content("\n".join(lines))

    with smtplib.SMTP_SSL(host, 465, timeout=30) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)

    print(f"이메일 발송 완료: {len(recipients)}명")


async def main():
    previous = load_previous()
    current, errors = await inspect()

    save_json(OUTPUT / "current.json", current)
    save_json(OUTPUT / "errors.json", errors)

    print("검사 시각:", datetime.now(KST).isoformat())
    print("확인한 회차:", len(current))
    print("오류:", len(errors))

    if errors or not current:
        raise RuntimeError(
            "검사 결과가 불완전하여 알림과 상태 저장을 중단합니다."
        )

    if previous is None:
        save_json(OUTPUT / "changes.json", [])
        save_json(STATE_FILE, current)
        print("V5 첫 실행: 기준 상태 생성 완료")
        print("첫 실행에서는 이메일을 발송하지 않습니다.")
        return

    changes = []

    for key, item in current.items():
        old = previous.get(key, {}).get("status")
        new = item["status"]

        if new != "candidate":
            continue

        if old == "sold_out":
            change_type = "sold_out_to_candidate"
        elif old is None:
            change_type = "new_candidate"
        else:
            continue

        changes.append({
            **item,
            "previous_status": old,
            "change_type": change_type,
        })

    save_json(OUTPUT / "changes.json", changes)

    print("예약 가능 후보 변화:", len(changes))

    if changes:
        send_email(changes)
    else:
        print("새로운 예약 가능 후보 없음")

    # 발송 실패 시 상태를 갱신하지 않아 다음 실행에 재시도
    save_json(STATE_FILE, current)
    print("V5 상태 저장 완료")


if __name__ == "__main__":
    asyncio.run(main())
