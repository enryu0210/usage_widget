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
.venv-build\Scripts\pyinstaller --noconfirm --clean --onefile --windowed --name AIUsageWidget ^
  --icon assets\icon.ico --add-data "assets\icon.ico;assets" widget.py
