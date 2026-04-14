"""
Telegram bot command handlers.
"""

import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.config import DEFAULT_POLLING_INTERVAL, MIN_POLLING_INTERVAL
from bot.db import crud
from bot.services.sheets_service import (
    InvalidURLError,
    SheetsAccessError,
    extract_spreadsheet_id,
    open_spreadsheet,
)

logger = logging.getLogger(__name__)
router = Router()


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await crud.upsert_user(message.from_user.id)
    await message.answer(
        "👋 Hello! I monitor Google Sheets for new tabs and notify you.\n\n"
        "Commands:\n"
        "  /add <url> — track a spreadsheet\n"
        "  /remove <url> — stop tracking\n"
        "  /list — show tracked spreadsheets\n"
        f"  /set_interval <url> <seconds> — set polling interval per spreadsheet (default: {DEFAULT_POLLING_INTERVAL}s)"
    )


# ---------------------------------------------------------------------------
# /add
# ---------------------------------------------------------------------------

@router.message(Command("add"))
async def cmd_add(message: Message) -> None:
    user_id = message.from_user.id
    args = (message.text or "").split(maxsplit=1)

    if len(args) < 2 or not args[1].strip():
        await message.answer("Usage: /add <google_sheet_url>")
        return

    url = args[1].strip()
    await crud.upsert_user(user_id)
    await message.answer("⏳ Checking access to the spreadsheet…")

    try:
        spreadsheet_id, title, sheets = await open_spreadsheet(url)
    except InvalidURLError:
        await message.answer(
            "❌ Invalid URL. Please send a valid Google Sheets link.\n"
            "Example: https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit"
        )
        return
    except SheetsAccessError as e:
        await message.answer(
            "❌ Cannot access the spreadsheet.\n"
            "Make sure you shared it with the service account.\n\n"
            f"Details: {e}"
        )
        return

    inserted = await crud.add_tracked_sheet(user_id, spreadsheet_id, title)

    if not inserted:
        await message.answer(f"⚠️ <b>{title}</b> is already being tracked.", parse_mode="HTML")
        return

    # Save initial snapshot so the first poll doesn't flood with "new" sheets
    await crud.save_snapshot(spreadsheet_id, sheets)

    await message.answer(
        f"✅ Now tracking <b>{title}</b>\n"
        f"Current tabs: {len(sheets)}\n"
        f"Polling interval: {DEFAULT_POLLING_INTERVAL}s",
        parse_mode="HTML",
    )
    logger.info("User %d added spreadsheet %s (%s)", user_id, spreadsheet_id, title)


# ---------------------------------------------------------------------------
# /remove
# ---------------------------------------------------------------------------

@router.message(Command("remove"))
async def cmd_remove(message: Message) -> None:
    user_id = message.from_user.id
    args = (message.text or "").split(maxsplit=1)

    if len(args) < 2 or not args[1].strip():
        await message.answer("Usage: /remove <google_sheet_url>")
        return

    spreadsheet_id = extract_spreadsheet_id(args[1].strip())
    if spreadsheet_id is None:
        await message.answer("❌ Invalid Google Sheets URL.")
        return

    removed = await crud.remove_tracked_sheet(user_id, spreadsheet_id)
    if removed:
        await message.answer("✅ Spreadsheet removed from tracking.")
        logger.info("User %d removed spreadsheet %s", user_id, spreadsheet_id)
    else:
        await message.answer("⚠️ That spreadsheet is not in your tracking list.")


# ---------------------------------------------------------------------------
# /list
# ---------------------------------------------------------------------------

@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    sheets = await crud.get_user_tracked_sheets(message.from_user.id)

    if not sheets:
        await message.answer("You have no tracked spreadsheets. Use /add to add one.")
        return

    lines = [
        f"{i + 1}. <b>{s['spreadsheet_name']}</b> — every {s['polling_interval']}s"
        for i, s in enumerate(sheets)
    ]
    await message.answer(
        "📋 Your tracked spreadsheets:\n\n" + "\n".join(lines),
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# /set_interval
# ---------------------------------------------------------------------------

@router.message(Command("set_interval"))
async def cmd_set_interval(message: Message) -> None:
    user_id = message.from_user.id
    args = (message.text or "").split(maxsplit=2)

    if len(args) < 3:
        await message.answer(
            "Usage: /set_interval <google_sheet_url> <seconds>\n"
            "Example: /set_interval https://docs.google.com/spreadsheets/d/ID/edit 120"
        )
        return

    url = args[1].strip()
    spreadsheet_id = extract_spreadsheet_id(url)
    if spreadsheet_id is None:
        await message.answer("❌ Invalid Google Sheets URL.")
        return

    try:
        interval = int(args[2].strip())
    except ValueError:
        await message.answer("❌ Please provide a valid integer number of seconds.")
        return

    if interval < MIN_POLLING_INTERVAL:
        await message.answer(f"❌ Minimum interval is {MIN_POLLING_INTERVAL} seconds.")
        return

    updated = await crud.set_sheet_polling_interval(user_id, spreadsheet_id, interval)
    if not updated:
        await message.answer("⚠️ That spreadsheet is not in your tracking list. Use /add first.")
        return

    await message.answer(f"✅ Polling interval set to {interval}s for this spreadsheet.")
    logger.info(
        "User %d set interval %ds for spreadsheet %s", user_id, interval, spreadsheet_id
    )
