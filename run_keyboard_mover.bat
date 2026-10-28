@echo off
rem Double-click to run keyboard_mover.py (must be in the same folder as this file).
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install it from https://www.python.org/downloads/
    echo and check "Add python.exe to PATH" during setup.
    pause
    exit /b 1
)

py -c "import pynput" >nul 2>nul
if errorlevel 1 (
    echo Installing pynput...
    py -m pip install pynput
    if errorlevel 1 (
        echo Failed to install pynput.
        pause
        exit /b 1
    )
)

echo Press Ctrl+C in this window to stop.
py keyboard_mover.py
pause
