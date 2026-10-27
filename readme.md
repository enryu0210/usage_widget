# AI 잔여 사용량 확인 Windows 위젯

Claude, Codex, Gemini 및 Argon(`Gemini 4 Argon`) 계정을 연동하여 각 서비스의 실시간 잔여 사용량(%)과 초기화까지 남은 시간을 바탕화면에 띄워주는 경량 Windows 위젯입니다.

## 다운로드
[Releases](https://github.com/enryu0210/usage_widget/releases/latest) 에서 `AIUsageWidget.exe` 를 내려받아 실행하면 됩니다(파이썬 불필요).
처음 실행 시 시작 프로그램에 자동 등록되고 트레이에 아이콘이 뜹니다. 서명되지 않은 exe 라 SmartScreen 경고가 뜨면 **추가 정보 → 실행** 을 누르세요.

## 프로젝트 폴더 구조
```text
usage_widget/
├── providers/                # 서비스별 잔여 사용량 조회 및 인증 연동 패키지
│   ├── __init__.py           # 패키지 공개 API 및 병렬 조회(fetch_all)
│   ├── __main__.py           # 단독 실행 검증 진입점 (python -m providers)
│   ├── base.py               # 공통 데이터 구조(QuotaMetric, ProviderStatus) 및 HTTP/시간 유틸
│   ├── claude.py             # Claude 로컬 토큰 조회 및 사용량 API 호출
│   ├── codex.py              # Codex 로컬 토큰 조회 및 WHAM 사용량 API 호출
│   ├── gemini.py             # Gemini & Argon 토큰 탐색 및 통합 쿼터 요약 분리 조회
│   └── auth.py               # 계정 연동 액션 (브라우저 Google OAuth, CLI 로그인 호출)
├── ui/                       # 데스크톱 위젯 UI 패키지
│   ├── __init__.py
│   ├── theme.py              # 다크 테마 색상 팔레트 및 잔여량 경고 색상 계산
│   ├── app.py                # UsageWidgetApp 플로팅 위젯 창 및 카드 렌더링
│   ├── tray.py               # 시스템 트레이 아이콘(pystray) 및 작업 표시줄 노출 처리
│   ├── settings.py           # ⚙ 표시 설정(카드 on/off, 세부 모델 행) 저장
│   └── autostart.py          # Windows 시작 프로그램 등록(HKCU Run 레지스트리)
├── assets/
│   ├── icon.ico              # 앱/트레이 로고
│   └── make_icon.py          # 로고 생성 스크립트 (Pillow)
├── widget.py                 # 위젯 실행 진입점 (main, 중복 실행 방지, --check 자가 검증)
├── test_providers.py         # 토큰 갱신·연동 로직 오프라인 검증 (실제 계정 미사용)
├── build.bat                 # exe 패키징 스크립트 → dist\AIUsageWidget.exe
└── run_widget.bat            # Windows 더블클릭 실행 런처 (소스 실행)
```

## 주요 기능
- **무설치 표준 라이브러리 기반**: 위젯 본체는 Python 기본 내장 모듈(`tkinter`, `urllib`, `sqlite3`, `ctypes`)만으로 동작합니다. 시스템 트레이만 `pystray`+`Pillow` 를 쓰며, 없으면 트레이 없이 실행됩니다(exe 에는 포함).
- **시스템 트레이**: 로고 아이콘이 작업 표시줄 알림 영역에 상주합니다. 아이콘 클릭 = 위젯 보이기/숨기기, 우클릭 메뉴 = 새로고침 / Windows 시작 시 실행 / 종료. 위젯의 `✕` 는 종료가 아니라 트레이로 숨기기입니다.
- **시작 프로그램 자동 등록**: exe 를 어느 PC에서든 처음 실행하면 현재 사용자의 시작 프로그램(HKCU Run)에 자동 등록됩니다. 트레이 메뉴에서 끄면 그 선택이 `~/.usage_widget/autostart_disabled` 로 기억되어 다시 켜지지 않습니다. exe 를 옮긴 뒤 한 번 실행하면 등록 경로도 갱신됩니다.
- **중복 실행 방지**: 이미 실행 중이면 두 번째 실행은 조용히 종료됩니다.
- **자동 계정 연동 및 원클릭 재연동**:
  - **Claude**: 로컬 `~/.claude/.credentials.json` OAuth 토큰 자동 감지 및 `claude login` 연동. 재부팅 등으로 토큰이 만료돼 있으면 위젯이 직접 갱신해 같은 파일에 되써 넣습니다(Claude Code 와 토큰 공유).
  - **Codex**: 로컬 `~/.codex/auth.json` OAuth 토큰 자동 감지 및 `codex login` 연동
  - **Gemini & Argon**: 위젯 전용 OAuth(`~/.usage_widget/gemini_oauth.json`) → Windows 자격 증명 관리자(`gemini:antigravity`) → Antigravity IDE(`%APPDATA%/Antigravity/.../state.vscdb`) 순서로 자동 감지하며, OAuth 클라이언트 정보는 PC 의 agy 설치본에서 읽어 짝을 검증한 뒤 `~/.usage_widget/gemini_client.json` 에 캐싱합니다. 일반 Gemini 모델(5시간/주간)과 **Argon(`Gemini 4 Argon`)** 주간 쿼터를 별도 카드로 분리해 표시합니다.
  - **Antigravity 를 안 써도 연동 가능 (배포용 exe)**: exe 에는 빌드 PC 에서 검증된 OAuth 클라이언트가 동봉되어 있어, agy 가 없는 PC 에서도 `계정 연동` → 브라우저 Google 로그인만 하면 됩니다. 소스 실행은 여전히 agy 설치본(또는 기존 캐시)이 필요합니다.
- **⚙ 표시 설정 (카드·세부 모델 선택)**: 위젯 상단 `⚙` → 서비스별 하위 메뉴에서
  - `카드 표시` 체크를 끄면 그 카드가 사라집니다 (예: Codex 를 안 쓰면 꺼서 빨간 '미연동' 카드를 숨김).
  - 행 단위로 켜고 끕니다. 기본 행(5시간/주간)은 처음부터 보이고, **세부 모델 행**은 처음엔 숨겨져 있어 필요할 때 켭니다.
    - Claude: `7일 Sonnet 잔여`, `7일 Opus 잔여` (요금제가 내려줄 때만 메뉴에 나타남)
    - Codex: 모델별 추가 한도(`additional_rate_limits`, 예: `codex-mini · 7일 주간 잔여`)
    - Gemini: Antigravity 의 다른 모델 그룹(예: `Claude and GPT models · 5시간 한도 잔여`)
  - 설정은 `~/.usage_widget/display.json` 에 저장되어 재시작해도 유지됩니다.
- **위젯 편의 기능**: 드래그 이동, 항상 위 표시(트레이 아이콘 클릭으로 보이기/숨기기), 수동 새로고침(`↻`), 5분 주기 자동 갱신(시간 초과 시 1회 재시도 후 직전 값 유지)

## 배포용 exe 만들기

```powershell
.\build.bat
```
- 결과물: `dist\AIUsageWidget.exe` (단일 파일, 약 20MB). 이 파일 하나만 다른 PC에 복사해 실행하면 됩니다.
- **python.org Python(`py` 런처)이 필요합니다.** Anaconda Python 으로 빌드하면 pyexpat DLL 충돌로 exe 가 시작 즉시 죽기 때문에, `build.bat` 은 `py -3` 로 전용 venv(`.venv-build`)를 만들어 그 안에서 빌드합니다.
- **Gemini 클라이언트 동봉**: 빌드 PC 의 `~/.usage_widget/gemini_client.json`(위젯에서 Gemini 연동을 한 번 성공하면 생김)을 exe 안에 넣습니다. 파일이 없으면 `[WARN]` 을 띄우고, 그 exe 는 Antigravity 없는 PC 에서 Gemini 연동이 안 됩니다. 저장소에는 올라가지 않습니다.
- 로고를 바꾸려면 `assets/make_icon.py` 를 수정 후 실행하고 다시 빌드합니다.
- 실행 중인 exe 는 덮어쓸 수 없으므로 재빌드 전 트레이 메뉴 → 종료 하세요.

## 실행 방법

1. **콘솔 창 없이 위젯 실행**:
   - `run_widget.bat` 더블클릭 또는 터미널에서 실행:
   ```powershell
   pythonw widget.py
   ```
2. **동작 자가 검증**:
   ```powershell
   python test_providers.py   # 오프라인 로직 검증
   python -m providers
   python widget.py --check
   ```
