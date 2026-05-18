@echo off
REM Interactive script to test number processing with selectable AI modes
REM Usage: test_numbers_with_ai.bat input_file

if "%~1"=="" (
    echo Usage: test_numbers_with_ai.bat input_file
    echo.
    echo Example: test_numbers_with_ai.bat sample.txt
    pause
    exit /b 1
)

set INPUT_FILE=%~f1

if not exist "%INPUT_FILE%" (
    echo Error: File not found: %INPUT_FILE%
    pause
    exit /b 1
)

cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo Error: venv not found. Please run install.bat first.
    pause
    exit /b 1
)

echo.
echo === Number Processing AI Mode ===
echo 1) Rules only ^(no AI^)
echo 2) Rules + AI on uncertain numbers
echo 3) AI only ^(skip rules^)
echo.
set /p CHOICE="Select mode (1-3): "

if "%CHOICE%"=="1" (
    set AI_MODE=rules_only
) else if "%CHOICE%"=="2" (
    set AI_MODE=rules_then_ai
) else if "%CHOICE%"=="3" (
    set AI_MODE=ai_only
) else (
    echo Invalid choice
    pause
    exit /b 1
)

venv\Scripts\python.exe process_numbers.py "%INPUT_FILE%" --review --ai-mode %AI_MODE%
pause
