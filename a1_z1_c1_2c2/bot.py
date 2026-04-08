import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN, ADMIN_IDS, LTC_ADDRESSES
from database import init_db, seed_addresses
from handlers import user, admin
from setup_defaults import setup as run_setup_defaults
import aiosqlite

from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

async def main():
    logging.basicConfig(level=logging.INFO)
    
    # Init Database Tables
    await init_db()
    
    # Auto-Setup defaults if empty
    async with aiosqlite.connect("bot_database.sqlite") as db:
        async with db.execute("SELECT COUNT(*) FROM locations") as cursor:
            count = (await cursor.fetchone())[0]
            if count == 0:
                logging.info("Empty database detected. Running setup_defaults...")
                await run_setup_defaults()
    
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Include routers
    dp.include_router(admin.router)
    dp.include_router(user.router)

    logging.info("A1 Z1 C1 2C2 Bot started!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
