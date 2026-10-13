
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from monitor_v4 import (
    inspect,
    load_previous,
    save_json,
    STATE_FILE,
    OUTPUT,
)

KST = ZoneInfo("Asia/Seoul")


async def main():
    previous = load_previous()
    current, errors = await inspect()

    save_json(OUTPUT / "current.json", current)
    save_json(OUTPUT / "errors.json", errors)

    if errors or not current:
        raise RuntimeError(
            "예약 정보 수집이 불완전하여 상태를 갱신하지 않습니다."
        )

    changes = []

    if previous is not None:
        for key, item in current.items():
            old = previous.get(key, {}).get("status")
            new = item["status"]

            if old != new:
                changes.append({
                    **item,
                    "previous_status": old,
                    "change_type": "status_changed",
                })

            elif old is None and new == "candidate":
                changes.append({
                    **item,
                    "previous_status": None,
                    "change_type": "new_candidate",
                })

    save_json(OUTPUT / "changes.json", changes)

    print("검사 시각:", datetime.now(KST).isoformat())
    print("확인한 회차:", len(current))
    print("오류:", len(errors))
    print("변경된 회차:", len(changes))
    print("안전 모드: 이메일 발송하지 않음")

    save_json(STATE_FILE, current)
    print("상태 저장 완료")


if __name__ == "__main__":
    asyncio.run(main())
