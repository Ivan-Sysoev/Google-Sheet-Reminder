"""
Async CRUD operations over SQLite via aiosqlite.
"""

import logging
from typing import Optional
import aiosqlite

from bot.db.models import ALL_TABLES
from bot.config import DATABASE_PATH, DEFAULT_POLLING_INTERVAL

logger = logging.getLogger(__name__)


async def init_db() -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        for statement in ALL_TABLES:
            await db.execute(statement)
        # Migration: add alias column to existing databases
        try:
            await db.execute("ALTER TABLE tracked_sheets ADD COLUMN alias TEXT")
            logger.info("Migration applied: added 'alias' column to tracked_sheets")
        except Exception:
            pass  # Column already exists
        await db.commit()
    logger.info("Database initialized at %s", DATABASE_PATH)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

async def upsert_user(user_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (id) VALUES (?)",
            (user_id,),
        )
        await db.commit()


async def get_all_user_ids() -> list[int]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT id FROM users") as cursor:
            rows = await cursor.fetchall()
    return [row[0] for row in rows]


# ---------------------------------------------------------------------------
# Tracked sheets
# ---------------------------------------------------------------------------

async def add_tracked_sheet(
    user_id: int,
    spreadsheet_id: str,
    spreadsheet_name: str,
    polling_interval: int = DEFAULT_POLLING_INTERVAL,
    alias: Optional[str] = None,
) -> bool:
    """Returns True if inserted, False if already tracked."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT OR IGNORE INTO tracked_sheets
                (user_id, spreadsheet_id, spreadsheet_name, alias, polling_interval)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, spreadsheet_id, spreadsheet_name, alias, polling_interval),
        )
        await db.commit()
        return cursor.rowcount > 0


async def remove_tracked_sheet(user_id: int, spreadsheet_id: str) -> bool:
    """Returns True if removed, False if wasn't tracked."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM tracked_sheets WHERE user_id = ? AND spreadsheet_id = ?",
            (user_id, spreadsheet_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_user_tracked_sheets(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT spreadsheet_id, spreadsheet_name, alias,
                   COALESCE(alias, spreadsheet_name) AS display_name,
                   polling_interval
            FROM tracked_sheets
            WHERE user_id = ?
            """,
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_spreadsheet_id_by_name(user_id: int, name: str) -> Optional[str]:
    """Find spreadsheet_id by alias or spreadsheet_name (case-insensitive)."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            """
            SELECT spreadsheet_id FROM tracked_sheets
            WHERE user_id = ?
              AND (LOWER(alias) = LOWER(?) OR (alias IS NULL AND LOWER(spreadsheet_name) = LOWER(?)))
            LIMIT 1
            """,
            (user_id, name, name),
        ) as cursor:
            row = await cursor.fetchone()
    return row[0] if row else None


async def update_alias(user_id: int, spreadsheet_id: str, alias: Optional[str]) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "UPDATE tracked_sheets SET alias = ? WHERE user_id = ? AND spreadsheet_id = ?",
            (alias, user_id, spreadsheet_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_all_tracked_sheets() -> list[dict]:
    """
    Return all distinct spreadsheets with per-(user, spreadsheet) data.

    Shape:
    [
        {
            "spreadsheet_id": str,
            "subscribers": [
                {"user_id": int, "polling_interval": int, "display_name": str},
                ...
            ],
        },
        ...
    ]
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT spreadsheet_id, spreadsheet_name, alias,
                   COALESCE(alias, spreadsheet_name) AS display_name,
                   user_id, polling_interval
            FROM tracked_sheets
            ORDER BY spreadsheet_id
            """
        ) as cursor:
            rows = await cursor.fetchall()

    grouped: dict[str, dict] = {}
    for row in rows:
        sid = row["spreadsheet_id"]
        if sid not in grouped:
            grouped[sid] = {"spreadsheet_id": sid, "subscribers": []}
        grouped[sid]["subscribers"].append(
            {
                "user_id": row["user_id"],
                "polling_interval": row["polling_interval"],
                "display_name": row["display_name"],
            }
        )
    return list(grouped.values())


async def get_sheet_polling_interval(user_id: int, spreadsheet_id: str) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT polling_interval FROM tracked_sheets WHERE user_id = ? AND spreadsheet_id = ?",
            (user_id, spreadsheet_id),
        ) as cursor:
            row = await cursor.fetchone()
    return row[0] if row else DEFAULT_POLLING_INTERVAL


async def set_sheet_polling_interval(
    user_id: int, spreadsheet_id: str, interval: int
) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "UPDATE tracked_sheets SET polling_interval = ? WHERE user_id = ? AND spreadsheet_id = ?",
            (interval, user_id, spreadsheet_id),
        )
        await db.commit()
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------

async def get_snapshot(spreadsheet_id: str) -> dict[int, str]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT sheet_id, title FROM snapshots WHERE spreadsheet_id = ?",
            (spreadsheet_id,),
        ) as cursor:
            rows = await cursor.fetchall()
    return {row[0]: row[1] for row in rows}


async def save_snapshot(spreadsheet_id: str, sheets: dict[int, str]) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM snapshots WHERE spreadsheet_id = ?", (spreadsheet_id,)
        )
        await db.executemany(
            "INSERT INTO snapshots (spreadsheet_id, sheet_id, title) VALUES (?, ?, ?)",
            [(spreadsheet_id, sheet_id, title) for sheet_id, title in sheets.items()],
        )
        await db.commit()
