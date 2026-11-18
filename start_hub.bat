@echo off
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" gesture_hub.py
) else (
    python gesture_hub.py
)
if errorlevel 1 pause
