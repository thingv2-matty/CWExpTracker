@echo off
REM Find a Python to run things with, and set PY and PYW to it.
REM
REM Tried in order:
REM
REM   1. the py launcher, which ships with every python.org install and knows
REM      where Python is even when it is not on PATH
REM   2. python on PATH
REM   3. the per-user install path, which is where python.org puts it by
REM      default and is where it lives on the machine this was built on
REM
REM The launcher goes first deliberately. Windows ships a stub called
REM python.exe that opens the Microsoft Store instead of running anything, and
REM "where python" finds it. Asking the launcher avoids walking into that.

set "PY="
set "PYW="

for /f "delims=" %%i in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PY=%%i"

if not defined PY (
    for /f "delims=" %%i in ('where python 2^>nul') do if not defined PY set "PY=%%i"
)

if not defined PY (
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    )
)

if not defined PY (
    echo.
    echo   Could not find Python on this computer.
    echo.
    echo   Install it from python.org, tick "Add Python to PATH" on the first
    echo   screen of the installer, then run this again.
    echo.
    pause
    exit /b 1
)

REM pythonw is the same interpreter with no console attached. It sits next to
REM python.exe in every normal install.
set "PYW=%PY%w.exe"
set "PYW=%PYW:.exew.exe=w.exe%"
if not exist "%PYW%" set "PYW=%PY%"
