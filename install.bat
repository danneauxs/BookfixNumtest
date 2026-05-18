@echo off
REM Install numtest in a fresh virtual environment

cd /d "%~dp0"

echo Creating virtual environment...
python -m venv venv

echo Activating virtual environment...
call venv\Scripts\activate

echo Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo Downloading spaCy model...
python -m spacy download en_core_web_md

echo.
echo ============================================
echo Installation complete!
echo ============================================
echo.
echo To use numtest:
echo   run.bat input_file.txt --review
echo   run.bat input_file.txt --dry-run
echo.
echo To use the interactive menu:
echo   test_numbers_with_ai.bat input_file.txt
echo.
echo Note: AI modes require Ollama running locally
echo   Configure ai_config.json for different AI providers
echo.
pause
