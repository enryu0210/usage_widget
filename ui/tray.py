"""시스템 트레이 아이콘 모듈 (pystray).

위젯은 타이틀바가 없어 작업 표시줄에 나타나지 않으므로, 트레이 아이콘이
숨김/표시·종료·시작 프로그램 설정의 유일한 진입점이 된다.
pystray 가 없는 소스 실행 환경에서는 트레이 없이 기존처럼 동작하도록 None 을 반환한다.
"""

from __future__ import annotations

import sys
import threading
import time
import winreg
from pathlib import Path
from typing import TYPE_CHECKING

from . import autostart, updater

if TYPE_CHECKING:
    from .app import UsageWidgetApp

# PyInstaller onefile 은 리소스를 임시 폴더(_MEIPASS)에 풀어두므로 실행 형태에 따라 기준 경로가 다르다.
_BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
ICON_PATH = _BASE_DIR / "assets" / "icon.ico"


def start_tray(app: UsageWidgetApp):
    """트레이 아이콘을 별도 스레드에서 띄우고 Icon 객체를 반환한다(실패 시 None)."""
    try:
        import pystray
        from PIL import Image
    except ImportError:
        return None

    # 트레이 콜백은 트레이 스레드에서 호출되므로, Tk 조작은 반드시 root.after 로 메인 스레드에 넘긴다.
    def on_main(fn):
        return lambda: app.root.after(0, fn)

    def toggle_autostart(icon, _item) -> None:
        autostart.set_enabled(not autostart.is_enabled())
        icon.update_menu()  # 체크 표시 갱신

    menu = pystray.Menu(
        pystray.MenuItem("위젯 보이기/숨기기", on_main(app.toggle_visible), default=True),
        pystray.MenuItem("새로고침", on_main(app.refresh_async)),
        pystray.MenuItem(
            "Windows 시작 시 실행",
            toggle_autostart,
            checked=lambda _item: autostart.is_enabled(),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("종료", on_main(app.quit)),
    )
    try:
        icon = pystray.Icon("AIUsageWidget", Image.open(ICON_PATH), f"AI 잔여 사용량 v{updater.APP_VERSION}", menu)
    except OSError:
        return None  # 아이콘 파일 누락 시 트레이 없이 실행
    def on_ready(icon) -> None:
        icon.visible = True
        time.sleep(3)  # Explorer 가 아이콘 설정 레지스트리 항목을 만들 시간을 준다.
        _promote_to_taskbar()

    threading.Thread(target=icon.run, kwargs={"setup": on_ready}, daemon=True).start()
    return icon


def _promote_to_taskbar() -> None:
    """Windows 11 은 새 트레이 아이콘을 '숨겨진 아이콘(^)'에 넣으므로, 첫 실행 시 작업 표시줄에 꺼내 놓는다.

    IsPromoted 값이 아직 없을 때만 1로 쓴다. 사용자가 직접 숨기면 Explorer 가 0을 기록하므로
    그 선택은 덮어쓰지 않는다. 소스 실행은 python(w).exe 전체가 대상이 되므로 exe 일 때만 한다.
    ponytail: 비공식 레지스트리(NotifyIconSettings) 기반 — Windows 가 형식을 바꾸면 조용히 아무 일도 안 한다.
    """
    if not getattr(sys, "frozen", False):
        return
    root_path = r"Control Panel\NotifyIconSettings"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, root_path) as root_key:
            for i in range(winreg.QueryInfoKey(root_key)[0]):
                sub_name = winreg.EnumKey(root_key, i)
                with winreg.OpenKey(root_key, sub_name, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as sub:
                    try:
                        exe_path = winreg.QueryValueEx(sub, "ExecutablePath")[0]
                    except OSError:
                        continue
                    if exe_path.lower() != sys.executable.lower():
                        continue
                    try:
                        winreg.QueryValueEx(sub, "IsPromoted")
                    except FileNotFoundError:
                        winreg.SetValueEx(sub, "IsPromoted", 0, winreg.REG_DWORD, 1)
    except OSError:
        pass
