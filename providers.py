"""Claude, Codex, Gemini 잔여 사용량 조회 및 계정 연동 모듈.

외부 패키지 의존성 없이 Python 표준 라이브러리만 사용하여
각 CLI/IDE가 로컬에 저장한 OAuth 인증 정보를 재사용하거나,
미연동 시 브라우저/CLI 로그인을 통해 계정을 연동한다.
"""

from __future__ import annotations

import base64
import datetime as dt
import http.server
import json
import os
import pathlib
import re
import sqlite3
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass, field

# 위젯 자체 연동 토큰(Gemini OAuth 등)을 기기 로컬에 보관하는 경로.
# 저장소 내부에 두면 다중 기기 동기화 시 인증 정보가 유출될 수 있어 홈 디렉터리에 격리한다.
WIDGET_CONFIG_DIR = pathlib.Path.home() / ".usage_widget"


def _get_gemini_oauth_client() -> tuple[str, str]:
    """로컬에 설치된 Antigravity 바이너리 또는 캐시 파일에서 OAuth 클라이언트 정보를 동적으로 읽는다.

    코드 저장소에 OAuth 클라이언트 식별자를 하드코딩하면 GitHub Push Protection에 차단되므로,
    현재 기기의 설치본에서 최초 1회 추출하여 ~/.usage_widget/gemini_client.json 에 캐싱한다.
    """
    cache_file = WIDGET_CONFIG_DIR / "gemini_client.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if data.get("client_id") and data.get("client_secret"):
                return str(data["client_id"]), str(data["client_secret"])
        except Exception:
            pass

    local_app = os.environ.get("LOCALAPPDATA", "")
    exe_path = pathlib.Path(local_app) / "agy" / "bin" / "agy.exe"
    if exe_path.exists():
        raw = exe_path.read_bytes()
        ids = re.findall(b"107[0-9]{10}-[a-z0-9]{32}\\.apps\\.googleusercontent\\.com", raw)
        secrets = re.findall(b"GOCSPX-[A-Za-z0-9_\\-]{28}", raw)
        if ids and secrets:
            cid = ids[0].decode("ascii")
            csec = secrets[0].decode("ascii")
            WIDGET_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(
                json.dumps({"client_id": cid, "client_secret": csec}, indent=2),
                encoding="utf-8",
            )
            return cid, csec

    raise RuntimeError("로컬 Antigravity 설치본에서 OAuth 클라이언트 정보를 찾을 수 없습니다.")


@dataclass
class QuotaMetric:
    """개별 쿼터 창(예: 5시간 한도, 주간 한도)의 잔여량 정보."""

    label: str
    remaining_percent: float  # 0.0 ~ 100.0 (잔여 비율)
    reset_text: str = ""


@dataclass
class ProviderStatus:
    """각 AI 서비스(Claude, Codex, Gemini)의 연동 상태 및 잔여 사용량."""

    name: str
    connected: bool
    plan: str = ""
    account: str = ""
    metrics: list[QuotaMetric] = field(default_factory=list)
    error: str = ""


def _http_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: float = 8.0,
) -> dict:
    """표준 urllib 만으로 JSON API를 호출한다."""
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _format_reset(iso_or_epoch: str | int | float | None) -> str:
    """초기화 시각을 한국어 상대 시간(예: '2시간 14분 후 초기화')으로 변환한다."""
    if not iso_or_epoch:
        return ""
    try:
        if isinstance(iso_or_epoch, (int, float)):
            target = dt.datetime.fromtimestamp(float(iso_or_epoch), tz=dt.timezone.utc)
        else:
            s = str(iso_or_epoch).replace("Z", "+00:00")
            target = dt.datetime.fromisoformat(s)
        now = dt.datetime.now(dt.timezone.utc)
        diff = int((target - now).total_seconds())
        if diff <= 0:
            return "곧 초기화"
        days, rem = divmod(diff, 86400)
        hours, rem = divmod(rem, 3600)
        minutes = rem // 60
        if days > 0:
            return f"{days}일 {hours}시간 후 초기화"
        if hours > 0:
            return f"{hours}시간 {minutes}분 후 초기화"
        return f"{minutes}분 후 초기화"
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# 1. Claude ( ~/.claude/.credentials.json )
# ---------------------------------------------------------------------------
def fetch_claude() -> ProviderStatus:
    """Claude Code 로컬 OAuth 토큰으로 5시간/7일 잔여 사용량을 조회한다."""
    cred_path = pathlib.Path.home() / ".claude" / ".credentials.json"
    if not cred_path.exists():
        return ProviderStatus("Claude", False, error="계정 미연동 (.claude 인증 없음)")

    try:
        raw = json.loads(cred_path.read_text(encoding="utf-8"))
        oauth = raw.get("claudeAiOauth") or {}
        token = oauth.get("accessToken")
        if not token:
            return ProviderStatus("Claude", False, error="토큰 없음 (로그인 필요)")

        plan = str(oauth.get("subscriptionType") or "Claude").upper()
        usage = _http_json(
            "https://api.anthropic.com/api/oauth/usage",
            headers={
                "Authorization": f"Bearer {token}",
                "anthropic-beta": "oauth-2025-04-20",
                "User-Agent": "claude-code/2.0.0",
            },
        )

        metrics: list[QuotaMetric] = []
        for key, label in [("five_hour", "5시간 세션 잔여"), ("seven_day", "7일 주간 잔여")]:
            win = usage.get(key)
            if isinstance(win, dict) and win.get("utilization") is not None:
                used = float(win["utilization"])
                rem = max(0.0, min(100.0, 100.0 - used))
                metrics.append(QuotaMetric(label, rem, _format_reset(win.get("resets_at"))))

        return ProviderStatus("Claude", True, plan=plan, metrics=metrics)
    except urllib.error.HTTPError as e:
        return ProviderStatus("Claude", False, error=f"API 오류 ({e.code}) - 재로그인 필요")
    except Exception as e:
        return ProviderStatus("Claude", False, error=f"조회 실패: {e}")


# ---------------------------------------------------------------------------
# 2. Codex ( ~/.codex/auth.json )
# ---------------------------------------------------------------------------
def fetch_codex() -> ProviderStatus:
    """Codex CLI 로컬 OAuth 토큰으로 WHAM 사용량 API를 호출해 잔여량을 계산한다."""
    auth_path = pathlib.Path.home() / ".codex" / "auth.json"
    if not auth_path.exists():
        return ProviderStatus("Codex", False, error="계정 미연동 (.codex 인증 없음)")

    try:
        raw = json.loads(auth_path.read_text(encoding="utf-8"))
        tokens = raw.get("tokens") or {}
        access_token = tokens.get("access_token")
        account_id = tokens.get("account_id")
        if not access_token:
            return ProviderStatus("Codex", False, error="토큰 없음 (로그인 필요)")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "codex_cli_rs/0.1.0",
        }
        if account_id:
            headers["ChatGPT-Account-Id"] = str(account_id)

        usage = _http_json("https://chatgpt.com/backend-api/wham/usage", headers=headers)
        plan = str(usage.get("plan_type") or "codex").upper()
        email = str(usage.get("email") or "")

        rl = usage.get("rate_limit") or {}
        metrics: list[QuotaMetric] = []

        for key, default_label in [("primary_window", "기본 한도 잔여"), ("secondary_window", "주간 한도 잔여")]:
            win = rl.get(key)
            if isinstance(win, dict) and win.get("used_percent") is not None:
                secs = int(win.get("limit_window_seconds") or 0)
                if secs == 18000:
                    label = "5시간 한도 잔여"
                elif secs == 604800:
                    label = "7일 주간 잔여"
                elif secs >= 2592000:
                    label = "월간 한도 잔여"
                else:
                    label = default_label
                used = float(win["used_percent"])
                rem = max(0.0, min(100.0, 100.0 - used))
                metrics.append(QuotaMetric(label, rem, _format_reset(win.get("reset_at"))))

        return ProviderStatus("Codex", True, plan=plan, account=email, metrics=metrics)
    except urllib.error.HTTPError as e:
        return ProviderStatus("Codex", False, error=f"API 오류 ({e.code}) - 재로그인 필요")
    except Exception as e:
        return ProviderStatus("Codex", False, error=f"조회 실패: {e}")


# ---------------------------------------------------------------------------
# 3. Gemini ( Antigravity state.vscdb 또는 ~/.usage_widget/gemini_oauth.json )
# ---------------------------------------------------------------------------
def _extract_antigravity_refresh_token() -> str | None:
    """Antigravity IDE의 로컬 SQLite(state.vscdb)에서 Google OAuth refresh_token을 추출한다."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    db_path = pathlib.Path(appdata) / "Antigravity" / "User" / "globalStorage" / "state.vscdb"
    if not db_path.exists():
        return None
    try:
        # IDE가 실행 중일 때도 락 충돌이 나지 않도록 읽기 전용 URI 모드로 연다.
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
        try:
            row = conn.execute(
                "SELECT value FROM ItemTable WHERE key = 'antigravityUnifiedStateSync.oauthToken'"
            ).fetchone()
        finally:
            conn.close()
        if not row or not row[0]:
            return None
        outer = base64.b64decode(row[0])
        for chunk in re.findall(b"[A-Za-z0-9_\\-\\./:=+]{16,}", outer):
            try:
                inner = base64.b64decode(chunk.decode("ascii", "ignore"))
                matches = re.findall(b"1//[A-Za-z0-9_\\-]+", inner)
                if matches:
                    return matches[0].decode("ascii")
            except Exception:
                continue
    except Exception:
        return None
    return None


def _get_gemini_refresh_token() -> str | None:
    """위젯 전용 저장소 -> Antigravity IDE 순서로 Gemini refresh_token을 찾는다."""
    saved = WIDGET_CONFIG_DIR / "gemini_oauth.json"
    if saved.exists():
        try:
            tok = json.loads(saved.read_text(encoding="utf-8")).get("refresh_token")
            if tok:
                return str(tok)
        except Exception:
            pass
    return _extract_antigravity_refresh_token()


def fetch_gemini() -> ProviderStatus:
    """Google Code Assist (Antigravity) API를 통해 Gemini 모델 잔여 쿼터를 조회한다."""
    refresh_token = _get_gemini_refresh_token()
    if not refresh_token:
        return ProviderStatus("Gemini", False, error="계정 미연동 ([연동] 클릭)")

    try:
        client_id, client_secret = _get_gemini_oauth_client()
        tok_Form = urllib.parse.urlencode(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")
        tok_res = _http_json("https://oauth2.googleapis.com/token", method="POST", data=tok_Form)
        access_token = tok_res["access_token"]

        ca_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            # 개인용 Google AI / Code Assist 쿼터 엔드포인트는 Antigravity UA를 요구한다.
            "User-Agent": "antigravity/1.20.3 windows/amd64",
        }

        load_res = _http_json(
            "https://daily-cloudcode-pa.googleapis.com/v1internal:loadCodeAssist",
            method="POST",
            headers=ca_headers,
            data=json.dumps(
                {
                    "metadata": {
                        "ideType": "ANTIGRAVITY",
                        "platform": "WINDOWS_AMD64",
                        "pluginType": "GEMINI",
                    }
                }
            ).encode("utf-8"),
        )

        paid_tier = load_res.get("paidTier") or {}
        current_tier = load_res.get("currentTier") or {}
        plan = str(paid_tier.get("name") or current_tier.get("name") or "Gemini").upper()
        project = load_res.get("cloudaicompanionProject") or "aicode-consumers"

        quota_res = _http_json(
            "https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuota",
            method="POST",
            headers=ca_headers,
            data=json.dumps({"project": project}).encode("utf-8"),
        )

        # Gemini 계열 모델들의 최저 잔여율과 초기화 시각을 집계한다.
        gemini_buckets = [
            b
            for b in (quota_res.get("buckets") or [])
            if str(b.get("modelId") or "").startswith("gemini-")
            and b.get("remainingFraction") is not None
        ]
        metrics: list[QuotaMetric] = []
        if gemini_buckets:
            # 가장 많이 소진된(잔여율이 가장 낮은) 메인 Gemini 버킷을 기준으로 표시한다.
            primary = min(gemini_buckets, key=lambda b: float(b["remainingFraction"]))
            rem = max(0.0, min(100.0, float(primary["remainingFraction"]) * 100.0))
            metrics.append(
                QuotaMetric("5시간 모델 쿼터 잔여", rem, _format_reset(primary.get("resetTime")))
            )

        return ProviderStatus("Gemini", True, plan=plan, metrics=metrics)
    except urllib.error.HTTPError as e:
        return ProviderStatus("Gemini", False, error=f"API 오류 ({e.code}) - 재연동 필요")
    except Exception as e:
        return ProviderStatus("Gemini", False, error=f"조회 실패: {e}")


# ---------------------------------------------------------------------------
# 계정 연동 액션 (OAuth 브라우저 로그인 / CLI 로그인 호출)
# ---------------------------------------------------------------------------
def link_gemini_oauth(timeout_sec: int = 120) -> bool:
    """로컬 루프백 HTTP 서버를 띄워 브라우저에서 Google 계정을 직접 연동한다."""
    client_id, client_secret = _get_gemini_oauth_client()
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
            "scope": "https://www.googleapis.com/auth/cloud-platform https://www.googleapis.com/auth/userinfo.email",
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
    tok_res = _http_json("https://oauth2.googleapis.com/token", method="POST", data=tok_data)
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


def fetch_all() -> list[ProviderStatus]:
    """세 서비스의 잔여 사용량을 병렬로 빠르게 조회한다."""
    from concurrent.futures import ThreadPoolExecutor

    # ponytail: 3개 고정 프로바이더만 조회하므로 단순 스레드풀(max_workers=3)로 충분함
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(fn) for fn in (fetch_claude, fetch_codex, fetch_gemini)]
        return [f.result() for f in futures]


if __name__ == "__main__":
    # Ponytail 단일 검증 루틴: 시간 포맷터 및 실제 프로바이더 조회 동작 검증
    assert _format_reset(dt.datetime.now(dt.timezone.utc).timestamp() + 3700).startswith("1시간")
    statuses = fetch_all()
    assert len(statuses) == 3
    for st in statuses:
        print(f"[{st.name}] connected={st.connected} plan={st.plan} error={st.error}")
        for m in st.metrics:
            print(f"  - {m.label}: {m.remaining_percent:.1f}% ({m.reset_text})")
