# ⚙ 표시 설정 — 카드 on/off + 세부 모델별 사용량 선택

- 작성일: 2026-10-23
- 상태: 구현 완료

## 1. 요구
- 쓰지 않는 서비스 카드(예: Codex)를 숨기고 싶다.
- 각 LLM 의 세부 모델별 사용량을 골라서 보고 싶다.

## 2. 동작
위젯 상단 `⚙` → 서비스별 하위 메뉴
- `카드 표시` : 끄면 카드가 화면에서 빠진다. (조회는 계속 — 메뉴에 행 목록을 보여주기 위해)
- 행 체크 : 행 단위로 켜고 끈다. 바꾸면 재조회 없이 즉시 다시 그린다.

기본값 : **기본 행(5시간/주간)은 보임, 세부 모델 행은 숨김.** 업데이트 후에도 기존 화면이 그대로다.

| 서비스 | 세부 행 (기본 숨김) | 데이터 출처 |
|---|---|---|
| Claude | `7일 Sonnet 잔여`, `7일 Opus 잔여` | usage API `seven_day_sonnet` / `seven_day_opus` (null 이면 행 자체가 없음) |
| Codex | `<limit_name> · <창>` | WHAM `additional_rate_limits` |
| Gemini | `<그룹명> · <창>` | `retrieveUserQuotaSummary` 의 Gemini/Argon 외 그룹 (이전엔 버려짐) |

2026-10-23 실계정 확인: Gemini 응답에 `Claude and GPT models` 그룹(5시간·주간)이 있음.
Claude PRO 계정은 Sonnet/Opus 주간 값이 내려오지 않음.

## 3. 저장 구조
`~/.usage_widget/display.json`
```json
{"hidden_cards": ["Codex"], "metrics": {"claude.seven_day_opus": true}}
```
- 행은 **사용자가 바꾼 것만** 저장한다 → 서버가 새 모델 한도를 내려도 기본값이 자연히 적용된다.
- 키는 `QuotaMetric.key` (`<서비스>.<응답 키 또는 bucketId>`). 라벨이 바뀌어도 설정이 유지된다.
- 파일이 깨지면 기본값으로 시작한다.

## 4. 코드 위치
- `providers/base.py` `QuotaMetric.key / detail`
- `ui/settings.py` `DisplaySettings`
- `ui/app.py` `_open_display_menu`, `_render_cards`
- `widget.py --check` : '켜진 카드 수'만큼 그려졌는지 검사

## 5. 한계
- Gemini 그룹 안에서 같은 창(예: 5시간)의 버킷이 여러 개 오면 라벨이 겹칠 수 있다(키는 bucketId 라 설정은 안 섞임).
- 모든 카드를 숨기면 상태 표시줄에 안내 문구가 나온다(다음 갱신 시점에 표시).
