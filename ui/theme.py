"""데스크톱 위젯의 다크 테마 색상 팔레트 및 상태 색상 계산 모듈."""

from __future__ import annotations

BG_MAIN = "#12151e"
BG_CARD = "#1b202e"
BG_BAR = "#2a3142"
FG_TEXT = "#f0f4f8"
FG_SUB = "#8c96a8"
BORDER_COLOR = "#262d40"

BRAND_COLORS = {
    "Claude": "#e07a5f",
    "Codex": "#10a37f",
    "Gemini": "#4ea8de",
    "Argon": "#a855f7",
}

REFRESH_INTERVAL_MS = 60_000  # 1분 주기 자동 갱신


def bar_color(percent: float, brand_color: str) -> str:
    """잔여량이 부족할 때 경고 색상으로 즉시 인지할 수 있게 한다."""
    if percent <= 15.0:
        return "#ef476f"  # 위험 (빨강)
    if percent <= 35.0:
        return "#ffd166"  # 주의 (노랑)
    return brand_color
