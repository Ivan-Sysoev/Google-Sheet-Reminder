"""
Access control middleware.

Blocks any update from users not listed in allowed_users.
Replies with a contact link to the creator for Messages;
answers with an alert for CallbackQueries.
"""

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.config import CREATOR_CONTACT
from bot.db import access_crud as crud


class AccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None or await crud.is_user_allowed(user.id):
            return await handler(event, data)

        if isinstance(event, Message):
            await event.answer(
                f"⛔ You don't have access to this bot.\n\n"
                f"Contact the creator to request access: {CREATOR_CONTACT}",
                disable_web_page_preview=True,
            )
        elif isinstance(event, CallbackQuery):
            await event.answer(
                f"⛔ Access denied. Contact: {CREATOR_CONTACT}",
                show_alert=True,
            )

        return None
