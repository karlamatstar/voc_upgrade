@echo off
rem VOC 에이전트 서버 6개 GUI 런처 (콘솔 창 없이 GUI만 표시)
rem 이 배치파일은 RUN 폴더 안에 있지만, 실제 프로젝트 루트(상위 폴더)를
rem 작업 위치로 사용해 server_gui.py를 실행합니다.
cd /d "%~dp0.."
start "" "%~dp0..\.venv\Scripts\pythonw.exe" "%~dp0..\server_gui.py"
