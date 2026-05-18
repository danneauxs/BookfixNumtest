#!/bin/bash
# Run the number processor

cd "$(dirname "$0")"
source venv/bin/activate
python process_numbers.py "$@"
