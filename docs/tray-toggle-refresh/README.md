# 트레이 토글 + 5분 갱신 + 시간 초과 대비

- 작성일: 2026-10-27
- 상태: 구현 완료

## 1. 요구
- `📌` 고정을 풀면 위젯이 다른 창 뒤로 묻히는데, 타이틀바가 없어 다시 앞으로 꺼낼 수단이 없다.
  → 고정 버튼을 없애고 **트레이 아이콘 클릭으로 나타내기/숨기기**.
- 1분마다 자동 갱신하면 `timed out` 이 자주 난다. → **5분 주기** + 시간 초과 대비책.

## 2. 동작
| 상황 | 결과 |
|---|---|
| 트레이 아이콘 왼쪽 클릭 (위젯 보임) | 위젯 숨김 |
| 트레이 아이콘 왼쪽 클릭 (위젯 숨김) | 위젯이 다시 맨 위에 나타남 |
| 위젯 `✕` | 숨김 (종료는 트레이 우클릭 메뉴 → `종료`) |
| 자동 갱신 | 5분마다 (`ui/theme.py` `REFRESH_INTERVAL_MS`) |

위젯은 항상 위(topmost) 고정. 가리고 싶으면 숨긴다.
Tk 의 타이틀바 없는 창은 iconify(최소화)가 안 되므로 "최소화" = withdraw(숨김).

## 3. 시간 초과 대비 (2단 방어)
1. **HTTP 재시도** — `providers/base.py` `http_json`
   - 응답 대기 8초 → 15초.
   - 일시적 실패(시간 초과·연결 끊김·429·5xx)면 2초 쉬고 1회 재시도.
   - 일회용 값을 보내는 호출(Claude 토큰 갱신 — refresh token 회전, Gemini 인가 코드 교환)은
     `retries=0`. 서버가 이미 처리했는데 재전송하면 토큰이 무효가 되기 때문.
2. **직전 값 유지** — `ui/app.py` `_keep_previous_on_transient`
   - 재시도까지 실패해도 일시적 실패(`ProviderStatus.transient`)면 카드를 빨간 오류로 바꾸지 않고
     직전 성공 값을 그대로 보여주며, 주황색 `⚠ 조회 지연 - HH:MM 이전 값 표시 중` 을 붙인다.
   - 401/403 같은 인증 실패는 사용자가 재연동해야 하므로 그대로 오류로 보여준다.

## 4. 검증
- `python test_providers.py` → `check_timeout_retries_and_keeps_previous` 포함 전부 OK
- `.venv-build\Scripts\python widget.py --check` → `WIDGET_CHECK_OK: 4 provider cards ... tray=on`
- 토글 스크립트: 클릭 1회 `withdrawn` → 2회 `normal` → `✕` `withdrawn`, topmost=1

## 5. 남은 한계
- 실제 네트워크 시간 초과 재현은 안 함 (가짜 urlopen 으로만 검증).
- 실패가 계속되면 다음 갱신까지 최대 5분 동안 이전 값이 보인다. 급하면 `↻`.
