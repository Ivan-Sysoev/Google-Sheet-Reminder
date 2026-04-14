"""
Google Sheets integration via gspread.
Runs blocking gspread calls in a thread pool to avoid blocking the event loop.
"""

import asyncio
import logging
import re
from functools import partial
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

from bot.config import GOOGLE_API_SCOPES, GOOGLE_CREDENTIALS_PATH

logger = logging.getLogger(__name__)

_client: Optional[gspread.Client] = None

# Regex to extract spreadsheet ID from Google Sheets URL
_SPREADSHEET_ID_RE = re.compile(
    r"https://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9_-]+)"
)


def _get_client() -> gspread.Client:
    global _client
    if _client is None:
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_PATH, scopes=GOOGLE_API_SCOPES)
        _client = gspread.authorize(creds)
    return _client


def extract_spreadsheet_id(url: str) -> Optional[str]:
    """Extract spreadsheet ID from a Google Sheets URL. Returns None on mismatch."""
    m = _SPREADSHEET_ID_RE.search(url)
    return m.group(1) if m else None


def _fetch_spreadsheet_sync(spreadsheet_id: str) -> tuple[str, dict[int, str]]:
    """
    Synchronous: open spreadsheet by ID and return (title, {sheet_id: title}).
    Raises gspread exceptions on auth/access errors.
    """
    client = _get_client()
    spreadsheet = client.open_by_key(spreadsheet_id)
    sheets = {ws.id: ws.title for ws in spreadsheet.worksheets()}
    return spreadsheet.title, sheets


async def fetch_spreadsheet(spreadsheet_id: str) -> tuple[str, dict[int, str]]:
    """
    Async wrapper around _fetch_spreadsheet_sync.
    Returns (spreadsheet_title, {sheet_id: title}).
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, partial(_fetch_spreadsheet_sync, spreadsheet_id)
    )


class SheetsAccessError(Exception):
    """Raised when the bot cannot access the requested spreadsheet."""


class InvalidURLError(Exception):
    """Raised when the provided URL is not a valid Google Sheets URL."""


async def open_spreadsheet(url: str) -> tuple[str, str, dict[int, str]]:
    """
    Validate URL, open spreadsheet, return (spreadsheet_id, title, sheets_snapshot).
    Raises InvalidURLError or SheetsAccessError on failure.
    """
    spreadsheet_id = extract_spreadsheet_id(url)
    if spreadsheet_id is None:
        raise InvalidURLError(f"Cannot extract spreadsheet ID from URL: {url}")

    try:
        title, sheets = await fetch_spreadsheet(spreadsheet_id)
    except gspread.exceptions.NoValidUrlKeyFound:
        raise InvalidURLError(f"Invalid spreadsheet ID derived from URL: {url}")
    except gspread.exceptions.APIError as e:
        raise SheetsAccessError(str(e)) from e
    except Exception as e:
        raise SheetsAccessError(str(e)) from e

    return spreadsheet_id, title, sheets
