"""Windows 데스크톱 AI 잔여 사용량 위젯 실행 진입점.

UI 구현체는 ui 패키지에서, 서비스별 API 조회 및 인증 연동은 providers 패키지에서 담당하며,
이 파일은 애플리케이션 실행과 자동 검증(--check) 진입점 역할만 수행한다.
"""

from __future__ import annotations

import sys
import tkinter as tk

from ui import UsageWidgetApp


def main() -> None:
    root = tk.Tk()
    app = UsageWidgetApp(root)

    # 자동 검증 모드 (--check): 실제 렌더링까지 마친 뒤 4개 카드 생성 여부를 검증하고 종료한다.
    if "--check" in sys.argv:
        def _verify_and_quit() -> None:
            if app._is_loading:
                root.after(200, _verify_and_quit)
                return
            cards = app.cards_frame.winfo_children()
            assert len(cards) == 4, f"Expected 4 provider cards, got {len(cards)}"
            print("WIDGET_CHECK_OK: 4 provider cards rendered successfully.")
            root.destroy()

        root.after(300, _verify_and_quit)

    root.mainloop()


if __name__ == "__main__":
    main()
