"""Windows 시작 프로그램 등록 모듈 (HKCU Run 레지스트리).

관리자 권한이 필요 없는 현재 사용자(HKCU) Run 키를 쓰므로, 다른 PC에서 exe를 내려받아
처음 실행하기만 해도 그 사용자 계정에 자동으로 등록된다.
사용자가 트레이 메뉴로 끈 경우에는 opt-out 표식 파일을 남겨, 다음 실행 때 다시 켜지 않는다.
"""

from __future__ import annotations

import sys
import winreg
from pathlib import Path

from providers.base import WIDGET_CONFIG_DIR

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "AIUsageWidget"
OPT_OUT_FILE = WIDGET_CONFIG_DIR / "autostart_disabled"


def launch_command() -> str:
    """부팅 시 실행할 명령. exe로 패키징됐으면 exe 자신, 소스 실행이면 pythonw + widget.py."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    widget_py = Path(__file__).resolve().parents[1] / "widget.py"
    return f'"{pythonw}" "{widget_py}"'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
        return True
    except OSError:
        return False


def set_enabled(enabled: bool) -> bool:
    """등록/해제 후 성공 여부를 반환한다. 레지스트리 실패가 위젯 실행을 막아서는 안 되므로 예외를 삼킨다."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, launch_command())
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except FileNotFoundError:
                    pass
        # 사용자의 명시적 선택을 기억해, 끈 경우 다음 실행에서 자동 재등록하지 않는다.
        if enabled:
            OPT_OUT_FILE.unlink(missing_ok=True)
        else:
            WIDGET_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            OPT_OUT_FILE.touch()
        return True
    except OSError:
        return False


def register_on_launch() -> None:
    """패키징된 exe 실행 시 기본으로 시작 프로그램에 등록한다.

    매번 다시 쓰는 이유: exe를 다른 폴더로 옮겨도 레지스트리 경로가 최신 위치로 갱신되게 하기 위함.
    소스 실행(개발 중)에서는 개발 PC 레지스트리를 오염시키지 않도록 자동 등록하지 않는다.
    """
    if getattr(sys, "frozen", False) and not OPT_OUT_FILE.exists():
        set_enabled(True)
