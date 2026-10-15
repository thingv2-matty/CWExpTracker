@echo off
REM Start the tracker WITH a console, so printed output is visible.
REM For everyday use double-click "Start EXP Tracker" instead, which opens
REM the window and nothing else.
REM
REM     tracker.bat --region     pick the screen region again
REM     tracker.bat --teach      re-learn the characters by hand
REM     tracker.bat --debug      dump one capture and every score, then exit

call "%~dp0_python.bat" || exit /b 1
"%PY%" "%~dp0..\run.py" %*
if errorlevel 1 (
    echo.
    echo Tracker exited with an error.
    pause
)
