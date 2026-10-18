# AI 잔여 사용량 확인 Windows 위젯

Claude, Codex, Gemini 계정을 연동하여 각 서비스의 실시간 잔여 사용량(%)과 초기화까지 남은 시간을 바탕화면에 띄워주는 경량 Windows 위젯입니다.

## 주요 기능
- **무설치 표준 라이브러리 기반**: 외부 패키지(`pip install`) 없이 Python 기본 내장 모듈(`tkinter`, `urllib`, `sqlite3`)만으로 동작합니다.
- **자동 계정 연동 및 원클릭 재연동**:
  - **Claude**: 로컬 `~/.claude/.credentials.json` OAuth 토큰 자동 감지 및 `claude login` 연동
  - **Codex**: 로컬 `~/.codex/auth.json` OAuth 토큰 자동 감지 및 `codex login` 연동
  - **Gemini**: Antigravity IDE 인증(`%APPDATA%/Antigravity/.../state.vscdb`) 자동 감지 또는 위젯 내 브라우저 OAuth 직접 연동(`~/.usage_widget/gemini_oauth.json`)
- **위젯 편의 기능**: 드래그 이동, 항상 위 고정(`📌`), 수동 새로고침(`↻`), 1분 주기 자동 갱신

## 실행 방법

1. **콘솔 창 없이 위젯 실행**:
   - `run_widget.bat` 더블클릭 또는 터미널에서 실행:
   ```powershell
   pythonw widget.py
   ```
2. **동작 자가 검증**:
   ```powershell
   python providers.py
   python widget.py --check
   ```
