@echo off
rem Double-click to open the Game Recorder window (game_recorder.py must be in the same folder).
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install it from https://www.python.org/downloads/
    echo and check "Add python.exe to PATH" during setup.
    pause
    exit /b 1
)

py -c "import pynput, mss, PIL" >nul 2>nul
if errorlevel 1 (
    echo Installing pynput, mss and pillow...
    py -m pip install pynput mss pillow
    if errorlevel 1 (
        echo Failed to install the required libraries.
        pause
        exit /b 1
    )
)

rem pyw runs without a console window.
start "" pyw game_recorder.py
