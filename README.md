# numtest: Standalone Number Processor

A self-contained number processing tool for preparing text for Text-to-Speech (TTS) systems.

## Quick Start

### Linux / macOS

```bash
# One-time setup
./install.sh

# Run the number processor
./run.sh input_file.txt --review
./run.sh input_file.txt --dry-run

# Or use interactive menu
./test_numbers_with_ai.sh input_file.txt
```

### Windows

```bat
# One-time setup
install.bat

# Run the number processor
run.bat input_file.txt --review
run.bat input_file.txt --dry-run

# Or use interactive menu
test_numbers_with_ai.bat input_file.txt
```

## What's Included

- **process_numbers.py** — Main entry point for number processing
- **rules_processor.py** — Rule-based number classification engine
- **ai_numbered_processor.py** — AI-assisted number formatting
- **review_window.py** — Interactive PyQt5 review window
- **ai/** — Number classification AI service (self-contained, no parent dependencies)
- **prompts/** — Number formatting prompt templates
- **ai_config.json** — AI provider configuration (Ollama by default)

## Usage Modes

```bash
# Rules only (no AI) — works offline
./run.sh input.txt

# Rules + AI on uncertain numbers (default)
./run.sh input.txt --ai-mode rules_then_ai

# AI only
./run.sh input.txt --ai-mode ai_only

# Preview proposals without applying
./run.sh input.txt --dry-run

# Interactive review window
./run.sh input.txt --review
```

## AI Configuration

By default, numtest uses **Ollama** locally with `wizardlm2:latest`.

To use a different AI provider, edit `ai_config.json`:
- Gemini API
- OpenAI (GPT-3.5, GPT-4)
- Groq (free tier)
- Anthropic Claude
- Together.ai

See `ai_config.json` for configuration examples.

## No Parent Dependencies

numtest is completely standalone:
- ✓ No imports from parent `bookfix/` project
- ✓ Self-contained AI service
- ✓ Local prompts directory
- ✓ Local learning data

Can be:
- ✓ Zipped and moved to another machine
- ✓ Run on Linux, macOS, Windows
- ✓ Distributed to other users (with just Python 3.8+)

## Requirements

- Python 3.8+
- pip
- spaCy `en_core_web_md` model (auto-downloaded by install script)
- Optional: Ollama (for AI modes)

## File Output

When processing `input.txt`:
- `input_numbered.txt` — Processed text with numbers formatted
- `logs/input_number_proposals.txt` — All proposed changes (preview)
- `logs/input_number_changes.txt` — Applied changes (after processing)

## Integration with Main Program

Eventually, numtest will be re-integrated into the main BookFix program as a standalone module.
For now, it's a complete development and testing environment.
