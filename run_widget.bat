@echo off
REM 어느 기기/드라이브에서 실행하든 현재 배치 파일이 위치한 폴더를 기준으로 백그라운드 실행한다.
start "" pythonw "%~dp0widget.py"
