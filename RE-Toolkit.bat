@echo off
title Universal RE Toolkit v1.0 - Electron/NSIS Installer Reverse Engineering
cd /d "%~dp0"

echo ============================================================
echo   UNIVERSAL RE TOOLKIT v1.0  (Fahad x Jarvis)
echo   Extract any Electron/NSIS installer into full source+data
echo   Proven on Stonic AI 3.1.8 - 44,653 files, SHA-256 verified
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    color 4F
    echo [ERROR] Python is not installed or not in PATH.
    echo.
    echo   1. Open https://www.python.org/downloads/
    echo   2. Download Python 3.x and RUN the installer
    echo   3. IMPORTANT: tick the box  [v] Add python.exe to PATH
    echo   4. Then run RE-Toolkit.bat again
    echo.
    pause
    exit /b 1
)

if "%~1"=="" (
    echo Drag ^& drop an installer .exe onto RE-Toolkit.bat
    echo.
    set /p INPUT="Or type/paste the full path of the .exe file: "
) else (
    set "INPUT=%~1"
)

echo.
python "%~dp0re_toolkit.py" "%INPUT%"
echo.
echo ============================================================
echo   Finished. Check the RE-OUTPUT folder next to this file.
echo ============================================================
pause
