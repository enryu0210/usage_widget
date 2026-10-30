"""Windows 데스크톱 AI 잔여 사용량 위젯 실행 진입점.

UI 구현체는 ui 패키지에서, 서비스별 API 조회 및 인증 연동은 providers 패키지에서 담당하며,
이 파일은 애플리케이션 실행과 자동 검증(--check) 진입점 역할만 수행한다.
"""

from __future__ import annotations

import ctypes
import sys
import time
import tkinter as tk

from ui import UsageWidgetApp, autostart, start_tray, updater

ERROR_ALREADY_EXISTS = 183


def already_running(wait_seconds: float = 0) -> bool:
    """시작 프로그램 + 수동 실행으로 위젯·트레이 아이콘이 두 개 뜨는 것을 막는다(명명된 뮤텍스).

    자동 업데이트 직후에는 이전 프로세스가 종료되는 중이라 잠깐 뮤텍스를 쥐고 있으므로,
    wait_seconds 동안은 풀리기를 기다렸다가 다시 잡아 본다.
    """
    kernel32 = ctypes.windll.kernel32
    deadline = time.monotonic() + wait_seconds
    while True:
        # 잡은 핸들은 프로세스 종료 시 OS 가 회수하므로 일부러 닫지 않는다(닫으면 잠금이 풀린다).
        handle = kernel32.CreateMutexW(None, False, "Local\\AIUsageWidget")
        if kernel32.GetLastError() != ERROR_ALREADY_EXISTS:
            return False
        kernel32.CloseHandle(handle)  # 남이 쥔 뮤텍스에 대한 내 참조만 놓는다
        if time.monotonic() >= deadline:
            return True
        time.sleep(0.5)


def main() -> None:
    is_check = "--check" in sys.argv
    wait = 15 if updater.UPDATED_FLAG in sys.argv else 0
    if not is_check and already_running(wait):
        return

    autostart.register_on_launch()

    root = tk.Tk()
    app = UsageWidgetApp(root)
    app.tray = start_tray(app)
    if not is_check:
        updater.start(app)

    # 자동 검증 모드 (--check): 실제 렌더링까지 마친 뒤 '표시 설정에서 켠 카드' 수만큼 그려졌는지 검증하고 종료한다.
    if is_check:
        def _verify_and_quit() -> None:
            if app._is_loading:
                root.after(200, _verify_and_quit)
                return
            cards = app.cards_frame.winfo_children()
            expected = sum(app.display.card_visible(st.name) for st in app._last_statuses)
            assert len(cards) == expected, f"Expected {expected} provider cards, got {len(cards)}"
            print(f"WIDGET_CHECK_OK: {expected} provider cards rendered successfully. tray={'on' if app.tray else 'off'}")
            app.quit()

        root.after(300, _verify_and_quit)

    root.mainloop()


if __name__ == "__main__":
    main()
