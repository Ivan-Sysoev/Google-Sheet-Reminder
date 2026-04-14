"""
Database schema definitions and initialization.
"""

from bot.config import DEFAULT_POLLING_INTERVAL

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY   -- Telegram user id
);
"""

CREATE_TRACKED_SHEETS_TABLE = f"""
CREATE TABLE IF NOT EXISTS tracked_sheets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    spreadsheet_id TEXT NOT NULL,
    spreadsheet_name TEXT NOT NULL,
    alias TEXT,
    polling_interval INTEGER NOT NULL DEFAULT {DEFAULT_POLLING_INTERVAL},
    UNIQUE(user_id, spreadsheet_id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""

CREATE_SNAPSHOTS_TABLE = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spreadsheet_id TEXT NOT NULL,
    sheet_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    UNIQUE(spreadsheet_id, sheet_id)
);
"""

ALL_TABLES = [
    CREATE_USERS_TABLE,
    CREATE_TRACKED_SHEETS_TABLE,
    CREATE_SNAPSHOTS_TABLE,
]
