@echo off
REM Run the number processor

cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo Error: venv not found. Please run install.bat first.
    pause
    exit /b 1
)
venv\Scripts\python.exe process_numbers.py %*
