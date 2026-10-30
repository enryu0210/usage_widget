# 자동 업데이트 + 새 모델 한도 자동 표시 (v1.0.4)

- 작성일: 2026-10-30
- 상태: v1.0.4 로 릴리스

## 1. 요구
새 모델이 나올 때마다 친구들이 exe 를 다시 받아야 하는 문제를 없앤다.
1. **자동 업데이트** — 배포용 exe 가 GitHub 최신 릴리스를 스스로 받아 교체한다.
2. **Claude 새 모델 한도 자동 표시** — 업데이트조차 필요 없게, API 가 새로 내려주는 한도는 바로 보여준다.
   (Gemini·Codex 는 이미 모르는 모델 그룹을 세부 행으로 보여주고 있었다.)

## 2. 자동 업데이트 동작 (`ui/updater.py`)
| 단계 | 내용 |
|---|---|
| 확인 시점 | exe 시작 직후 + 24시간마다 (소스 실행은 대상 아님) |
| 확인 | `api.github.com/repos/enryu0210/usage_widget/releases/latest` 의 태그 > `APP_VERSION` |
| 다운로드 | `AIUsageWidget.exe` → `AIUsageWidget.exe.new` |
| 검증 | GitHub 가 주는 asset `digest`(sha256) 와 비교. 다르거나 digest 가 없으면 설치 안 함 |
| 교체 | 실행 중 exe → `.old` 로 이름 변경, `.new` → 원래 이름 (시작 프로그램 경로 유지) |
| 재시작 | 새 exe 를 `--updated` 로 실행하고 기존 프로세스 종료. 새 프로세스는 뮤텍스가 풀릴 때까지 최대 15초 대기 |
| 정리 | 다음 실행 때 `.old` 삭제 |

실패(오프라인·권한·GitHub 장애)는 조용히 무시하고 다음 주기에 재시도한다.
`APP_VERSION` 을 깜빡하고 안 올려도, 실행 중 파일 해시가 릴리스 해시와 같으면 건너뛰므로 무한 재설치는 없다.

## 3. 릴리스 절차 (중요)
1. `ui/updater.py` 의 `APP_VERSION` 을 올린다 (예: `1.0.5`).
2. `.\build.bat` — 마지막에 Defender 검사까지 한다. `[ERROR] Defender ...` 가 뜨면 그 exe 는 올리지 말고 다시 빌드
   (v1.0.4 오탐 사고, `docs/defender-false-positive/` 참고).
3. `gh release create v1.0.5 dist\AIUsageWidget.exe --title "v1.0.5 — ..." --notes "..."`
   - 태그는 반드시 `APP_VERSION` 과 같은 번호, 첨부 파일 이름은 반드시 `AIUsageWidget.exe`.
   - 첨부 즉시 모든 친구 PC 에 하루 안에 퍼진다 → **올리기 전에 직접 한 번 실행해 볼 것.**

## 4. Claude 새 모델 한도 (`providers/claude.py` `_usage_windows`)
- 기존 4개 키(5시간/7일/Sonnet/Opus)는 그대로.
- 그 외 `five_hour_*` / `seven_day_*` 키는 자동으로 세부 행(기본 숨김, ⚙ 에서 켬).
  예: `seven_day_new_model` → `7일 New Model 잔여`
- 값이 `null` 이거나 한도 창이 아닌 키(`extra_usage` 등)는 무시.

## 4-1. Codex 모델별 사용 가능 여부 (GPT-6 Astra 등)
- 실제 WHAM 응답(2026-10-30, Pro): `"model_usage": {"gpt-6-astra": {"available": true, "available_at": null, ...}}`.
  **잔여 % 는 주지 않고 사용 가능 여부만 준다.** 별도 % 한도가 생기면 `additional_rate_limits` 로 오며 그건 기존 코드가 처리한다.
- `providers/codex.py` `_model_usage_metrics` → Codex 카드에 상태 행 (기본 표시, ⚙ 에서 끌 수 있음).
  - `GPT-6 Astra   사용 가능` (초록, 막대 없음)
  - `GPT-7 Nova    한도 도달` (빨강) + `3시간 2분 후 초기화` (`available_at` 기준)
- `QuotaMetric.status_text` 가 있으면 UI 가 % 와 막대 대신 이 문구를 그린다 (`ui/app.py`).
- `model_usage` 에 새 모델이 추가되면 업데이트 없이 자동으로 행이 생긴다.

## 5. 검증 (2026-10-30)
- `python test_providers.py` → 12개 OK (신규: `check_claude_shows_new_model_windows`, `check_updater_finds_and_installs`, `check_codex_model_usage_shows_status`)
- 실계정 Codex 조회: `GPT-6 Astra 사용 가능` 행 생성 확인, 화면 캡처로 상태 행 렌더링 확인
- 실제 GitHub API: `APP_VERSION=1.0.2` 가정 시 v1.0.3 URL + sha256 `a906...b9a` 반환, 1.0.4 에서는 None
- 뮤텍스 대기: 다른 프로세스가 점유 중이면 즉시 True, 대기 모드에선 점유 해제 직후(2.0s) 획득
- **실제 exe E2E**: `APP_VERSION=1.0.2` 로 빌드한 exe 를 격리 폴더에서 실행 →
  v1.0.3 다운로드, 해시 일치(`A906…B9A`), `.old` 생성, `.new` 잔여 없음, `--updated` 로 재시작되어 실행 중 확인
- `.venv-build\Scripts\python widget.py --check` → `WIDGET_CHECK_OK`

## 6. 리스크와 한계
- **기존 v1.0.3 사용자는 v1.0.4 를 한 번은 직접 받아야 한다** (업데이터가 v1.0.4 부터 들어감).
- **공급망 리스크**: GitHub 계정이 털리면 악성 exe 가 모든 친구 PC 에 자동 설치된다.
  sha256 은 전송 중 손상만 막고, 계정 탈취는 못 막는다 → GitHub 2FA 필수.
  더 막으려면 코드 서명 또는 공개키 서명 검증이 필요(현재 미적용).
- `Program Files` 처럼 쓰기 권한 없는 곳에 두면 업데이트가 조용히 실패한다 (Downloads·바탕화면 등은 OK).
- 업데이트 시 위젯이 예고 없이 2~3초 사라졌다 다시 뜬다.
