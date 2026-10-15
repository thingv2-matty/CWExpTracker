@echo off
REM Find the per-user Python. It is deliberately not on PATH on this machine,
REM so it is called by full path rather than relying on the environment.
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not exist "%PY%" (
    for /f "delims=" %%i in ('where python 2^>nul') do set "PY=%%i"
)
if not exist "%PY%" (
    echo.
    echo Could not find Python. Install it from python.org, or edit
    echo scripts\_python.bat to point at it.
    echo.
    pause
    exit /b 1
)
