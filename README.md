# Google Sheet Reminder Bot

Telegram bot that monitors Google Spreadsheets for structural changes — specifically, addition of new worksheets (tabs) — and sends instant notifications to subscribed users.

---

## Features

- Track multiple Google Spreadsheets per user
- Per-URL configurable polling interval
- Works with any **publicly accessible** spreadsheet — no sharing required
- Change detection by stable `sheetId` (ignores renames, catches additions)
- Deduplication — a spreadsheet shared across users is fetched only once per cycle
- SQLite storage, no external dependencies

---

## How it works

```
User adds URL
     │
     ▼
Bot opens the sheet via Google Sheets API (Service Account)
Saves initial snapshot {sheetId → title} to DB
     │
     ▼
Background polling loop runs continuously
  For each tracked (user, spreadsheet):
    If elapsed time ≥ polling_interval:
      Fetch current worksheet list
      Diff against stored snapshot
      If new sheets found → send Telegram notification
      Update snapshot in DB
```

New sheets are identified by `sheetId` (a stable numeric ID), so renaming a tab does **not** trigger a notification. Only genuinely new tabs do.

---

## Bot Commands

| Command | Description |
|---|---|
| `/start` | Register your account |
| `/add <url>` | Start tracking a Google Spreadsheet |
| `/remove <url>` | Stop tracking a spreadsheet |
| `/list` | Show all tracked spreadsheets with their polling intervals |
| `/set_interval <url> <seconds>` | Change polling interval for a specific spreadsheet |

**Example:**
```
/add https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/edit
/set_interval https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/edit 120
```

---

## Project Structure

```
google-sheet-reminder-bot/
├── bot/
│   ├── main.py                   # Entrypoint: wires bot + polling task
│   ├── config.py                 # All configuration (env vars + constants)
│   ├── handlers/
│   │   └── commands.py           # Telegram command handlers
│   ├── services/
│   │   ├── sheets_service.py     # Google Sheets API wrapper (gspread)
│   │   └── polling_service.py    # Background change-detection loop
│   └── db/
│       ├── models.py             # SQL CREATE TABLE statements
│       └── crud.py               # Async CRUD operations (aiosqlite)
├── credentials.json              # Google Service Account key (not committed)
├── .env                          # Local configuration (not committed)
├── .env.example                  # Configuration template
├── requirements.txt
└── README.md
```

---

## Configuration

All settings live in `bot/config.py` and are read from environment variables (`.env` file).

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | **required** | Telegram bot token from [@BotFather](https://t.me/BotFather) |
| `GOOGLE_API_KEY` | **required** | Google API key from Cloud Console (Sheets API must be enabled) |
| `DATABASE_PATH` | `bot.db` | Path to SQLite database file |
| `DEFAULT_POLLING_INTERVAL` | `60` | Polling interval (seconds) applied to every newly added URL |
| `MIN_POLLING_INTERVAL` | `10` | Hard minimum a user can set via `/set_interval` |
| `MIN_CYCLE_SLEEP` | `10` | Floor for global cycle sleep — prevents spinning too fast |
| `IDLE_SLEEP` | `60` | Sleep duration when no spreadsheets are tracked |
| `POLLING_STARTUP_DELAY` | `2` | Seconds to wait after startup before the first poll |

---

## Database Schema

**`users`** — registered Telegram users

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Telegram user ID |

**`tracked_sheets`** — subscriptions

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `user_id` | INTEGER | Telegram user ID (FK → users) |
| `spreadsheet_id` | TEXT | Google Spreadsheet ID extracted from URL |
| `spreadsheet_name` | TEXT | Title at the time of `/add` |
| `polling_interval` | INTEGER | Per-URL interval in seconds |

Unique constraint: `(user_id, spreadsheet_id)` — one subscription per user per sheet.

**`snapshots`** — last known worksheet state per spreadsheet

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `spreadsheet_id` | TEXT | Google Spreadsheet ID |
| `sheet_id` | INTEGER | Stable numeric worksheet ID |
| `title` | TEXT | Worksheet title at last poll |

Unique constraint: `(spreadsheet_id, sheet_id)`.

---

## Setup

### 1. Create a Telegram Bot

1. Open [@BotFather](https://t.me/BotFather) → `/newbot`
2. Follow the prompts, copy the token

### 2. Get a Google API Key

1. Open [Google Cloud Console](https://console.cloud.google.com/)
2. Go to **APIs & Services → Library** → enable **Google Sheets API**
3. Go to **APIs & Services → Credentials → Create Credentials → API key**
4. Copy the key into your `.env` as `GOOGLE_API_KEY`

### 3. Make Sure Spreadsheets are Public

The spreadsheet must allow public access — the bot does not use any account credentials:

- Open the sheet → **Share → Change to anyone with the link → Viewer**

The bot is strictly read-only and never writes to any sheet.

### 4. Install and Configure

```bash
git clone <repo>
cd google-sheet-reminder-bot

python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — set BOT_TOKEN at minimum
```

### 5. Run

```bash
python -m bot.main
```

Logs are printed to stdout in the format:
```
2024-01-15 12:00:00 [INFO] bot.main: Starting bot
2024-01-15 12:00:02 [INFO] bot.services.polling_service: Polling loop started
```

---

## Notification Format

When new worksheets are detected:

```
📄 New sheets added in My Spreadsheet:

  • Q1 Report
  • Q2 Report
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `aiogram` | Telegram Bot API framework (async) |
| `aiohttp` | Async HTTP client for Sheets API v4 requests |
| `aiosqlite` | Async SQLite driver |
| `python-dotenv` | `.env` file loader |
