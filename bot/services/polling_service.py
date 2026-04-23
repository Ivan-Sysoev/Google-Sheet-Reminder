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


_SHEETS_URL = "https://docs.google.com/spreadsheets/d/{sid}/edit#gid={gid}"


async def _check_spreadsheet(spreadsheet_id: str) -> tuple[list[tuple[int, str]], list[str]]:
    """
    Fetch current state and diff against stored snapshot.
    Returns (new_sheets, deleted_sheet_titles) where new_sheets is list of (sheet_id, title).
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

    return [(sid, current_sheets[sid]) for sid in new_ids], [previous[sid] for sid in deleted_ids]


async def _notify_user(
    bot: "Bot",
    user_id: int,
    display_name: str,
    spreadsheet_id: str,
    new_sheets: list[tuple[int, str]],
) -> None:
    lines = [
        f'  • <a href="{_SHEETS_URL.format(sid=spreadsheet_id, gid=gid)}">{title}</a>'
        for gid, title in new_sheets
    ]
    text = f"📄 New sheets added in <b>{display_name}</b>:\n\n" + "\n".join(lines)
    try:
        await bot.send_message(user_id, text, parse_mode="HTML", disable_notification=False, disable_web_page_preview=True)
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

        # Collect subscribers whose interval has elapsed
        due = [
            sub
            for sub in sheet_info["subscribers"]
            if now - _last_check.get((sub["user_id"], spreadsheet_id), 0.0)
            >= sub["polling_interval"]
        ]

        if not due:
            continue

        new_sheets, _ = await _check_spreadsheet(spreadsheet_id)

        ts = time.monotonic()
        for sub in due:
            _last_check[(sub["user_id"], spreadsheet_id)] = ts

        if new_sheets:
            for sub in due:
                await _notify_user(bot, sub["user_id"], sub["display_name"], spreadsheet_id, new_sheets)
