@echo off
REM The whole setup, in one double-click. Nothing here has to be typed.
REM
REM It finds Python, installs the three libraries the tracker needs, makes the
REM Start EXP Tracker shortcut, and offers to open it so the first run can
REM happen straight away.
REM
REM Safe to run again. Installing libraries that are already there does
REM nothing, and remaking the shortcut just overwrites it.

setlocal
cd /d "%~dp0"
title EXP Tracker setup

echo.
echo   ============================================
echo     EXP Tracker setup
echo   ============================================
echo.
echo   This installs what the tracker needs and makes a shortcut.
echo   It does not touch MapleStory, and it never will.
echo.

call "%~dp0scripts\_python.bat" || exit /b 1
echo   Found Python:
echo     %PY%
echo.

echo   Installing the three libraries it needs. This can take a minute.
echo.
"%PY%" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo.
    echo   Installing the libraries failed.
    echo.
    echo   The usual cause is no internet, or a company laptop blocking it.
    echo   Nothing has been broken. Send whatever is printed above to Matt.
    echo.
    pause
    exit /b 1
)

echo.
echo   Making the shortcut.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\make-shortcuts.ps1"
if errorlevel 1 (
    echo.
    echo   The shortcut could not be made, but the tracker itself is installed.
    echo   You can still start it with run.bat in the scripts folder.
    echo.
)

echo.
echo   ============================================
echo     Done.
echo   ============================================
echo.
echo   There is now a "Start EXP Tracker" shortcut in this folder.
echo.
echo   The FIRST time it runs it asks you to drag a box around the
echo   experience line at the bottom of the game:
echo.
echo       EXP. 10,155[74.04%%]
echo.
echo   Have MapleStory open before you start it.
echo.

choice /c YN /n /m "   Start it now? [Y/N] "
if errorlevel 2 goto done
start "" "%~dp0Start EXP Tracker.lnk"

:done
echo.
endlocal
