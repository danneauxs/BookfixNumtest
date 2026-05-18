#!/bin/bash
# Install numtest in a fresh virtual environment

set -e  # Exit on any error

cd "$(dirname "$0")"

echo "Creating virtual environment..."
python3 -m venv venv

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Downloading spaCy model..."
python -m spacy download en_core_web_md

echo ""
echo "============================================"
echo "Installation complete!"
echo "============================================"
echo ""
echo "To use numtest:"
echo "  ./run.sh input_file.txt --review"
echo "  ./run.sh input_file.txt --dry-run"
echo ""
echo "To use the interactive menu:"
echo "  ./test_numbers_with_ai.sh input_file.txt"
echo ""
echo "Note: AI modes require Ollama running locally"
echo "  Configure ai_config.json for different AI providers"
echo ""
