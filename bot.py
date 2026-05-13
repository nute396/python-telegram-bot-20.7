import os
import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

# =====================
# SAFETY CONFIG
# =====================

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не знайдено в env")

ADMIN_ID = 5959832681

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# =====================
# BOT INIT
# =====================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# =====================
# DB SAFE INIT
# =====================

def init_db():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT
        )
    """)
    conn.commit()
    return conn

conn = init_db()

# =====================
# SAFE EXEC WRAPPER (АНТИ-КРАШ)
# =====================

def safe(func):
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logging.error(f"Handler error: {e}")
    return wrapper

# =====================
# HANDLERS
# =====================

@dp.message(Command("start"))
@safe
async def start(message: Message):
    await message.answer(
        "🔥 Бот працює стабільно\n"
        "Напиши щось"
    )

@dp.message()
@safe
async def echo(message: Message):
    text = message.text

    # save safely
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO logs (user_id, text) VALUES (?, ?)",
            (message.from_user.id, text)
        )
        conn.commit()
    except Exception as e:
        logging.error(f"DB error: {e}")

    await message.answer(f"✔️ Отримав: {text}")

# =====================
# GLOBAL ERROR PROTECTION
# =====================

async def on_startup():
    logging.info("🚀 BOT STARTED SUCCESSFULLY")

async def main():
    try:
        await dp.start_polling(
            bot,
            skip_updates=True,
            on_startup=on_startup
        )
    except Exception as e:
        logging.critical(f"FATAL CRASH PREVENTED: {e}")
        await asyncio.sleep(3)
        await main()  # auto-restart loop

if __name__ == "__main__":
    asyncio.run(main())
