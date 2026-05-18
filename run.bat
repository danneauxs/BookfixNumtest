@echo off
REM Run the number processor

cd /d "%~dp0"
call venv\Scripts\activate
python process_numbers.py %*
