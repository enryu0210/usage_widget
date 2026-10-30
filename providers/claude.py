"""Claude 잔여 사용량 조회 모듈.

Claude Code CLI가 로컬에 저장한 OAuth 토큰(~/.claude/.credentials.json)을 읽어
Anthropic OAuth 사용량 엔드포인트에서 5시간 세션 및 7일 주간 잔여율을 가져온다.
"""

from __future__ import annotations

import json
import os
import pathlib
import time
import urllib.error

from .base import ProviderStatus, QuotaMetric, format_reset, http_json, is_transient

# Claude Code CLI 의 공개 OAuth 클라이언트 ID (비밀값이 아니라 앱 식별자).
CLAUDE_CODE_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
# Claude Code 버전에 따라 토큰 발급처가 다르므로 신규 → 구 주소 순서로 시도한다.
TOKEN_URLS = (
    "https://platform.claude.com/v1/oauth/token",
    "https://console.anthropic.com/v1/oauth/token",
)
# Cloudflare 가 기본 Python-urllib UA 를 차단(403 error 1010)하므로 CLI UA 를 쓴다.
USER_AGENT = "claude-code/2.0.0"
# (응답 키, 라벨, 세부 행 여부). 모델별 주간 한도는 요금제에 따라 null 로 오거나 아예 없어서
# 기본은 숨기고, 필요한 사람만 표시 설정(⚙)에서 켠다.
USAGE_WINDOWS = (
    ("five_hour", "5시간 세션 잔여", False),
    ("seven_day", "7일 주간 잔여", False),
    ("seven_day_sonnet", "7일 Sonnet 잔여", True),
    ("seven_day_opus", "7일 Opus 잔여", True),
)
# 위 목록에 없는 새 모델 한도(예: seven_day_fable)도 업데이트 없이 보이도록 접두어로 알아본다.
WINDOW_PREFIXES = (("five_hour_", "5시간"), ("seven_day_", "7일"))


def _usage_windows(usage: dict) -> list[tuple[str, str, bool]]:
    """알려진 한도 창 + 응답에 새로 나타난 모델별 한도 창 목록을 (키, 라벨, 세부 여부)로 만든다."""
    windows = list(USAGE_WINDOWS)
    known = {key for key, _, _ in USAGE_WINDOWS}
    for key in usage:
        if key in known:
            continue
        for prefix, period in WINDOW_PREFIXES:
            if key.startswith(prefix):
                model = key[len(prefix):].replace("_", " ").title()
                # 어떤 모델이 올지 모르므로 기본 화면을 어지럽히지 않게 세부 행(기본 숨김)으로 둔다.
                windows.append((key, f"{period} {model} 잔여", True))
                break
    return windows


def _refresh_access_token(cred_path: pathlib.Path, raw: dict, oauth: dict) -> str:
    """만료된 access token 을 refresh token 으로 갱신하고 credentials 파일에 되써 넣는다.

    PC 를 재부팅하면 Claude Code 가 실행되기 전까지 아무도 토큰을 갱신하지 않아 위젯이 401 을 받는다.
    refresh token 은 갱신할 때마다 새 값으로 교체(rotation)되므로, 새 값을 파일에 저장하지 않으면
    Claude Code 쪽이 옛 refresh token 을 들고 있다가 로그아웃된다. 그래서 반드시 되써 넣는다.
    """
    body = json.dumps(
        {
            "grant_type": "refresh_token",
            "refresh_token": oauth["refreshToken"],
            "client_id": CLAUDE_CODE_CLIENT_ID,
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}

    last_error: Exception | None = None
    for url in TOKEN_URLS:
        try:
            tok = http_json(url, method="POST", headers=headers, data=body, retries=0)
            break
        except urllib.error.HTTPError as e:
            # 404/403 은 주소 문제일 수 있어 다음 주소로 넘어가고, 400/401 은 토큰 자체가 무효라 바로 중단한다.
            if e.code in (400, 401):
                raise
            last_error = e
    else:
        raise last_error or RuntimeError("토큰 갱신 실패")

    oauth["accessToken"] = tok["access_token"]
    if tok.get("refresh_token"):
        oauth["refreshToken"] = tok["refresh_token"]
    if tok.get("expires_in"):
        oauth["expiresAt"] = int(time.time() * 1000) + int(tok["expires_in"]) * 1000

    # 쓰는 도중 죽어도 Claude Code 인증 파일이 반쯤 깨진 상태로 남지 않도록 임시 파일 → 교체로 원자적 저장.
    tmp_path = cred_path.with_suffix(".widget-tmp")
    tmp_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    os.replace(tmp_path, cred_path)
    return oauth["accessToken"]


def fetch_claude(cred_path: pathlib.Path | None = None) -> ProviderStatus:
    """Claude Code 로컬 OAuth 토큰으로 5시간/7일 잔여 사용량을 조회한다."""
    cred_path = cred_path or pathlib.Path.home() / ".claude" / ".credentials.json"
    if not cred_path.exists():
        return ProviderStatus("Claude", False, error="계정 미연동 (.claude 인증 없음)")

    try:
        raw = json.loads(cred_path.read_text(encoding="utf-8"))
        oauth = raw.get("claudeAiOauth") or {}
        token = oauth.get("accessToken")
        if not token:
            return ProviderStatus("Claude", False, error="토큰 없음 (로그인 필요)")

        # 만료 1분 전부터 미리 갱신한다. Claude Code 가 켜져 있으면 스스로 먼저 갱신하므로 여기까지 오지 않는다.
        expires_at_ms = oauth.get("expiresAt") or 0
        if oauth.get("refreshToken") and expires_at_ms and expires_at_ms <= (time.time() + 60) * 1000:
            token = _refresh_access_token(cred_path, raw, oauth)

        plan = str(oauth.get("subscriptionType") or "Claude").upper()
        usage = http_json(
            "https://api.anthropic.com/api/oauth/usage",
            headers={
                "Authorization": f"Bearer {token}",
                # OAuth 토큰으로 사용량 API에 접근하기 위해 필수 요구되는 베타 헤더
                "anthropic-beta": "oauth-2025-04-20",
                "User-Agent": USER_AGENT,
            },
        )

        metrics: list[QuotaMetric] = []
        for key, label, detail in _usage_windows(usage):
            win = usage.get(key)
            if isinstance(win, dict) and win.get("utilization") is not None:
                used = float(win["utilization"])
                rem = max(0.0, min(100.0, 100.0 - used))
                metrics.append(
                    QuotaMetric(
                        label, rem, format_reset(win.get("resets_at")),
                        key=f"claude.{key}", detail=detail,
                    )
                )

        return ProviderStatus("Claude", True, plan=plan, metrics=metrics)
    except urllib.error.HTTPError as e:
        return ProviderStatus(
            "Claude", False, error=f"API 오류 ({e.code}) - 재로그인 필요", transient=is_transient(e)
        )
    except Exception as e:
        return ProviderStatus("Claude", False, error=f"조회 실패: {e}", transient=is_transient(e))
