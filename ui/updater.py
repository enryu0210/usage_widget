"""GitHub Releases 자동 업데이트 모듈.

새 모델·API 변경에 대응한 버전을 친구들이 직접 다시 받지 않아도 되도록,
배포용 exe 가 최신 릴리스를 확인해 스스로 내려받고 교체한 뒤 재시작한다.
소스 실행(python widget.py)은 git 으로 갱신하므로 대상이 아니다.

릴리스 규칙: APP_VERSION 을 올리고 빌드한 뒤, 같은 번호의 태그(v1.2.3)로
dist\\AIUsageWidget.exe 를 첨부해 GitHub 릴리스를 만든다.
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess
import sys
import threading
import time
import urllib.request
from typing import TYPE_CHECKING, Callable

from providers.base import http_json

if TYPE_CHECKING:
    from .app import UsageWidgetApp

APP_VERSION = "1.0.4"
LATEST_RELEASE_URL = "https://api.github.com/repos/enryu0210/usage_widget/releases/latest"
ASSET_NAME = "AIUsageWidget.exe"
CHECK_INTERVAL_SEC = 24 * 3600  # 위젯은 시작 프로그램으로 며칠씩 켜져 있으므로 하루 한 번 다시 본다.
# 재시작된 새 exe 에게 "이전 프로세스가 아직 뮤텍스를 쥐고 있을 수 있으니 잠시 기다려라"를 알리는 인자.
UPDATED_FLAG = "--updated"
_HEADERS = {"User-Agent": "AIUsageWidget-updater", "Accept": "application/vnd.github+json"}


def parse_version(text: str) -> tuple[int, ...]:
    """'v1.2.3' 또는 '1.2.3' 을 (1, 2, 3) 으로 바꾼다. 숫자가 아니면 ValueError."""
    return tuple(int(part) for part in text.strip().lstrip("vV").split("."))


def sha256_of(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_update(exe_path: pathlib.Path) -> tuple[str, str] | None:
    """새 버전이 있으면 (다운로드 URL, 기대 sha256) 을, 없으면 None 을 돌려준다."""
    release = http_json(LATEST_RELEASE_URL, headers=_HEADERS)
    if parse_version(str(release.get("tag_name") or "0")) <= parse_version(APP_VERSION):
        return None
    for asset in release.get("assets") or []:
        if asset.get("name") != ASSET_NAME:
            continue
        expected = str(asset.get("digest") or "").removeprefix("sha256:")
        # 해시가 없으면 받은 파일이 온전한지 확인할 방법이 없으므로 설치하지 않는다.
        if not expected:
            return None
        # APP_VERSION 을 안 올리고 릴리스해도 '받고 → 재시작 → 또 받고' 무한 반복이 되지 않게,
        # 지금 실행 중인 파일이 이미 그 릴리스 파일이면 건너뛴다.
        if sha256_of(exe_path) == expected:
            return None
        return str(asset["browser_download_url"]), expected
    return None


def install(exe_path: pathlib.Path, url: str, expected_sha256: str) -> bool:
    """새 exe 를 내려받아 해시를 확인한 뒤 실행 중인 exe 와 바꿔치기한다. 성공하면 True.

    Windows 는 실행 중인 exe 를 덮어쓸 수는 없지만 이름은 바꿀 수 있다.
    그래서 현재 파일을 .old 로 비키고 새 파일을 원래 이름에 놓는다(시작 프로그램 경로 그대로 유지).
    """
    new_path = exe_path.with_name(exe_path.name + ".new")
    old_path = exe_path.with_name(exe_path.name + ".old")
    req = urllib.request.Request(url, headers={"User-Agent": _HEADERS["User-Agent"]})
    with urllib.request.urlopen(req, timeout=60) as resp, open(new_path, "wb") as f:
        while chunk := resp.read(1 << 20):
            f.write(chunk)
    if sha256_of(new_path) != expected_sha256:
        new_path.unlink(missing_ok=True)  # 손상·변조된 파일은 절대 실행하지 않는다
        return False

    old_path.unlink(missing_ok=True)
    os.replace(exe_path, old_path)
    try:
        os.replace(new_path, exe_path)
    except OSError:
        os.replace(old_path, exe_path)  # 새 파일을 못 놓았으면 원래 exe 를 되돌려 실행 불가 상태를 막는다
        raise
    return True


def relaunch(exe_path: pathlib.Path) -> None:
    """교체된 exe 를 새 프로세스로 띄운다."""
    # PyInstaller onefile 은 환경변수로 자식에게 자기 임시 폴더(_MEI)를 물려주는데,
    # 이 프로세스가 곧 종료되며 그 폴더를 지우므로 새 프로세스는 처음부터 다시 풀게 한다.
    env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
    subprocess.Popen([str(exe_path), UPDATED_FLAG], env=env, close_fds=True)


def check_and_update(exe_path: pathlib.Path, on_installed: Callable[[], None]) -> None:
    """한 번 확인하고, 새 버전을 설치했으면 재시작한 뒤 on_installed(앱 종료)를 부른다."""
    try:
        found = find_update(exe_path)
        if found and install(exe_path, *found):
            relaunch(exe_path)
            on_installed()
    except Exception:
        # 오프라인·GitHub 장애·권한 문제(Program Files 설치 등)는 위젯 사용을 막을 이유가 아니다.
        # 다음 확인 주기에 다시 시도한다.
        pass


def start(app: UsageWidgetApp) -> None:
    """배포용 exe 일 때만 백그라운드에서 시작 시 + 하루마다 업데이트를 확인한다."""
    if not getattr(sys, "frozen", False):
        return
    exe_path = pathlib.Path(sys.executable)
    # 직전 업데이트에서 비켜 둔 옛 exe 정리. 이전 프로세스가 아직 안 끝나 잠겨 있으면 다음 실행 때 지운다.
    _remove_quietly(exe_path.with_name(exe_path.name + ".old"))

    def loop() -> None:
        while True:
            # Tk 조작은 메인 스레드에서만 해야 하므로 종료도 root.after 로 넘긴다.
            check_and_update(exe_path, lambda: app.root.after(0, app.quit))
            time.sleep(CHECK_INTERVAL_SEC)

    threading.Thread(target=loop, daemon=True).start()


def _remove_quietly(path: pathlib.Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
