@echo off
rem Launch JARVIS CLI using project venv
"%~dp0.venv\Scripts\python.exe" "%~dp0cli\jarvis_argparse.py" %*
