# Antigravity 미사용자의 Gemini 연동

- 작성일: 2026-10-23
- 상태: 구현 완료 (실계정 미검증 항목 있음 — 아래 §4)

## 1. 문제
Gemini 연동에 필요한 Google OAuth 클라이언트(client_id/secret)를 PC 에 설치된 `agy.exe` 에서
뽑아 쓰고 있었다. Antigravity 를 안 쓰는 PC 에서는 `계정 연동` 을 눌러도 곧바로
`Antigravity(agy) 설치본을 찾을 수 없습니다` 로 실패했다.

## 2. 결정 (사용자 선택)
**배포용 exe 에 빌드 PC 의 검증된 클라이언트를 동봉한다.**

검토했지만 고르지 않은 대안: Gemini CLI(npm) 설치본에서 클라이언트·토큰 읽기
→ "결국 Gemini CLI 는 깔아야 함" + 그 토큰으로 지금 쓰는 쿼터 API 가 되는지 실측 불가.

## 3. 구현
| 위치 | 내용 |
|---|---|
| `build.bat` | `%USERPROFILE%\.usage_widget\gemini_client.json` 이 있으면 `--add-data ...;bundled` 로 exe 에 포함. 없으면 `[WARN]` |
| `providers/gemini.py` `get_gemini_oauth_client` | 조회 순서: 사용자 캐시 → agy 설치본 추출 → **exe 동봉본**(`_MEIPASS/bundled/`) |
| 공통 | `verified: true` 표시가 있는 파일만 사용 (짝이 틀린 옛 캐시 방지) |

저장소에는 클라이언트 값이 들어가지 않는다 (GitHub Push Protection).

## 4. 리스크 / 미검증
- **배포 리스크**: Antigravity 의 OAuth 클라이언트를 제3자 exe 로 배포하는 셈이다.
  설치형 앱 클라이언트라 Google 기준 비밀값은 아니지만, Google 이 차단하면 연동이 끊길 수 있다.
  공개 배포(유료화 등) 전에 다시 검토할 것 — `docs/business/` 의 "비공식 경로" 리스크와 같은 줄기.
- **미검증**: Antigravity 를 한 번도 쓴 적 없는 Google 계정에서 `loadCodeAssist` /
  `retrieveUserQuotaSummary` 가 정상 응답하는지. (온보딩이 필요하면 별도 처리 필요)
  → agy 가 없는 PC 에서 새 exe 로 실제 연동해 보고 결과를 여기에 기록할 것.
- 동봉본은 빌드 시점 값이다. Google 이 클라이언트를 교체하면 재빌드가 필요하다.

## 5. 검증 기록 (2026-10-23)
- `python test_providers.py` → `check_gemini_falls_back_to_bundled_client` 포함 8개 OK
- `build.bat` → exe 아카이브에 `bundled\gemini_client.json` 포함 확인 (PyInstaller CArchiveReader)
