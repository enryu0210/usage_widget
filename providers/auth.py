"""계정 연동 및 재로그인 실행 모듈.

Gemini/Argon의 경우 로컬 루프백 HTTP 서버를 띄워 브라우저 Google OAuth 연동을 처리하고,
Claude와 Codex의 경우 각 공식 CLI의 로그인 터미널 창을 실행한다.
"""

from __future__ import annotations

import http.server
import json
import subprocess
import time
import urllib.error
import urllib.parse
import webbrowser

from .base import WIDGET_CONFIG_DIR, http_json
from .gemini import get_gemini_oauth_client


def link_gemini_oauth(timeout_sec: int = 300) -> bool:
    """로컬 루프백 HTTP 서버를 띄워 브라우저에서 Google 계정을 직접 연동한다.

    새 PC 에서는 Google 로그인·2단계 인증까지 거치느라 시간이 걸리므로 5분을 기다린다.
    취소·시간 초과는 False, 토큰 교환 실패 같은 오류는 예외로 올려 UI 가 원인을 보여주게 한다.
    """
    client_id, client_secret = get_gemini_oauth_client()
    result: dict[str, str] = {}

    class _CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            if "code" in qs:
                result["code"] = qs["code"][0]
                body = "<h3>Google 인증을 받았습니다. 위젯으로 돌아가 결과를 확인해주세요.</h3>".encode("utf-8")
            elif "error" in qs:
                result["error"] = qs["error"][0]
                body = "<h3>연동이 취소되었습니다.</h3>".encode("utf-8")
            else:
                # favicon 등 OAuth 와 무관한 요청. 여기서 끝내면 진짜 콜백을 못 받으므로 무시한다.
                body = b""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return  # 콘솔 노이즈 방지

    server = http.server.HTTPServer(("127.0.0.1", 0), _CallbackHandler)
    port = server.server_port
    redirect_uri = f"http://localhost:{port}"

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": (
                "https://www.googleapis.com/auth/cloud-platform "
                "https://www.googleapis.com/auth/aicode "
                "https://www.googleapis.com/auth/userinfo.email"
            ),
            "access_type": "offline",
            "prompt": "consent",
        }
    )
    webbrowser.open(auth_url)
    # handle_request() 는 요청 1건만 처리하므로, 콜백(code/error)이 올 때까지 마감 시각 안에서 반복한다.
    deadline = time.monotonic() + timeout_sec
    try:
        while not result and time.monotonic() < deadline:
            server.timeout = max(1.0, deadline - time.monotonic())
            server.handle_request()
    finally:
        server.server_close()

    code = result.get("code")
    if not code:
        return False

    tok_data = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    try:
        tok_res = http_json("https://oauth2.googleapis.com/token", method="POST", data=tok_data)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Google 토큰 교환 실패 ({e.code})") from e
    if "refresh_token" in tok_res:
        WIDGET_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        (WIDGET_CONFIG_DIR / "gemini_oauth.json").write_text(
            json.dumps({"refresh_token": tok_res["refresh_token"]}, indent=2),
            encoding="utf-8",
        )
        return True
    return False


def launch_cli_login(provider_name: str) -> None:
    """Claude 또는 Codex의 공식 CLI 로그인 창을 새 터미널로 띄운다."""
    cmd_map = {
        "Claude": "claude login",
        "Codex": "codex login",
    }
    cmd = cmd_map.get(provider_name)
    if cmd:
        subprocess.Popen(["cmd.exe", "/c", "start", "cmd.exe", "/k", cmd])
