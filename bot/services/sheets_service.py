"""
Google Sheets integration via Sheets API v4 (HTTP + API key).

Works with any spreadsheet that is publicly accessible
("Anyone with the link can view") — no sharing with a service account needed.
"""

import logging
import re
from typing import Optional

import aiohttp

from bot.config import GOOGLE_API_KEY, SHEETS_API_BASE_URL

logger = logging.getLogger(__name__)

_SPREADSHEET_ID_RE = re.compile(
    r"https://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9_-]+)"
)


class InvalidURLError(Exception):
    """Raised when the provided URL is not a valid Google Sheets URL."""


class SheetsAccessError(Exception):
    """Raised when the spreadsheet cannot be fetched (not public, deleted, bad ID, etc.)."""


def extract_spreadsheet_id(url: str) -> Optional[str]:
    """Extract spreadsheet ID from a Google Sheets URL. Returns None on mismatch."""
    m = _SPREADSHEET_ID_RE.search(url)
    return m.group(1) if m else None


async def fetch_spreadsheet(spreadsheet_id: str) -> tuple[str, dict[int, str]]:
    """
    Fetch spreadsheet title and worksheet list via Sheets API v4.

    Returns:
        (spreadsheet_title, {sheet_id: title})

    Raises:
        SheetsAccessError: if the sheet is not public, not found, or API returns an error.
    """
    url = f"{SHEETS_API_BASE_URL}/{spreadsheet_id}"
    params = {
        "key": GOOGLE_API_KEY,
        "fields": "properties.title,sheets.properties(sheetId,title)",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            data = await resp.json()

            if resp.status != 200:
                error_msg = data.get("error", {}).get("message", str(resp.status))
                raise SheetsAccessError(error_msg)

    title: str = data["properties"]["title"]
    sheets: dict[int, str] = {
        s["properties"]["sheetId"]: s["properties"]["title"]
        for s in data.get("sheets", [])
    }
    return title, sheets


async def open_spreadsheet(url: str) -> tuple[str, str, dict[int, str]]:
    """
    Validate URL, fetch spreadsheet metadata.

    Returns:
        (spreadsheet_id, title, {sheet_id: title})

    Raises:
        InvalidURLError: if the URL doesn't match Google Sheets format.
        SheetsAccessError: if the spreadsheet is not accessible.
    """
    spreadsheet_id = extract_spreadsheet_id(url)
    if spreadsheet_id is None:
        raise InvalidURLError(f"Cannot extract spreadsheet ID from: {url}")

    title, sheets = await fetch_spreadsheet(spreadsheet_id)
    return spreadsheet_id, title, sheets
