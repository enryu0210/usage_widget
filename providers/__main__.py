"""providers 패키지 단독 실행 자가 검증 진입점 (python -m providers)."""

from __future__ import annotations

import datetime as dt

from . import fetch_all, format_reset


def main() -> None:
    """시간 포맷터 및 4개 카드(Claude, Codex, Gemini, Argon) 조회 동작을 검증한다."""
    assert format_reset(dt.datetime.now(dt.timezone.utc).timestamp() + 3700).startswith("1시간")
    statuses = fetch_all()
    assert len(statuses) == 4
    for st in statuses:
        print(f"[{st.name}] connected={st.connected} plan={st.plan} error={st.error}")
        for m in st.metrics:
            print(f"  - {m.label}: {m.remaining_percent:.1f}% ({m.reset_text})")


if __name__ == "__main__":
    main()
