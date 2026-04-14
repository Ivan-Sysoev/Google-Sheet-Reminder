"""
Bot entrypoint.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import BOT_TOKEN
from bot.db.crud import init_db
from bot.handlers.callbacks import router as callbacks_router
from bot.handlers.commands import router as commands_router
from bot.services.polling_service import polling_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    await init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Callbacks first so inline buttons are handled before fallback text handlers
    dp.include_router(callbacks_router)
    dp.include_router(commands_router)

    polling_task = asyncio.create_task(polling_loop(bot))

    try:
        logger.info("Starting bot")
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
