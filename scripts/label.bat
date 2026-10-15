@echo off
REM Label everything harvest.bat gathered. Enter accepts, so a correct guess
REM costs one keystroke. Quitting halfway keeps what is done.

call "%~dp0_python.bat" || exit /b 1
"%PY%" "%~dp0..\tools\label.py" %*
if errorlevel 1 pause
