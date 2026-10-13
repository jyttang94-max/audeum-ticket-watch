
import os
import smtplib
from email.message import EmailMessage

sender = os.environ["NAVER_EMAIL"]
password = os.environ["NAVER_PASSWORD"]
recipients = [
    address.strip()
    for address in os.environ["ALERT_EMAIL"].split(",")
    if address.strip()
]

message = EmailMessage()
message["Subject"] = "[오디움] 이메일 알림 테스트 성공"
message["From"] = sender
message["To"] = ", ".join(recipients)
message.set_content(
    "오디움 취소표 감시 프로그램 V4의 이메일 발송 테스트입니다.\n\n"
    "이 메일이 도착했다면 네이버 SMTP 발송이 정상적으로 작동합니다.\n"
    "실제 취소표가 발견된 것은 아닙니다."
)

with smtplib.SMTP_SSL(
    os.environ.get("SMTP_HOST", "smtp.naver.com"),
    465,
    timeout=30,
) as smtp:
    smtp.login(sender, password)
    smtp.send_message(message)

print("테스트 이메일 발송 완료")
print("수신 대상:", len(recipients), "개")
