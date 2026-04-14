"""
Keyboard builders for reply and inline keyboards.
"""

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# Preset intervals: (seconds, display_label)
INTERVAL_PRESETS: list[tuple[int, str]] = [
    (10,   "10s"),
    (30,   "30s"),
    (60,   "1m"),
    (300,  "5m"),
    (600,  "10m"),
    (900,  "15m"),
    (1200, "20m"),
    (1800, "30m"),
    (3600, "1h"),
]


def format_interval(seconds: int) -> str:
    """Human-readable interval: 10 → '10s', 300 → '5m', 3600 → '1h'."""
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{m}m" if s == 0 else f"{seconds}s"
    h, m = divmod(seconds, 3600)
    return f"{h}h" if m == 0 else f"{seconds // 60}m"


# ---------------------------------------------------------------------------
# Reply keyboard (persistent bottom panel)
# ---------------------------------------------------------------------------

def main_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="📋 My Sheets")
    builder.button(text="➕ Add Sheet")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


# ---------------------------------------------------------------------------
# Inline keyboards
# ---------------------------------------------------------------------------

def list_keyboard(sheets: list[dict]) -> InlineKeyboardMarkup:
    """One manage-button per tracked sheet."""
    builder = InlineKeyboardBuilder()
    for s in sheets:
        name = s["display_name"]
        label = (name[:22] + "…") if len(name) > 22 else name
        builder.button(text=f"⚙️ {label}", callback_data=f"sheet:{s['spreadsheet_id']}")
    builder.adjust(1)
    return builder.as_markup()


def sheet_detail_keyboard(spreadsheet_id: str) -> InlineKeyboardMarkup:
    """Per-sheet actions: set interval, remove, back to list."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⏱ Set Interval", callback_data=f"si:{spreadsheet_id}")
    builder.button(text="🗑 Remove",       callback_data=f"rm:{spreadsheet_id}")
    builder.button(text="‹ Back",          callback_data="list")
    builder.adjust(2, 1)
    return builder.as_markup()


def interval_keyboard(spreadsheet_id: str) -> InlineKeyboardMarkup:
    """Preset interval buttons + custom input + back."""
    builder = InlineKeyboardBuilder()
    for seconds, label in INTERVAL_PRESETS:
        builder.button(text=label, callback_data=f"ci:{spreadsheet_id}:{seconds}")
    builder.button(text="✏️ Custom",  callback_data=f"custom_i:{spreadsheet_id}")
    builder.button(text="‹ Back",     callback_data=f"sheet:{spreadsheet_id}")
    # 9 presets → rows of 3, 3, 3; then custom + back on last row
    builder.adjust(3, 3, 3, 2)
    return builder.as_markup()


def confirm_remove_keyboard(spreadsheet_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Yes, remove", callback_data=f"crm:{spreadsheet_id}")
    builder.button(text="❌ Cancel",      callback_data=f"sheet:{spreadsheet_id}")
    builder.adjust(2)
    return builder.as_markup()
