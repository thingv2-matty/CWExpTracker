@echo off
REM Watch the exp bar while grinding and keep every distinct reading.
REM Nothing to do while it runs. Ctrl+C or close the window to stop early.
REM
REM     harvest.bat --target 200
REM     harvest.bat --forever

call "%~dp0_python.bat" || exit /b 1
"%PY%" "%~dp0..\tools\harvest.py" %*
echo.
pause
