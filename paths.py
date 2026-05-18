"""
Path configuration for numtest standalone application.

Defines all directory and file paths used by the application.
"""

from pathlib import Path

# Root directory of the numtest application
NUMTEST_ROOT = Path(__file__).parent.absolute()

# Directory where prompts are stored
PROMPTS_DIR = NUMTEST_ROOT / "prompts"

# Directory where logs are written
LOGS_DIR = NUMTEST_ROOT / "logs"

# Input/output directories
INPUT_DIR = NUMTEST_ROOT.parent / "InputText"

# Ensure required directories exist
LOGS_DIR.mkdir(exist_ok=True)
PROMPTS_DIR.mkdir(exist_ok=True)


def get_prompt_file(filename: str) -> Path:
    """Get the full path to a prompt file."""
    return PROMPTS_DIR / filename


def get_log_file(filename: str) -> Path:
    """Get the full path to a log file."""
    return LOGS_DIR / filename
