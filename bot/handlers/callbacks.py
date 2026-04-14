"""
Inline keyboard callback handlers + FSM for custom interval input.
"""

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from bot.config import MIN_POLLING_INTERVAL
from bot.db import crud
from bot.handlers.keyboards import (
    confirm_remove_keyboard,
    format_interval,
    interval_keyboard,
    list_keyboard,
    main_keyboard,
    sheet_detail_keyboard,
)

logger = logging.getLogger(__name__)
router = Router()


# ---------------------------------------------------------------------------
# FSM states
# ---------------------------------------------------------------------------

class IntervalInput(StatesGroup):
    waiting = State()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _list_text_and_keyboard(user_id: int) -> tuple[str, InlineKeyboardMarkup | None]:
    sheets = await crud.get_user_tracked_sheets(user_id)
    if not sheets:
        return "You have no tracked spreadsheets.\nUse ➕ Add Sheet to add one.", None
    lines = [
        f"{i + 1}. <b>{s['display_name']}</b> — every {format_interval(s['polling_interval'])}"
        for i, s in enumerate(sheets)
    ]
    text = "📋 <b>Your tracked spreadsheets:</b>\n\n" + "\n".join(lines)
    return text, list_keyboard(sheets)


# ---------------------------------------------------------------------------
# /cancel — clears any active FSM state
# ---------------------------------------------------------------------------

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Cancelled.", reply_markup=main_keyboard())


# ---------------------------------------------------------------------------
# Navigate back to list
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "list")
async def cb_list(callback: CallbackQuery) -> None:
    text, keyboard = await _list_text_and_keyboard(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


# ---------------------------------------------------------------------------
# Sheet detail view
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("sheet:"))
async def cb_sheet_detail(callback: CallbackQuery) -> None:
    spreadsheet_id = callback.data.split(":", 1)[1]
    sheets = await crud.get_user_tracked_sheets(callback.from_user.id)
    sheet = next((s for s in sheets if s["spreadsheet_id"] == spreadsheet_id), None)

    if sheet is None:
        await callback.answer("Sheet not found.", show_alert=True)
        return

    text = (
        f"<b>{sheet['display_name']}</b>\n\n"
        f"Polling every <code>{format_interval(sheet['polling_interval'])}</code>"
    )
    await callback.message.edit_text(text, reply_markup=sheet_detail_keyboard(spreadsheet_id))
    await callback.answer()


# ---------------------------------------------------------------------------
# Set interval — show preset picker
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("si:"))
async def cb_show_interval_picker(callback: CallbackQuery) -> None:
    spreadsheet_id = callback.data.split(":", 1)[1]
    await callback.message.edit_text(
        "Choose polling interval:",
        reply_markup=interval_keyboard(spreadsheet_id),
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Set interval — apply preset
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("ci:"))
async def cb_confirm_interval(callback: CallbackQuery) -> None:
    _, spreadsheet_id, seconds_str = callback.data.split(":", 2)
    seconds = int(seconds_str)
    user_id = callback.from_user.id

    updated = await crud.set_sheet_polling_interval(user_id, spreadsheet_id, seconds)
    if not updated:
        await callback.answer("Sheet not found.", show_alert=True)
        return

    sheets = await crud.get_user_tracked_sheets(user_id)
    sheet = next((s for s in sheets if s["spreadsheet_id"] == spreadsheet_id), None)
    name = sheet["display_name"] if sheet else spreadsheet_id

    await callback.message.edit_text(
        f"<b>{name}</b>\n\nPolling every <code>{format_interval(seconds)}</code>",
        reply_markup=sheet_detail_keyboard(spreadsheet_id),
    )
    await callback.answer(f"✅ Set to {format_interval(seconds)}")


# ---------------------------------------------------------------------------
# Set interval — custom value via FSM
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("custom_i:"))
async def cb_custom_interval(callback: CallbackQuery, state: FSMContext) -> None:
    spreadsheet_id = callback.data.split(":", 1)[1]
    await state.set_state(IntervalInput.waiting)
    await state.update_data(spreadsheet_id=spreadsheet_id)
    await callback.message.edit_text(
        f"Enter interval in seconds (min {MIN_POLLING_INTERVAL}):\n"
        "Send /cancel to go back."
    )
    await callback.answer()


@router.message(IntervalInput.waiting)
async def fsm_interval_input(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    spreadsheet_id = data["spreadsheet_id"]
    user_id = message.from_user.id

    try:
        seconds = int((message.text or "").strip())
    except ValueError:
        await message.answer("Please enter a valid number (e.g. 120):")
        return

    if seconds < MIN_POLLING_INTERVAL:
        await message.answer(f"Minimum is {MIN_POLLING_INTERVAL}s. Try again:")
        return

    await state.clear()
    await crud.set_sheet_polling_interval(user_id, spreadsheet_id, seconds)

    sheets = await crud.get_user_tracked_sheets(user_id)
    sheet = next((s for s in sheets if s["spreadsheet_id"] == spreadsheet_id), None)
    name = sheet["display_name"] if sheet else spreadsheet_id

    await message.answer(
        f"✅ Interval for <b>{name}</b> set to <code>{format_interval(seconds)}</code>",
        reply_markup=main_keyboard(),
    )


# ---------------------------------------------------------------------------
# Remove — confirm prompt
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("rm:"))
async def cb_remove_prompt(callback: CallbackQuery) -> None:
    spreadsheet_id = callback.data.split(":", 1)[1]
    sheets = await crud.get_user_tracked_sheets(callback.from_user.id)
    sheet = next((s for s in sheets if s["spreadsheet_id"] == spreadsheet_id), None)
    name = sheet["display_name"] if sheet else spreadsheet_id

    await callback.message.edit_text(
        f"Remove <b>{name}</b> from tracking?",
        reply_markup=confirm_remove_keyboard(spreadsheet_id),
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Remove — confirmed
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("crm:"))
async def cb_remove_confirmed(callback: CallbackQuery) -> None:
    spreadsheet_id = callback.data.split(":", 1)[1]
    await crud.remove_tracked_sheet(callback.from_user.id, spreadsheet_id)

    text, keyboard = await _list_text_and_keyboard(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer("✅ Removed")
