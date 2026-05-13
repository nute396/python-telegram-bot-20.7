import os
import asyncio
import logging
import sqlite3
import traceback

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# =====================
# CONFIG
# =====================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 5959832681

FACTIONS = ["ДБР", "НПС", "СБС", "НАБС"]

QUESTIONS = [
    "XP у поліції?",
    "Досвід роботи?",
    "Активність (1-10)?",
    "Адекватність (1-10)?",
    "Ім'я?",
    "Вік?",
    "Чому хочеш вступити?"
]

logging.basicConfig(level=logging.INFO)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# =====================
# DB
# =====================

conn = sqlite3.connect("rpg.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    faction TEXT DEFAULT NULL
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    faction TEXT,
    data TEXT,
    status TEXT DEFAULT 'pending'
)
""")

conn.commit()

# =====================
# LEVEL SYSTEM
# =====================

def add_xp(user_id, amount=10):
    cur.execute("SELECT xp, level FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()

    if not row:
        cur.execute("INSERT INTO users (user_id, xp, level) VALUES (?, 0, 1)", (user_id,))
        conn.commit()
        return

    xp, level = row
    xp += amount

    if xp >= level * 100:
        level += 1
        xp = 0

    cur.execute(
        "UPDATE users SET xp=?, level=? WHERE user_id=?",
        (xp, level, user_id)
    )
    conn.commit()

# =====================
# START RPG PROFILE
# =====================

@dp.message(Command("start"))
async def start(message: Message):
    uid = message.from_user.id

    cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
    conn.commit()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Подати заявку", callback_data="apply")],
        [InlineKeyboardButton(text="👤 Профіль", callback_data="profile")]
    ])

    await message.answer("⚔️ RPG БОТ ВІТАЄ\nОбери дію:", reply_markup=kb)

# =====================
# PROFILE
# =====================

@dp.callback_query(lambda c: c.data == "profile")
async def profile(call: CallbackQuery):
    uid = call.from_user.id

    cur.execute("SELECT xp, level, faction FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone()

    xp, level, faction = row

    await call.message.edit_text(
        f"👤 Профіль\n\n"
        f"⭐ Level: {level}\n"
        f"⚡ XP: {xp}/100\n"
        f"🏛 Фракція: {faction or 'немає'}"
    )

# =====================
# APPLY SYSTEM
# =====================

user_state = {}

@dp.callback_query(lambda c: c.data == "apply")
async def apply(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f, callback_data=f"f_{f}")]
        for f in FACTIONS
    ])

    await call.message.edit_text("🏛 Обери фракцію:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("f_"))
async def faction(call: CallbackQuery):
    faction = call.data[2:]
    uid = call.from_user.id

    user_state[uid] = {
        "faction": faction,
        "answers": [],
        "q": 0
    }

    await call.message.edit_text(f"📋 Анкета {faction}\n\n{QUESTIONS[0]}")

# =====================
# ANSWERS FLOW
# =====================

@dp.message()
async def answers(message: Message):
    uid = message.from_user.id

    if uid not in user_state:
        add_xp(uid, 5)
        return

    state = user_state[uid]

    state["answers"].append(message.text)
    state["q"] += 1

    add_xp(uid, 10)

    if state["q"] < len(QUESTIONS):
        await message.answer(QUESTIONS[state["q"]])
        return

    faction = state["faction"]
    answers = state["answers"]

    cur.execute(
        "INSERT INTO applications (user_id, faction, data) VALUES (?, ?, ?)",
        (uid, faction, str(answers))
    )
    conn.commit()

    app_id = cur.lastrowid

    text = f"📩 ЗАЯВКА #{app_id}\n🏛 {faction}\n\n"
    for q, a in zip(QUESTIONS, answers):
        text += f"{q}\n➡️ {a}\n\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Accept", callback_data=f"a_{app_id}"),
            InlineKeyboardButton(text="❌ Reject", callback_data=f"r_{app_id}")
        ]
    ])

    await message.answer("📨 Заявку відправлено!")

    await bot.send_message(ADMIN_ID, text, reply_markup=kb)

    del user_state[uid]

# =====================
# ADMIN
# =====================

@dp.callback_query(lambda c: c.data.startswith("a_") or c.data.startswith("r_"))
async def admin(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    action, app_id = call.data.split("_")

    status = "accepted" if action == "a" else "rejected"

    cur.execute(
        "UPDATE applications SET status=? WHERE id=?",
        (status, app_id)
    )
    conn.commit()

    await call.message.edit_text(f"{status.upper()} #{app_id}")

# =====================
# SAFE RUN
# =====================

async def main():
    while True:
        try:
            logging.info("🚀 RPG BOT STARTED")

            await dp.start_polling(
                bot,
                skip_updates=True
            )

        except Exception as e:
            logging.error("💥 CRASH - RESTART")
            logging.error(e)
            logging.error(traceback.format_exc())
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())
