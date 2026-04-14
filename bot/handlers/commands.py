"""
Telegram bot command and reply-keyboard handlers.
"""

import logging
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot.config import DEFAULT_POLLING_INTERVAL, MIN_POLLING_INTERVAL
from bot.db import crud
from bot.handlers.keyboards import (
    format_interval,
    list_keyboard,
    main_keyboard,
    sheet_detail_keyboard,
)
from bot.services.sheets_service import (
    InvalidURLError,
    SheetsAccessError,
    extract_spreadsheet_id,
    open_spreadsheet,
)

logger = logging.getLogger(__name__)
router = Router()


# ---------------------------------------------------------------------------
# FSM: "➕ Add Sheet" button flow
# ---------------------------------------------------------------------------

class AddSheet(StatesGroup):
    waiting_for_url = State()


# ---------------------------------------------------------------------------
# Shared helper: process add-sheet request
# ---------------------------------------------------------------------------

async def _do_add(message: Message, url: str, alias: Optional[str]) -> None:
    user_id = message.from_user.id
    await crud.upsert_user(user_id)
    await message.answer("⏳ Checking access to the spreadsheet…")

    try:
        spreadsheet_id, title, sheets = await open_spreadsheet(url)
    except InvalidURLError:
        await message.answer(
            "❌ Invalid URL. Please send a valid Google Sheets link.\n"
            "Example:\n<code>https://docs.google.com/spreadsheets/d/ID/edit</code>",
            reply_markup=main_keyboard(),
        )
        return
    except SheetsAccessError as e:
        await message.answer(
            "❌ Cannot access the spreadsheet.\n"
            "Make sure it is set to <b>Anyone with the link → Viewer</b>.\n\n"
            f"Details: {e}",
            reply_markup=main_keyboard(),
        )
        return

    inserted = await crud.add_tracked_sheet(
        user_id, spreadsheet_id, title, alias=alias
    )

    display_name = alias or title

    if not inserted:
        await message.answer(
            f"⚠️ <b>{display_name}</b> is already being tracked.",
            reply_markup=main_keyboard(),
        )
        return

    await crud.save_snapshot(spreadsheet_id, sheets)

    await message.answer(
        f"✅ Now tracking <b>{display_name}</b>\n"
        f"Current tabs: {len(sheets)}\n"
        f"Polling every: {format_interval(DEFAULT_POLLING_INTERVAL)}",
        reply_markup=main_keyboard(),
    )
    logger.info("User %d added %s (alias=%s)", user_id, spreadsheet_id, alias)


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await crud.upsert_user(message.from_user.id)
    await message.answer(
        "👋 Hello! I monitor Google Sheets for new tabs and notify you.\n\n"
        "<b>Commands:</b>\n"
        "  /add <code>&lt;url&gt; [name]</code> — track a spreadsheet\n"
        "  /remove <code>&lt;url&gt;</code> — stop tracking\n"
        "  /list — show tracked spreadsheets\n"
        f"  /set_interval <code>&lt;url or name&gt; &lt;seconds&gt;</code> — set polling interval\n\n"
        "Or use the buttons below 👇",
        reply_markup=main_keyboard(),
    )


# ---------------------------------------------------------------------------
# /add <url> [optional name]
# ---------------------------------------------------------------------------

@router.message(Command("add"))
async def cmd_add(message: Message) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "Usage: /add <code>&lt;url&gt; [optional name]</code>\n\n"
            "Examples:\n"
            "<code>/add https://docs.google.com/spreadsheets/d/ID/edit</code>\n"
            "<code>/add https://docs.google.com/spreadsheets/d/ID/edit Q1 Report</code>"
        )
        return

    tokens = parts[1].strip().split(maxsplit=1)
    url = tokens[0]
    alias = tokens[1].strip() if len(tokens) > 1 else None
    await _do_add(message, url, alias)


# ---------------------------------------------------------------------------
# ➕ Add Sheet button — FSM flow (no command syntax needed)
# ---------------------------------------------------------------------------

@router.message(F.text == "➕ Add Sheet")
async def btn_add_sheet(message: Message, state: FSMContext) -> None:
    await state.set_state(AddSheet.waiting_for_url)
    await message.answer(
        "Send me the spreadsheet URL.\n"
        "Optionally add a custom name after the URL:\n\n"
        "<code>https://docs.google.com/spreadsheets/d/ID/edit</code>\n"
        "<code>https://docs.google.com/spreadsheets/d/ID/edit Q1 Report</code>\n\n"
        "Send /cancel to go back."
    )


@router.message(AddSheet.waiting_for_url)
async def fsm_add_url(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    tokens = text.split(maxsplit=1)
    url = tokens[0]
    alias = tokens[1].strip() if len(tokens) > 1 else None

    await state.clear()
    await _do_add(message, url, alias)


# ---------------------------------------------------------------------------
# /remove <url>
# ---------------------------------------------------------------------------

@router.message(Command("remove"))
async def cmd_remove(message: Message) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Usage: /remove <code>&lt;google_sheet_url&gt;</code>")
        return

    spreadsheet_id = extract_spreadsheet_id(parts[1].strip())
    if spreadsheet_id is None:
        await message.answer("❌ Invalid Google Sheets URL.")
        return

    removed = await crud.remove_tracked_sheet(message.from_user.id, spreadsheet_id)
    if removed:
        await message.answer("✅ Spreadsheet removed from tracking.", reply_markup=main_keyboard())
    else:
        await message.answer("⚠️ That spreadsheet is not in your tracking list.")


# ---------------------------------------------------------------------------
# /list + 📋 My Sheets button
# ---------------------------------------------------------------------------

async def _send_list(message: Message) -> None:
    sheets = await crud.get_user_tracked_sheets(message.from_user.id)
    if not sheets:
        await message.answer(
            "You have no tracked spreadsheets.\nUse ➕ Add Sheet to add one.",
            reply_markup=main_keyboard(),
        )
        return

    lines = [
        f"{i + 1}. <b>{s['display_name']}</b> — every {format_interval(s['polling_interval'])}"
        for i, s in enumerate(sheets)
    ]
    await message.answer(
        "📋 <b>Your tracked spreadsheets:</b>\n\n" + "\n".join(lines),
        reply_markup=list_keyboard(sheets),
    )


@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    await _send_list(message)


@router.message(F.text == "📋 My Sheets")
async def btn_my_sheets(message: Message) -> None:
    await _send_list(message)


# ---------------------------------------------------------------------------
# /set_interval <url or name> <seconds>
# ---------------------------------------------------------------------------

@router.message(Command("set_interval"))
async def cmd_set_interval(message: Message) -> None:
    user_id = message.from_user.id
    parts = (message.text or "").split(maxsplit=2)

    if len(parts) < 3:
        await message.answer(
            "Usage: /set_interval <code>&lt;url or name&gt; &lt;seconds&gt;</code>\n"
            "Example: <code>/set_interval Q1 Report 120</code>"
        )
        return

    target = parts[1].strip()
    try:
        seconds = int(parts[2].strip())
    except ValueError:
        await message.answer("❌ Please provide a valid integer number of seconds.")
        return

    if seconds < MIN_POLLING_INTERVAL:
        await message.answer(f"❌ Minimum interval is {MIN_POLLING_INTERVAL}s.")
        return

    # Resolve: try as URL first, then as name
    if target.startswith("http"):
        spreadsheet_id = extract_spreadsheet_id(target)
        if spreadsheet_id is None:
            await message.answer("❌ Invalid Google Sheets URL.")
            return
    else:
        spreadsheet_id = await crud.get_spreadsheet_id_by_name(user_id, target)
        if spreadsheet_id is None:
            await message.answer(f"❌ No tracked spreadsheet found with name <b>{target}</b>.")
            return

    updated = await crud.set_sheet_polling_interval(user_id, spreadsheet_id, seconds)
    if not updated:
        await message.answer("⚠️ That spreadsheet is not in your tracking list.")
        return

    await message.answer(
        f"✅ Polling interval set to <code>{format_interval(seconds)}</code>.",
        reply_markup=main_keyboard(),
    )
    logger.info("User %d set interval %ds for %s", user_id, seconds, spreadsheet_id)
