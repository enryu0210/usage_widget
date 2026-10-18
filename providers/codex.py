"""Codex (ChatGPT) 잔여 사용량 조회 모듈.

Codex CLI가 로컬에 저장한 인증 파일(~/.codex/auth.json)에서 토큰과 계정 ID를 읽어
WHAM 사용량 API를 호출하고 요금제별 한도 창(5시간/7일/월간)의 잔여율을 계산한다.
"""

from __future__ import annotations

import json
import pathlib
import urllib.error

from .base import ProviderStatus, QuotaMetric, format_reset, http_json


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
        # 다중 워크스페이스/계정 환경에서 정확한 구독 플랜을 조회하기 위해 계정 ID 헤더를 함께 보낸다.
        if account_id:
            headers["ChatGPT-Account-Id"] = str(account_id)

        usage = http_json("https://chatgpt.com/backend-api/wham/usage", headers=headers)
        plan = str(usage.get("plan_type") or "codex").upper()
        email = str(usage.get("email") or "")

        rl = usage.get("rate_limit") or {}
        metrics: list[QuotaMetric] = []

        for key, default_label in [
            ("primary_window", "기본 한도 잔여"),
            ("secondary_window", "주간 한도 잔여"),
        ]:
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
                metrics.append(QuotaMetric(label, rem, format_reset(win.get("reset_at"))))

        return ProviderStatus("Codex", True, plan=plan, account=email, metrics=metrics)
    except urllib.error.HTTPError as e:
        return ProviderStatus("Codex", False, error=f"API 오류 ({e.code}) - 재로그인 필요")
    except Exception as e:
        return ProviderStatus("Codex", False, error=f"조회 실패: {e}")
