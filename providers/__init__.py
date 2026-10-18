"""AI 프로바이더 잔여 사용량 조회 및 계정 연동 패키지.

각 서비스별 모듈(claude, codex, gemini, auth)을 하나로 묶어
UI 계층에서 단순한 인터페이스로 호출할 수 있도록 공개 심볼을 노출한다.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from .auth import launch_cli_login, link_gemini_oauth
from .base import ProviderStatus, QuotaMetric, format_reset
from .claude import fetch_claude
from .codex import fetch_codex
from .gemini import fetch_gemini_and_argon

__all__ = [
    "ProviderStatus",
    "QuotaMetric",
    "fetch_all",
    "fetch_claude",
    "fetch_codex",
    "fetch_gemini_and_argon",
    "format_reset",
    "launch_cli_login",
    "link_gemini_oauth",
]


def fetch_all() -> list[ProviderStatus]:
    """Claude, Codex, Gemini, Argon의 잔여 사용량을 병렬로 빠르게 조회한다."""
    # ponytail: 3개 계정 엔드포인트를 병렬 조회한 뒤 Gemini/Argon 결과를 펼쳐 4개 카드로 반환함
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_claude = pool.submit(fetch_claude)
        f_codex = pool.submit(fetch_codex)
        f_gem_argon = pool.submit(fetch_gemini_and_argon)
        gemini_st, argon_st = f_gem_argon.result()
        return [f_claude.result(), f_codex.result(), gemini_st, argon_st]
