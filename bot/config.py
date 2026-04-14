import os
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
# Polling
# ---------------------------------------------------------------------------

# Default polling interval (seconds) applied to every newly added spreadsheet URL
DEFAULT_POLLING_INTERVAL: int = int(os.getenv("DEFAULT_POLLING_INTERVAL", "60"))

# Hard minimum a user can set via /set_interval
MIN_POLLING_INTERVAL: int = int(os.getenv("MIN_POLLING_INTERVAL", "10"))

# Floor for the global cycle sleep so we never spin too fast even with many sheets
MIN_CYCLE_SLEEP: int = int(os.getenv("MIN_CYCLE_SLEEP", "10"))

# Sleep duration when no spreadsheets are tracked at all
IDLE_SLEEP: int = int(os.getenv("IDLE_SLEEP", "60"))

# Delay (seconds) before the first polling cycle after bot startup
POLLING_STARTUP_DELAY: int = int(os.getenv("POLLING_STARTUP_DELAY", "2"))
