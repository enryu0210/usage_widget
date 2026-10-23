# 사업성 검증: 고객·기술자 페르소나 리뷰

- 작성일: 2026-10-21
- 방식: /office-hours (Startup mode) + 페르소나 시뮬레이션
- 목표(사용자 답변): 수익화 / 창업 / 도구 고도화
- 제약(사용자 답변): 기능 추가 가능, 위젯 형태를 벗어나도 됨
- 상태: DRAFT

---

## 1. 결론 (먼저)

**"AI 잔여 사용량 위젯"은 그대로는 돈이 안 된다. 하지만 이 앱이 만든 도메인 지식은 돈이 되는 쪽으로 옮길 수 있다.**

| 질문 | 답 |
|---|---|
| 지금 형태로 유료 판매 가능? | **아니오.** 같은 기능의 무료 오픈소스가 Windows에만 6개 이상 있다. |
| 기능을 더 붙이면? | 개인용으로는 "보는 도구"에서 "알려주는 도구"(소진 예측·알림·ROI)로 가치가 오르지만, 여전히 무료 시장이다. |
| 돈이 되는 방향은? | **AI 구독비를 결재하는 사람(팀장·CTO)** 을 위한 시트 활용도/비용 최적화. 단, 공식 API 기반의 **다른 제품**이다. |
| 가장 큰 리스크 | 데이터를 비공식 경로로 가져온다. 무료 개인 도구일 땐 회색지대, 유료화하는 순간 약관 위반 리스크가 사업 리스크가 된다. |

---

## 2. 현재 상태 (사실만)

**기능**: Claude / Codex / Gemini / Argon 의 5시간·주간 잔여율과 초기화까지 남은 시간을 1분마다 갱신해 데스크톱 위젯 + 트레이에 표시. Windows 전용, 표준 라이브러리 기반, PyInstaller 단일 exe(~20MB).

**수요 증거** (2026-10-21 GitHub API 조회):

| 지표 | 값 |
|---|---|
| 저장소 생성 | 2026-10-18 (3일 전) |
| 릴리스 다운로드 | v1.0.0: 2, v1.0.1: 1, v1.0.2: 1 → **총 4회** |
| 스타 / 포크 | 0 / 0 |
| 최근 조회수 | 1 (고유 1) |

→ 본인 노트북·데스크톱 외 사용자 증거는 **아직 없다.** 이건 실패가 아니라 "아직 시장에 내놓지 않았다"는 뜻이다. 다만 아래 판단은 전부 실제 고객이 아니라 가상 페르소나 기반이라는 한계가 있다.

**릴리스 3개가 모두 "연동 오류 수정"** 이었다는 점도 기록해 둔다(아래 §5-2 참고).

---

## 3. 시장 현황 (2026-10 웹 검색)

| 플랫폼 | 제품 | 가격 | 지원 범위 |
|---|---|---|---|
| macOS | [CodexBar](https://www.mintlify.com/steipete/codexbar) | 무료 OSS | Claude, Codex, Gemini, Cursor, Copilot 등 15+ |
| Windows | [TaskbarQuota](https://github.com/zioder/TaskbarQuota/wiki) | 무료 | 포커스된 터미널의 도구를 자동 감지해 해당 쿼터 표시 |
| Windows | [AIUsage.NET](https://wingetgui.com/apps/LuigiElleBalotta-AIUsageNET) | 무료, winget 등록 | Claude, Codex, Cursor, Copilot, **Antigravity**, OpenRouter 등 |
| Windows | [OpenTokenUsage](https://wingetly.io/apps/power-user-z/open-token-usage) | 무료, winget 등록 | Claude, Codex, Copilot, Cursor, Gemini |
| Windows | [ClaudTray](https://wingetly.io/apps/victor-magne/claud-tray) | 무료, winget 등록 | Claude, Copilot, Codex, **Antigravity** |
| Windows | [Quotify](https://awesome.ecosyste.ms/projects/github.com%2Fzuoxinyu%2Fquotify), [claude-usage-tray](https://github.com/ksmaster03/claude-usage-tray) | 무료 | Claude 중심 |

**판정**: "잔여량 표시"는 이미 commodity다. 가격이 0원으로 수렴했고, 차별점으로 생각할 만한 Antigravity/Argon 지원도 이미 2곳이 한다. 이 시장에서 경쟁 상대는 다른 위젯이 아니라 **터미널에서 `/usage` 한 번 치는 습관**이다.

---

## 4. 고객 페르소나

### 고객 A. "한도에 막히는 1인 개발자" (현재 앱의 타깃)

- 프리랜서 풀스택 개발자. Claude Max 5x + ChatGPT Plus + Gemini 구독, 월 약 25만 원.
- 하루 6~8시간 AI 코딩. 주 2~3회 Claude 5시간 한도에 작업 도중 막힌다.
- **현재 해결책**: 막히면 Codex로 넘어가고, 가끔 `/usage` 를 쳐본다.

> "숫자 보는 건 좋은데, 막히고 나서 위젯 보면 의미가 없잖아요.
> 제가 원하는 건 **'지금 페이스면 40분 뒤에 막힌다'** 는 경고, 그리고 막히면 어디로 넘어가면 되는지예요.
> 돈이요? 무료 앱이 여섯 개인데요. 월 3천 원도 고민할 것 같아요."

- **지불 의사**: 매우 낮음.
- **진짜 원하는 것**: 소진 예측, 임계치 알림, "다음엔 어느 도구로" 추천.
- **이 앱에 대한 평가**: 쓸 만하다. 근데 바꿀 이유가 없다.

### 고객 B. "AI 구독비를 결재하는 CTO" (돈을 낼 사람)

- 직원 20명 스타트업 CTO. 개발자 12명에게 Claude Team/Max + ChatGPT Business 시트 지급, 월 AI 비용 약 600만 원.
- 매달 "Max로 올려달라"는 요청과 "이 시트 쓰긴 하나?" 하는 의문이 동시에 있다.
- **현재 해결책**: 각 콘솔 관리자 화면을 따로 열어 보고 스프레드시트로 정리하거나, 그냥 감으로 정한다.

> "개인 PC 위젯엔 관심 없어요. 제가 알고 싶은 건 **누가 시트를 놀리고 있고, 누가 매일 한도에 막히는지**,
> 그래서 누구를 Pro로 내리고 누구를 Max로 올릴지예요. 그걸로 한 달에 100만 원만 아껴도 바로 결제합니다.
> 그리고 직원 PC에서 다른 앱 인증 파일을 읽는 exe는 보안팀이 절대 승인 안 해요."

- **지불 의사**: 높음 (절감액의 일부라면).
- **조건**: 공식 관리자 API, 웹 대시보드, SSO, 직원 PC 설치 없음.
- **이 앱에 대한 평가**: 이 제품은 아니다. 근데 이 문제를 아는 사람이 만든 제품이면 관심 있다.

### 고객 C. "Claude Code를 안 쓰는 AI 헤비유저"

- 서비스 기획자. claude.ai 웹 + ChatGPT 앱 + Gemini 앱을 하루 종일 쓴다. 터미널은 안 쓴다.
- **이 앱을 설치하면**: 전부 "계정 미연동"이 뜬다. 앱이 `~/.claude/.credentials.json`, `~/.codex/auth.json`, agy 설치본 같은 **CLI 흔적**에 의존하기 때문.

> "깔았는데 아무것도 안 나와요. 로그인 버튼 눌렀더니 터미널이 떠요."

- **판정**: 시장은 개발자보다 훨씬 크지만, 현재 기술 구조로는 닿을 수 없다. 이쪽은 브라우저 확장 같은 완전히 다른 구조가 필요하다.

---

## 5. 기술자 페르소나

### 기술자 1. 보안 엔지니어

> "개인이 자기 PC에서 쓰는 건 말리지 않겠습니다. 근데 회사 배포는 불가예요."

근거 (코드 기준):
- **서명 없는 exe** + **다른 앱의 인증 파일 읽기/쓰기** + **바이너리에서 OAuth secret 추출**(`providers/gemini.py` `get_gemini_oauth_client`, `GOCSPX-` 정규식으로 agy.exe 스캔). 이 세 가지 조합은 EDR이 인포스틸러로 탐지하는 패턴과 거의 같다. 사용자가 늘수록 백신 오탐 신고가 늘어난다.
- **토큰 갱신 경합 (미검증 리스크)**: `providers/claude.py` `_refresh_access_token` 은 Claude Code 와 같은 credentials 파일을 갱신·덮어쓴다. 원자적 교체는 하지만 **잠금은 없다.** 위젯과 Claude Code 가 거의 동시에 갱신하면 refresh token 회전(rotation) 때문에 한쪽이 무효 토큰을 들고 있게 되고, 그러면 **사용자가 Claude Code에서 로그아웃된다.** 무료 도구면 "가끔 재로그인"으로 끝나지만, 유료 제품이면 CS 티켓이다.
- 저장소에 secret을 넣지 않고 홈 디렉터리에 격리한 점(`WIDGET_CONFIG_DIR`)은 좋은 판단이다.

### 기술자 2. 플랫폼 / API 엔지니어

> "이 앱의 데이터 소스는 전부 남의 집 뒷문이에요. 문이 언제 잠길지 모릅니다."

| 서비스 | 호출 대상 | 공식 여부 | 흉내 내는 것 |
|---|---|---|---|
| Claude | `api.anthropic.com/api/oauth/usage` | 비공개 | Claude Code client ID + UA `claude-code/2.0.0` |
| Codex | `chatgpt.com/backend-api/wham/usage` | 비공개 | UA `codex_cli_rs/0.1.0` |
| Gemini/Argon | `daily-cloudcode-pa.googleapis.com/v1internal:*` | 내부(internal) | agy.exe 에서 뽑은 OAuth client |

- **약관**: Anthropic은 2026-02-19 문서를 개정해 Free/Pro/Max 구독 OAuth 토큰을 Claude Code·claude.ai 외 제품에서 쓰는 것을 소비자 약관 위반으로 명시했다 ([WinBuzzer](https://winbuzzer.com/2026/02/19/anthropic-bans-claude-subscription-oauth-in-third-party-apps-xcxwbn/), [GIGAZINE](https://gigazine.net/gsc_news/en/20260220-anthropic-third-party-block)). 단속 대상은 주로 추론(inference) 우회지만, 문구만 보면 "사용량 조회"도 걸린다. 경쟁 제품들도 같은 방식이라 지금은 묵인 상태에 가깝다.
- **무료 개인 도구 vs 유료 제품의 차이**: 무료면 "최악의 경우 엔드포인트 막히고 끝". 유료면 "고객 계정 정지 시 책임 + 상업적 이용 주장 불가".
- **유지보수 비용**: 3일 동안 릴리스 3번이 전부 연동 수정이었다. 비공개 API 의존 구조에서는 이 비율이 계속 간다.
- **공식 경로 대안**:
  - Claude: `~/.claude/projects/**/*.jsonl` 로컬 로그 파싱(ccusage 방식). 토큰을 아예 안 쓴다. 대신 "잔여 %"가 아니라 "사용 토큰/추정 비용"이다.
  - 조직용: Anthropic Admin API(usage/cost report), OpenAI Organization Usage API. **공식이고 안정적이다. 단 개인 구독은 못 본다.**
  - 결론: **개인 구독 잔여 %는 영원히 비공식일 수밖에 없다.** 이걸 해자로 삼으면 안 된다.

### 기술자 3. 아키텍트

> "코드 구조는 확장하기 좋게 돼 있어요. 근데 지금 앱엔 '기억'이 없어요."

- **좋은 점**: `providers/` 가 UI와 완전히 분리돼 있고 `ProviderStatus`/`QuotaMetric` 데이터 모델이 공통이다. `python -m providers` CLI 진입점도 이미 있다. UI를 바꾸거나 CLI/로컬 서버로 꺼내기 쉽다.
- **빠진 것**: 1분마다 조회하고 **버린다.** 히스토리가 없으니 예측·추세·ROI 같은 "돈 되는 기능"이 전부 불가능하다. 첫 단추는 스냅샷을 sqlite(이미 `sqlite3` 사용 중)에 쌓는 것.
- **플랫폼**: macOS는 CodexBar가 장악. Windows 집중은 맞는 판단이다. 배포는 winget 등록이 무료이고 경쟁작들도 다 거기 있다.

---

## 6. 가설 판정표

| 가설 | 판정 | 근거 |
|---|---|---|
| 잔여량 위젯을 유료로 팔 수 있다 | ✗ | 무료 경쟁작 6+, 고객 A 지불 의사 없음 |
| 한국어/Windows 특화가 차별점이다 | △ | 한국어는 진입장벽이 아님. Windows 경쟁작 다수 |
| Argon/Antigravity 지원이 차별점이다 | △ | AIUsage.NET, ClaudTray도 지원 |
| "보여주기"에서 "알려주기"(예측·알림)로 가면 개인 가치가 오른다 | ○ | 고객 A의 핵심 요구. 단 여전히 무료 시장 |
| 팀 시트 최적화는 돈이 된다 | ○ (미검증) | 고객 B는 가상. 실제 인터뷰 필요 |
| 지금 구조로 비개발자 시장에 간다 | ✗ | CLI 흔적 의존, 고객 C 연동 불가 |

---

## 7. 전제 (Premises)

1. 잔여량 **표시** 자체로는 돈을 받을 수 없다.
2. 개인 구독 데이터는 비공식 경로뿐이라, 이걸로 유료화하면 법적·운영 리스크가 수익보다 크다.
3. 돈을 내는 고객은 "한도에 막히는 개인"이 아니라 **"AI 구독비를 결재하는 사람"** 이다.

---

## 8. 접근안

### A. 개인 도구 고도화 (최소, 무료 OSS 유지)
- 내용: 스냅샷 히스토리 적재 → 소진 예측("이 페이스면 40분 뒤 한도") → 임계치 토스트 알림(20%, 5%) → winget 등록.
- 규모: S / 리스크: Low
- 장점: 기존 `providers/`, `sqlite3`, 트레이를 그대로 재사용. 본인 생산성에 바로 효과.
- 단점: 매출 0. 경쟁작과 차이는 작다.

### B. 팀용 "AI 시트 최적화" 웹 서비스 (이상, 수익 모델)
- 내용: Anthropic Admin API / OpenAI Organization Usage API 를 연결하는 웹 대시보드. 시트별 활용도, 다운/업그레이드 추천, "이번 달 절감 가능액".
- 규모: L~XL / 리스크: Med (시장), Low (약관, 공식 API라서)
- 장점: 결재권자가 고객. 절감액 기반 가격 책정 가능. 약관 리스크 없음.
- 단점: 현재 코드 재사용 거의 없음(도메인 지식만). 영업·보안 심사 필요. 기존 SaaS 지출 관리 툴과 경쟁.

### C. "구독 ROI 코치" (측면, A 위에 얹기)
- 내용: A의 히스토리로 월간 리포트. "이번 달 Claude Max 주간 한도 평균 사용률 23% → Pro로 내리면 월 약 X원 절약" 같은 개인 판단 근거 제공.
- 규모: M / 리스크: Low~Med
- 장점: 경쟁작이 안 하는 각도. "돈을 아껴준다"는 메시지가 B로 가는 다리. 블로그/커뮤니티 공유 소재.
- 단점: 개인은 여전히 돈을 잘 안 낸다. 비공식 데이터 리스크는 A와 같다.

### 권장
**A → C 를 개인 도구로 2~4주 굴리면서, B는 코드 한 줄 쓰기 전에 인터뷰부터.**
A·C는 싸고 본인에게 바로 쓸모 있다. B는 돈이 되지만 비싸고, 고객 B가 실제로 존재하는지 아직 모른다.

---

## 9. 먼저 고칠 것 (사업 방향과 무관)

- **Claude 토큰 갱신 경합** (§5 기술자 1): 지금도 실사용자가 로그아웃당할 수 있는 경로. 갱신 직전 파일을 다시 읽어 Claude Code가 이미 갱신했는지 확인하거나, 갱신 자체를 하지 않고 "Claude Code를 한 번 실행하세요" 안내로 바꾸는 선택지가 있다. **실제로 재현되는지는 미검증.**

---

## 10. 성공 기준

- A: 2주간 "알림 없이 한도에 막힌 횟수" 0회. winget 등록 후 본인 외 다운로드 20회.
- C: 본인 구독에 대해 리포트를 근거로 실제 플랜 변경(또는 유지) 결정 1회.
- B 착수 조건: 결재권자 5명 인터뷰 중 3명 이상이 "누가 얼마나 쓰는지 모른다 + 알면 시트를 조정하겠다", 그리고 1명 이상이 사전 결제/파일럿 의사.

## 11. 열린 질문

- 고객 B 같은 사람을 실제로 5명 알고 있는가? (모르면 B는 보류가 맞다)
- Anthropic/OpenAI 관리자 API가 시트별(사용자별) 데이터를 어디까지 주는가? B의 기술 타당성은 여기서 갈린다.
- 개인 도구를 계속 공개 배포할 것인가, 본인용으로 둘 것인가? (공개 시 §5-2 약관 리스크를 사용자에게 고지해야 한다)

## 12. 이번 주 할 일 (Assignment)

**AI 시트 비용을 결재하는 사람(팀장·CTO·대표) 5명에게 메시지 하나 보내기:**
"지난달 회사 AI 구독비 얼마였어요? 누가 얼마나 쓰는지 알아요?"

답을 그대로 이 문서 아래에 붙인다. 3명 이상이 "모른다, 알고 싶다"면 B 설계를 시작하고, 아니면 A·C에 집중한다.

---

## 출처
- [CodexBar](https://www.mintlify.com/steipete/codexbar)
- [TaskbarQuota](https://github.com/zioder/TaskbarQuota/wiki)
- [AIUsage.NET](https://wingetgui.com/apps/LuigiElleBalotta-AIUsageNET)
- [OpenTokenUsage](https://wingetly.io/apps/power-user-z/open-token-usage)
- [ClaudTray](https://wingetly.io/apps/victor-magne/claud-tray)
- [Quotify](https://awesome.ecosyste.ms/projects/github.com%2Fzuoxinyu%2Fquotify)
- [claude-usage-tray](https://github.com/ksmaster03/claude-usage-tray)
- [Anthropic Bans Claude Subscription OAuth in Third-Party Apps (WinBuzzer)](https://winbuzzer.com/2026/02/19/anthropic-bans-claude-subscription-oauth-in-third-party-apps-xcxwbn/)
- [Anthropic officially bans third-party subscription authentication (GIGAZINE)](https://gigazine.net/gsc_news/en/20260220-anthropic-third-party-block)
