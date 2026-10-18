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
│   └── app.py                # UsageWidgetApp 플로팅 위젯 창 및 카드 렌더링
├── widget.py                 # 위젯 실행 진입점 (main 및 --check 자가 검증)
└── run_widget.bat            # Windows 더블클릭 실행 런처
```

## 주요 기능
- **무설치 표준 라이브러리 기반**: 외부 패키지(`pip install`) 없이 Python 기본 내장 모듈(`tkinter`, `urllib`, `sqlite3`, `ctypes`)만으로 동작합니다.
- **자동 계정 연동 및 원클릭 재연동**:
  - **Claude**: 로컬 `~/.claude/.credentials.json` OAuth 토큰 자동 감지 및 `claude login` 연동
  - **Codex**: 로컬 `~/.codex/auth.json` OAuth 토큰 자동 감지 및 `codex login` 연동
  - **Gemini & Argon**: 위젯 전용 OAuth(`~/.usage_widget/gemini_oauth.json`) → Windows 자격 증명 관리자(`gemini:antigravity`) → Antigravity IDE(`%APPDATA%/Antigravity/.../state.vscdb`) 순서로 자동 감지하며, 일반 Gemini 모델(5시간/주간)과 **Argon(`Gemini 4 Argon`)** 주간 쿼터를 별도 카드로 분리해 표시합니다.
- **위젯 편의 기능**: 드래그 이동, 항상 위 고정(`📌`), 수동 새로고침(`↻`), 1분 주기 자동 갱신

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
