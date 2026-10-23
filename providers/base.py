"""AI 잔여 사용량 위젯의 공통 데이터 모델 및 유틸리티 모듈.

각 프로바이더(Claude, Codex, Gemini, Argon) 모듈이 공통으로 사용하는
데이터 구조(QuotaMetric, ProviderStatus)와 표준 라이브러리 기반 HTTP/시간 변환 함수를 정의한다.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import urllib.request
from dataclasses import dataclass, field

# 위젯 자체 연동 토큰(Gemini OAuth 등)을 기기 로컬에 보관하는 경로.
# 저장소 내부에 두면 다중 기기 동기화 시 인증 정보가 유출될 수 있어 홈 디렉터리에 격리한다.
WIDGET_CONFIG_DIR = pathlib.Path.home() / ".usage_widget"


@dataclass
class QuotaMetric:
    """개별 쿼터 창(예: 5시간 한도, 7일 주간 한도)의 잔여량 정보."""

    label: str
    remaining_percent: float  # 0.0 ~ 100.0 (잔여 비율)
    reset_text: str = ""
    # 표시 설정(⚙)에 저장되는 고유 키. 라벨은 바뀔 수 있어 키로 켜고 끈 상태를 기억한다.
    key: str = ""
    # 모델별 세부 한도처럼 '있으면 좋은' 행. 기본 화면이 복잡해지지 않게 처음엔 숨긴다.
    detail: bool = False


@dataclass
class ProviderStatus:
    """각 AI 서비스(Claude, Codex, Gemini, Argon)의 연동 상태 및 잔여 사용량."""

    name: str
    connected: bool
    plan: str = ""
    account: str = ""
    metrics: list[QuotaMetric] = field(default_factory=list)
    error: str = ""


def http_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: float = 8.0,
) -> dict:
    """외부 패키지(requests 등) 설치 없이 표준 urllib 만으로 JSON API를 호출한다."""
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def format_reset(iso_or_epoch: str | int | float | None) -> str:
    """초기화 시각을 한국어 상대 시간(예: '2시간 14분 후 초기화')으로 변환한다.

    서비스마다 초기화 시각을 ISO-8601 문자열(Claude, Gemini) 또는 Unix 타임스탬프(Codex)로
    다르게 내려주므로, 이를 하나의 함수에서 통합 처리한다.
    """
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
