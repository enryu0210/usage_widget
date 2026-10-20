"""토큰 갱신·연동 로직 오프라인 검증 (python test_providers.py).

실제 계정 토큰을 건드리지 않도록 네트워크 호출(http_json)을 가짜로 바꾸고 임시 폴더에서만 실행한다.
"""

from __future__ import annotations

import json
import os
import pathlib
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from unittest import mock

from providers import auth, claude, gemini


def check_claude_refreshes_expired_token(tmp: pathlib.Path) -> None:
    """재부팅 후처럼 access token 이 만료돼 있으면 갱신하고, 새 토큰을 파일에 되써 넣어야 한다."""
    cred = tmp / ".credentials.json"
    expired_ms = int((time.time() - 3600) * 1000)
    cred.write_text(json.dumps({"claudeAiOauth": {
        "accessToken": "old-at", "refreshToken": "old-rt", "expiresAt": expired_ms,
        "subscriptionType": "max", "scopes": ["user:inference"],
    }}), encoding="utf-8")

    calls: list[str] = []

    def fake_http_json(url, **kw):
        calls.append(url)
        if url.endswith("/oauth/token"):
            assert json.loads(kw["data"])["refresh_token"] == "old-rt"
            return {"access_token": "new-at", "refresh_token": "new-rt", "expires_in": 28800}
        assert kw["headers"]["Authorization"] == "Bearer new-at"
        return {"five_hour": {"utilization": 30, "resets_at": None}}

    with mock.patch.object(claude, "http_json", fake_http_json):
        st = claude.fetch_claude(cred)

    assert st.connected and st.metrics[0].remaining_percent == 70.0, st
    saved = json.loads(cred.read_text(encoding="utf-8"))["claudeAiOauth"]
    assert saved["accessToken"] == "new-at" and saved["refreshToken"] == "new-rt"
    assert saved["expiresAt"] > time.time() * 1000
    assert saved["scopes"] == ["user:inference"], "다른 필드는 보존돼야 한다"

    # 유효한 토큰이면 갱신 호출 없이 사용량 API 만 불러야 한다.
    calls.clear()
    with mock.patch.object(claude, "http_json", fake_http_json):
        claude.fetch_claude(cred)
    assert not any(u.endswith("/oauth/token") for u in calls), calls


def check_gemini_picks_matching_secret(tmp: pathlib.Path) -> None:
    """agy.exe 안의 첫 번째 secret 이 짝이 아니어도 검증을 통과한 secret 을 골라야 한다."""
    cid = "107" + "1" * 10 + "-" + "a" * 32 + ".apps.googleusercontent.com"
    # Push Protection 오탐을 피하려고 secret 형태 문자열을 실행 시점에 조립한다.
    wrong, right = "GOCSPX" + "-" + "W" * 28, "GOCSPX" + "-" + "R" * 28
    exe = tmp / "agy" / "bin" / "agy.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(f"xx{wrong}yy{cid}zz{wrong}{right}".encode())
    conf = tmp / "conf"
    # 옛 버전이 잘못 캐싱한(검증 표시 없는) 짝은 무시하고 다시 골라야 한다.
    conf.mkdir()
    (conf / "gemini_client.json").write_text(json.dumps({"client_id": cid, "client_secret": wrong}))

    with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(tmp)}), \
         mock.patch.object(gemini, "WIDGET_CONFIG_DIR", conf), \
         mock.patch.object(gemini, "_is_valid_client_pair", lambda c, s: s == right):
        assert gemini.get_gemini_oauth_client() == (cid, right)
    cached = json.loads((conf / "gemini_client.json").read_text())
    assert cached["client_secret"] == right and cached["verified"]


def check_agy_found_on_path(tmp: pathlib.Path) -> None:
    """기본 경로에 agy 가 없어도 PATH 에 있는 agy.exe 를 찾아야 하고, .cmd 래퍼는 거절해야 한다."""
    exe = tmp / "elsewhere" / "agy.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"")
    with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(tmp)}):
        with mock.patch.object(gemini.shutil, "which", lambda name: str(exe)):
            assert gemini._find_agy_exe() == exe
        with mock.patch.object(gemini.shutil, "which", lambda name: str(tmp / "agy.cmd")):
            try:
                gemini._find_agy_exe()
                raise AssertionError(".cmd 래퍼를 agy 바이너리로 받아들였다")
            except RuntimeError as e:
                assert "agy.cmd" in str(e)  # 오류 문구에 찾은 경로가 남아야 다음 진단이 쉽다


def check_login_ignores_stray_requests(tmp: pathlib.Path) -> None:
    """콜백 전에 favicon 같은 요청이 먼저 와도 서버가 닫히지 않고 진짜 code 를 받아야 한다."""

    def fake_browser(url: str) -> None:
        redirect_uri = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["redirect_uri"][0]
        port = redirect_uri.rsplit(":", 1)[1]

        def _hit() -> None:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/favicon.ico").read()
            urllib.request.urlopen(f"http://127.0.0.1:{port}/?code=abc").read()

        threading.Thread(target=_hit, daemon=True).start()

    def fake_http_json(url, **kw):
        assert b"code=abc" in kw["data"]
        return {"refresh_token": "rt-1"}

    with mock.patch.object(auth, "get_gemini_oauth_client", lambda: ("cid", "sec")), \
         mock.patch.object(auth.webbrowser, "open", fake_browser), \
         mock.patch.object(auth, "http_json", fake_http_json), \
         mock.patch.object(auth, "WIDGET_CONFIG_DIR", tmp):
        assert auth.link_gemini_oauth(timeout_sec=10) is True
    assert json.loads((tmp / "gemini_oauth.json").read_text())["refresh_token"] == "rt-1"


if __name__ == "__main__":
    for check in (check_claude_refreshes_expired_token, check_gemini_picks_matching_secret,
                  check_agy_found_on_path, check_login_ignores_stray_requests):
        with tempfile.TemporaryDirectory() as d:
            check(pathlib.Path(d))
        print("OK", check.__name__)
