@echo off
rem Launch Jarvis Assistant using project venv
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py" %*
exit
