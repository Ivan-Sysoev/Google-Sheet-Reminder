"""
CRUD operations for the allowed_users access-control table.
"""

from typing import Optional

import aiosqlite

from bot.config import DATABASE_PATH


async def is_user_allowed(user_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM allowed_users WHERE user_id = ?", (user_id,)
        ) as cursor:
            return await cursor.fetchone() is not None


async def add_allowed_user(user_id: int, note: Optional[str] = None) -> bool:
    """Returns True if inserted, False if already existed."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "INSERT OR IGNORE INTO allowed_users (user_id, note) VALUES (?, ?)",
            (user_id, note),
        )
        await db.commit()
        return cursor.rowcount > 0


async def remove_allowed_user(user_id: int) -> bool:
    """Returns True if removed, False if wasn't in the list."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM allowed_users WHERE user_id = ?", (user_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_all_allowed_users() -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, note, added_at FROM allowed_users ORDER BY added_at"
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(row) for row in rows]
