@echo off
chcp 65001 >nul
REM 단일 exe 패키징 (PyInstaller). 결과물: dist\AIUsageWidget.exe
REM Anaconda 파이썬으로 빌드하면 pyexpat DLL 충돌로 exe 가 시작 즉시 죽고 용량도 커지므로,
REM python.org 파이썬(py 런처)으로 만든 전용 venv(.venv-build)에서 빌드한다.
cd /d "%~dp0"
if not exist .venv-build\Scripts\python.exe (
  py -3 -m venv .venv-build || (echo [ERROR] python.org Python ^(py 런처^)이 필요합니다. & exit /b 1)
)
.venv-build\Scripts\python -m pip install -q --disable-pip-version-check pyinstaller pystray pillow || exit /b 1
REM Antigravity 를 안 쓰는 사람도 Gemini 를 연동할 수 있게, 이 PC 에서 검증된 OAuth 클라이언트를 exe 안에 동봉한다.
REM 저장소에는 올리지 않는다(Push Protection). 이 PC 에서 위젯 Gemini 연동을 한 번 성공시켜야 파일이 생긴다.
set "GEMINI_CLIENT=%USERPROFILE%\.usage_widget\gemini_client.json"
set "BUNDLE_ARGS="
if exist "%GEMINI_CLIENT%" set BUNDLE_ARGS=--add-data "%GEMINI_CLIENT%;bundled"
if not exist "%GEMINI_CLIENT%" echo [WARN] %GEMINI_CLIENT% 없음 - Antigravity 미설치 PC 에서는 Gemini 연동이 안 되는 exe 가 만들어집니다.
.venv-build\Scripts\pyinstaller --noconfirm --clean --onefile --windowed --name AIUsageWidget ^
  --icon assets\icon.ico --add-data "assets\icon.ico;assets" %BUNDLE_ARGS% widget.py
if errorlevel 1 exit /b 1
REM 2026-10-30 v1.0.4 사고: PyInstaller exe 는 빌드마다 바이트가 달라지는데, 그중 하나가
REM Defender 머신러닝 오탐(Trojan:Win32/Sabsik.TE.A!ml)에 걸린 채 릴리스됐다. 자동 업데이트로
REM 친구 PC 에 퍼지기 전에 막으려고, 올리기 전에 여기서 한 번 검사한다. 걸리면 다시 빌드하면 된다.
set "MPCMD=%ProgramFiles%\Windows Defender\MpCmdRun.exe"
if exist "%MPCMD%" (
  "%MPCMD%" -Scan -ScanType 3 -File "%CD%\dist\AIUsageWidget.exe" -DisableRemediation >nul
  if errorlevel 1 (echo [ERROR] Defender 가 dist\AIUsageWidget.exe 를 탐지했습니다. 릴리스하지 말고 다시 빌드하세요. & exit /b 1)
  echo [OK] Defender 검사 통과
) else (
  echo [WARN] Defender 가 없어 검사를 건너뜁니다.
)
