"""카드·세부 모델 행 표시 설정(⚙ 메뉴) 저장 모듈.

쓰지 않는 서비스의 '미연동' 카드나, 관심 없는 모델별 한도 행을 숨길 수 있게
사용자의 선택을 ~/.usage_widget/display.json 에 기억한다.
"""

from __future__ import annotations

import json
import os
import pathlib

from providers import QuotaMetric
from providers.base import WIDGET_CONFIG_DIR

SETTINGS_PATH = WIDGET_CONFIG_DIR / "display.json"


class DisplaySettings:
    """숨긴 카드 목록과, 행마다 사용자가 직접 켜고 끈 기록을 들고 있는다.

    행은 '바꾼 것만' 저장한다. 그래야 서버가 새 모델 한도를 내려줘도
    기본값(기본 행은 보임, 세부 행은 숨김)이 자연스럽게 적용된다.
    """

    def __init__(self, path: pathlib.Path = SETTINGS_PATH) -> None:
        self.path = path
        self.hidden_cards: set[str] = set()
        self.metric_overrides: dict[str, bool] = {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.hidden_cards = {str(n) for n in data.get("hidden_cards") or []}
            self.metric_overrides = {
                str(k): bool(v) for k, v in (data.get("metrics") or {}).items()
            }
        except FileNotFoundError:
            pass  # 첫 실행: 기본값 그대로
        except Exception:
            # 파일이 깨졌다고 위젯이 안 뜨면 안 되므로 기본값으로 시작한다(다음 저장 때 덮어써진다).
            pass

    def card_visible(self, name: str) -> bool:
        return name not in self.hidden_cards

    def metric_visible(self, metric: QuotaMetric) -> bool:
        if not metric.key:
            return True  # 키가 없는 행은 켜고 끌 수 없으니 항상 보인다
        return self.metric_overrides.get(metric.key, not metric.detail)

    def set_card(self, name: str, visible: bool) -> None:
        if visible:
            self.hidden_cards.discard(name)
        else:
            self.hidden_cards.add(name)
        self.save()

    def set_metric(self, metric: QuotaMetric, visible: bool) -> None:
        self.metric_overrides[metric.key] = visible
        self.save()

    def save(self) -> None:
        """임시 파일 → 교체로 저장해, 쓰다가 꺼져도 설정 파일이 반쯤 깨지지 않게 한다."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(
                    {"hidden_cards": sorted(self.hidden_cards), "metrics": self.metric_overrides},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            os.replace(tmp, self.path)
        except OSError:
            pass  # 저장 실패해도 이번 실행 동안은 메모리 값으로 계속 동작한다
