#!/bin/bash

# Interactive script to test number processing with selectable AI modes
# Usage: ./test_numbers_with_ai.sh input_file

if [ -z "$1" ]; then
    echo "Usage: ./test_numbers_with_ai.sh input_file"
    exit 1
fi

INPUT_FILE="$1"

if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: File not found: $INPUT_FILE"
    exit 1
fi

# Show menu
echo ""
echo "=== Number Processing AI Mode ==="
echo "1) Rules only (no AI)"
echo "2) Rules + AI on uncertain numbers"
echo "3) AI only (skip rules)"
echo ""
read -p "Select mode (1-3): " CHOICE

case $CHOICE in
    1)
        AI_MODE="rules_only"
        ;;
    2)
        AI_MODE="rules_then_ai"
        ;;
    3)
        AI_MODE="ai_only"
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

source ../venv/bin/activate
python process_numbers.py "$INPUT_FILE" --review --ai-mode "$AI_MODE"
