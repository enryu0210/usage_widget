"""Claude 잔여 사용량 조회 모듈.

Claude Code CLI가 로컬에 저장한 OAuth 토큰(~/.claude/.credentials.json)을 읽어
Anthropic OAuth 사용량 엔드포인트에서 5시간 세션 및 7일 주간 잔여율을 가져온다.
"""

from __future__ import annotations

import json
import pathlib
import urllib.error

from .base import ProviderStatus, QuotaMetric, format_reset, http_json


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
        usage = http_json(
            "https://api.anthropic.com/api/oauth/usage",
            headers={
                "Authorization": f"Bearer {token}",
                # OAuth 토큰으로 사용량 API에 접근하기 위해 필수 요구되는 베타 헤더
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
                metrics.append(QuotaMetric(label, rem, format_reset(win.get("resets_at"))))

        return ProviderStatus("Claude", True, plan=plan, metrics=metrics)
    except urllib.error.HTTPError as e:
        return ProviderStatus("Claude", False, error=f"API 오류 ({e.code}) - 재로그인 필요")
    except Exception as e:
        return ProviderStatus("Claude", False, error=f"조회 실패: {e}")
