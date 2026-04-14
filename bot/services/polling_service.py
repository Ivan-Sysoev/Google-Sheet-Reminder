"""
Background polling service.

Architecture:
- A single asyncio task iterates over all tracked spreadsheets.
- Deduplication: each spreadsheet is fetched only once per cycle, even if
  multiple users track the same one.
- Per-(user, spreadsheet) polling interval: each row in tracked_sheets has its
  own interval. A subscriber is "due" when (now - last_check) >= their interval.
- The global cycle sleep is the minimum interval across all active subscriptions
  (floored by MIN_CYCLE_SLEEP from config).
"""

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from bot.config import IDLE_SLEEP, MIN_CYCLE_SLEEP, POLLING_STARTUP_DELAY
from bot.db import crud
from bot.services.sheets_service import SheetsAccessError, fetch_spreadsheet

if TYPE_CHECKING:
    from aiogram import Bot

logger = logging.getLogger(__name__)

# {(user_id, spreadsheet_id): last_check_monotonic_timestamp}
_last_check: dict[tuple[int, str], float] = {}


async def _check_spreadsheet(spreadsheet_id: str) -> tuple[list[str], list[str]]:
    """
    Fetch current state and diff against stored snapshot.
    Returns (new_sheet_titles, deleted_sheet_titles).
    Persists updated snapshot on any change.
    """
    try:
        _, current_sheets = await fetch_spreadsheet(spreadsheet_id)
    except SheetsAccessError as e:
        logger.warning("Cannot access spreadsheet %s: %s", spreadsheet_id, e)
        return [], []
    except Exception as e:
        logger.error("Unexpected error fetching %s: %s", spreadsheet_id, e)
        return [], []

    previous = await crud.get_snapshot(spreadsheet_id)

    new_ids = set(current_sheets) - set(previous)
    deleted_ids = set(previous) - set(current_sheets)

    if new_ids or deleted_ids:
        await crud.save_snapshot(spreadsheet_id, current_sheets)
        if deleted_ids:
            logger.info(
                "Spreadsheet %s: deleted sheets: %s",
                spreadsheet_id,
                [previous[sid] for sid in deleted_ids],
            )

    return [current_sheets[sid] for sid in new_ids], [previous[sid] for sid in deleted_ids]


async def _notify_users(
    bot: "Bot",
    user_ids: list[int],
    spreadsheet_name: str,
    new_titles: list[str],
) -> None:
    bullet_list = "\n".join(f"  • {t}" for t in new_titles)
    text = f"📄 New sheets added in <b>{spreadsheet_name}</b>:\n\n{bullet_list}"
    for user_id in user_ids:
        try:
            await bot.send_message(user_id, text, parse_mode="HTML")
        except Exception as e:
            logger.warning("Failed to notify user %d: %s", user_id, e)


async def polling_loop(bot: "Bot") -> None:
    """Main polling loop. Run as a background asyncio task."""
    logger.info("Polling loop started")
    await asyncio.sleep(POLLING_STARTUP_DELAY)

    while True:
        try:
            await _run_cycle(bot)
        except asyncio.CancelledError:
            logger.info("Polling loop cancelled")
            return
        except Exception:
            logger.exception("Unhandled error in polling cycle")

        sleep_for = await _next_cycle_sleep()
        logger.debug("Next poll cycle in %d seconds", sleep_for)
        await asyncio.sleep(sleep_for)


async def _next_cycle_sleep() -> int:
    """Return how long to sleep until the soonest subscriber is due."""
    all_sheets = await crud.get_all_tracked_sheets()
    if not all_sheets:
        return IDLE_SLEEP

    now = time.monotonic()
    min_wait = IDLE_SLEEP

    for sheet_info in all_sheets:
        sid = sheet_info["spreadsheet_id"]
        for sub in sheet_info["subscribers"]:
            interval = sub["polling_interval"]
            last = _last_check.get((sub["user_id"], sid), 0.0)
            wait = max(0, interval - (now - last))
            min_wait = min(min_wait, wait)

    return max(MIN_CYCLE_SLEEP, int(min_wait))


async def _run_cycle(bot: "Bot") -> None:
    now = time.monotonic()
    all_sheets = await crud.get_all_tracked_sheets()

    for sheet_info in all_sheets:
        spreadsheet_id = sheet_info["spreadsheet_id"]
        spreadsheet_name = sheet_info["spreadsheet_name"]

        # Collect subscribers whose interval has elapsed
        due: list[int] = [
            sub["user_id"]
            for sub in sheet_info["subscribers"]
            if now - _last_check.get((sub["user_id"], spreadsheet_id), 0.0)
            >= sub["polling_interval"]
        ]

        if not due:
            continue

        new_titles, _ = await _check_spreadsheet(spreadsheet_id)

        ts = time.monotonic()
        for uid in due:
            _last_check[(uid, spreadsheet_id)] = ts

        if new_titles:
            await _notify_users(bot, due, spreadsheet_name, new_titles)
