"""Codex (ChatGPT) 잔여 사용량 조회 모듈.

Codex CLI가 로컬에 저장한 인증 파일(~/.codex/auth.json)에서 토큰과 계정 ID를 읽어
WHAM 사용량 API를 호출하고 요금제별 한도 창(5시간/7일/월간)의 잔여율을 계산한다.
"""

from __future__ import annotations

import json
import pathlib
import urllib.error

from .base import ProviderStatus, QuotaMetric, format_reset, http_json


def _window_label(win: dict, default_label: str) -> str:
    """한도 창 길이(초)로 라벨을 정한다. 요금제마다 primary 가 5시간일 수도, 월간일 수도 있기 때문."""
    secs = int(win.get("limit_window_seconds") or 0)
    if secs == 18000:
        return "5시간 한도 잔여"
    if secs == 604800:
        return "7일 주간 잔여"
    if secs >= 2592000:
        return "월간 한도 잔여"
    return default_label


def _window_metrics(
    rate_limit: dict, key_prefix: str, name_prefix: str = "", detail: bool = False
) -> list[QuotaMetric]:
    """rate_limit 객체의 primary/secondary 창을 QuotaMetric 목록으로 바꾼다 (기본·모델별 한도 공통)."""
    metrics: list[QuotaMetric] = []
    for key, default_label in [
        ("primary_window", "기본 한도 잔여"),
        ("secondary_window", "주간 한도 잔여"),
    ]:
        win = rate_limit.get(key)
        if isinstance(win, dict) and win.get("used_percent") is not None:
            rem = max(0.0, min(100.0, 100.0 - float(win["used_percent"])))
            metrics.append(
                QuotaMetric(
                    name_prefix + _window_label(win, default_label),
                    rem,
                    format_reset(win.get("reset_at")),
                    key=f"{key_prefix}.{key}",
                    detail=detail,
                )
            )
    return metrics


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

        metrics = _window_metrics(usage.get("rate_limit") or {}, "codex")
        # 모델별 별도 한도(예: codex-mini 계열)는 additional_rate_limits 로 따로 내려온다.
        # 요금제에 따라 없으므로 있을 때만 세부 행으로 붙이고, 기본은 숨긴다.
        for extra in usage.get("additional_rate_limits") or []:
            if not isinstance(extra, dict):
                continue
            name = str(extra.get("limit_name") or extra.get("metered_feature") or "추가 한도")
            metrics += _window_metrics(
                extra.get("rate_limit") or {}, f"codex.{name}", name_prefix=f"{name} · ", detail=True
            )

        return ProviderStatus("Codex", True, plan=plan, account=email, metrics=metrics)
    except urllib.error.HTTPError as e:
        return ProviderStatus("Codex", False, error=f"API 오류 ({e.code}) - 재로그인 필요")
    except Exception as e:
        return ProviderStatus("Codex", False, error=f"조회 실패: {e}")
