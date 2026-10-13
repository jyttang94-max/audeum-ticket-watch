
import os
import smtplib
from datetime import datetime, date
from email.message import EmailMessage
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
FIRST_OPEN = date(2026, 10, 20)
today = datetime.now(KST).date()

days_since_first = (today - FIRST_OPEN).days

# 2026-10-20부터 정확히 14일 간격으로만 발송
if days_since_first < 0 or days_since_first % 14 != 0:
    print("오늘은 신규 예약 오픈일이 아닙니다.")
else:
    sender = os.environ["NAVER_EMAIL"]
    password = os.environ["NAVER_PASSWORD"]
    recipients = [
        address.strip()
        for address in os.environ["ALERT_EMAIL"].split(",")
        if address.strip()
    ]

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = "[오디움] 2분 후 정음 전시 예약 오픈!"

    msg.set_content(
        "오디움 《정음: 소리의 여정》 신규 예약 안내\n\n"
        "오늘 오후 2시(KST)에 신규 예약이 오픈됩니다.\n"
        "토요일 관람을 원하신다면 해당 날짜부터 확인해 주세요.\n\n"
        "예약 페이지: https://audeum.org/booking\n\n"
        "※ 예약 오픈 일정은 공식 공지를 기준으로 합니다.\n"
        "※ 이 메일은 예약을 자동으로 진행하지 않습니다."
    )

    with smtplib.SMTP_SSL(
        os.environ.get("SMTP_HOST", "smtp.naver.com"),
        465,
        timeout=30,
    ) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)

    print("신규 예약 오픈 사전 알림 발송 완료")
