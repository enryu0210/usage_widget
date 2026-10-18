"""계정 연동 및 재로그인 실행 모듈.

Gemini/Argon의 경우 로컬 루프백 HTTP 서버를 띄워 브라우저 Google OAuth 연동을 처리하고,
Claude와 Codex의 경우 각 공식 CLI의 로그인 터미널 창을 실행한다.
"""

from __future__ import annotations

import http.server
import json
import subprocess
import urllib.parse
import webbrowser

from .base import WIDGET_CONFIG_DIR, http_json
from .gemini import get_gemini_oauth_client


def link_gemini_oauth(timeout_sec: int = 120) -> bool:
    """로컬 루프백 HTTP 서버를 띄워 브라우저에서 Google 계정을 직접 연동한다."""
    client_id, client_secret = get_gemini_oauth_client()
    result: dict[str, str] = {}

    class _CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            if "code" in qs:
                result["code"] = qs["code"][0]
                body = "<h3>Gemini 계정 연동이 완료되었습니다. 창을 닫아주세요.</h3>".encode("utf-8")
            else:
                body = "<h3>연동이 취소되었습니다.</h3>".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return  # 콘솔 노이즈 방지

    server = http.server.HTTPServer(("127.0.0.1", 0), _CallbackHandler)
    server.timeout = timeout_sec
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
    try:
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
    tok_res = http_json("https://oauth2.googleapis.com/token", method="POST", data=tok_data)
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
