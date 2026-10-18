# AI 잔여 사용량 확인 Windows 위젯

Claude, Codex, Gemini 및 Argon(`Gemini 4 Argon`) 계정을 연동하여 각 서비스의 실시간 잔여 사용량(%)과 초기화까지 남은 시간을 바탕화면에 띄워주는 경량 Windows 위젯입니다.

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
│   └── autostart.py          # Windows 시작 프로그램 등록(HKCU Run 레지스트리)
├── assets/
│   ├── icon.ico              # 앱/트레이 로고
│   └── make_icon.py          # 로고 생성 스크립트 (Pillow)
├── widget.py                 # 위젯 실행 진입점 (main, 중복 실행 방지, --check 자가 검증)
├── build.bat                 # exe 패키징 스크립트 → dist\AIUsageWidget.exe
└── run_widget.bat            # Windows 더블클릭 실행 런처 (소스 실행)
```

## 주요 기능
- **무설치 표준 라이브러리 기반**: 위젯 본체는 Python 기본 내장 모듈(`tkinter`, `urllib`, `sqlite3`, `ctypes`)만으로 동작합니다. 시스템 트레이만 `pystray`+`Pillow` 를 쓰며, 없으면 트레이 없이 실행됩니다(exe 에는 포함).
- **시스템 트레이**: 로고 아이콘이 작업 표시줄 알림 영역에 상주합니다. 아이콘 클릭 = 위젯 보이기/숨기기, 우클릭 메뉴 = 새로고침 / Windows 시작 시 실행 / 종료. 위젯의 `✕` 는 종료가 아니라 트레이로 숨기기입니다.
- **시작 프로그램 자동 등록**: exe 를 어느 PC에서든 처음 실행하면 현재 사용자의 시작 프로그램(HKCU Run)에 자동 등록됩니다. 트레이 메뉴에서 끄면 그 선택이 `~/.usage_widget/autostart_disabled` 로 기억되어 다시 켜지지 않습니다. exe 를 옮긴 뒤 한 번 실행하면 등록 경로도 갱신됩니다.
- **중복 실행 방지**: 이미 실행 중이면 두 번째 실행은 조용히 종료됩니다.
- **자동 계정 연동 및 원클릭 재연동**:
  - **Claude**: 로컬 `~/.claude/.credentials.json` OAuth 토큰 자동 감지 및 `claude login` 연동
  - **Codex**: 로컬 `~/.codex/auth.json` OAuth 토큰 자동 감지 및 `codex login` 연동
  - **Gemini & Argon**: 위젯 전용 OAuth(`~/.usage_widget/gemini_oauth.json`) → Windows 자격 증명 관리자(`gemini:antigravity`) → Antigravity IDE(`%APPDATA%/Antigravity/.../state.vscdb`) 순서로 자동 감지하며, 일반 Gemini 모델(5시간/주간)과 **Argon(`Gemini 4 Argon`)** 주간 쿼터를 별도 카드로 분리해 표시합니다.
- **위젯 편의 기능**: 드래그 이동, 항상 위 고정(`📌`), 수동 새로고침(`↻`), 1분 주기 자동 갱신

## 배포용 exe 만들기

```powershell
.\build.bat
```
- 결과물: `dist\AIUsageWidget.exe` (단일 파일, 약 20MB). 이 파일 하나만 다른 PC에 복사해 실행하면 됩니다.
- **python.org Python(`py` 런처)이 필요합니다.** Anaconda Python 으로 빌드하면 pyexpat DLL 충돌로 exe 가 시작 즉시 죽기 때문에, `build.bat` 은 `py -3` 로 전용 venv(`.venv-build`)를 만들어 그 안에서 빌드합니다.
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
   python -m providers
   python widget.py --check
   ```
