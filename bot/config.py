import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

BOT_TOKEN: str = os.environ["BOT_TOKEN"]

# ---------------------------------------------------------------------------
# Google Sheets
# ---------------------------------------------------------------------------

# API key from Google Cloud Console — works for any publicly accessible spreadsheet
GOOGLE_API_KEY: str = os.environ["GOOGLE_API_KEY"]

# Base URL for Sheets API v4
SHEETS_API_BASE_URL: str = "https://sheets.googleapis.com/v4/spreadsheets"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASE_PATH: str = os.getenv("DATABASE_PATH", "bot.db")

# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

CREATOR_CONTACT: str = os.environ["CREATOR_CONTACT"]

# ---------------------------------------------------------------------------
# Polling — loaded from polling_config.yaml
# ---------------------------------------------------------------------------

_POLLING_CONFIG_PATH = Path(__file__).parent.parent / "polling_config.yaml"

with open(_POLLING_CONFIG_PATH) as _f:
    _polling = yaml.safe_load(_f)["polling"]

DEFAULT_POLLING_INTERVAL: int = _polling["default_interval"]
MIN_POLLING_INTERVAL: int     = _polling["min_interval"]
MIN_CYCLE_SLEEP: int          = _polling["min_cycle_sleep"]
IDLE_SLEEP: int               = _polling["idle_sleep"]
POLLING_STARTUP_DELAY: int    = _polling["startup_delay"]
