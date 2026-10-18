"""앱 로고(icon.ico) 생성 스크립트 — 빌드 전 로고를 바꿀 때만 실행한다.
다크 둥근 사각형 위에 서비스 브랜드 색상(Claude/Codex/Gemini/Argon) 막대 4개를
잔여량 게이지처럼 세워 "사용량 위젯"임을 16px 트레이 크기에서도 알아보게 한다.
실행: python assets/make_icon.py  (Pillow 필요, 위젯 실행 자체에는 불필요)
"""

from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
SIZE = 1024  # 크게 그린 뒤 축소해 작은 크기에서도 계단 현상을 줄인다.

BG = "#12151e"
BARS = [  # (색상, 막대 높이 비율)
    ("#e07a5f", 0.80),  # Claude
    ("#10a37f", 0.55),  # Codex
    ("#4ea8de", 0.95),  # Gemini
    ("#a855f7", 0.40),  # Argon
]


def draw_logo() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), radius=SIZE // 5, fill=BG)

    pad = SIZE * 0.17
    gap = SIZE * 0.06
    bar_w = (SIZE - 2 * pad - gap * (len(BARS) - 1)) / len(BARS)
    bottom = SIZE - pad
    max_h = SIZE - 2 * pad
    for i, (color, ratio) in enumerate(BARS):
        x0 = pad + i * (bar_w + gap)
        d.rounded_rectangle(
            (x0, bottom - max_h * ratio, x0 + bar_w, bottom),
            radius=bar_w / 3,
            fill=color,
        )
    return img


if __name__ == "__main__":
    logo = draw_logo()
    logo.save(HERE / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("saved:", HERE / "icon.ico")
