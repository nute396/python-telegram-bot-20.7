import os
import time
import sqlite3
import logging

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command

# =====================
# CONFIG
# =====================

BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_ID = 5959832681

FACTIONS = ["ДБР", "НПС", "СБС", "НАБС"]

QUESTIONS = [
    "📊 XP у фракції / грі:",
    "💼 Досвід роботи:",
    "⚡ Активність (1-10):",
    "🧠 Адекватність (1-10):",
    "👤 Ім'я:",
    "🎂 Вік:",
    "❓ Чому хочеш вступити?",
]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

# =====================
# DB
# =====================

conn = sqlite3.connect("apps.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    faction TEXT,
    data TEXT,
    status TEXT DEFAULT 'pending'
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    step INTEGER DEFAULT 0,
    answers TEXT DEFAULT '',
    faction TEXT DEFAULT ''
)
""")

conn.commit()

# =====================
# ANTI SPAM
# =====================

cooldowns = {}
COOLDOWN = 3

def anti_spam(uid):
    now = time.time()
    if uid in cooldowns and now - cooldowns[uid] < COOLDOWN:
        return False
    cooldowns[uid] = now
    return True

# =====================
# START
# =====================

@dp.message(Command("start"))
async def start(message: types.Message):
    if not anti_spam(message.from_user.id):
        return

    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=f)] for f in FACTIONS],
        resize_keyboard=True
    )

    await message.answer("🔥 ОФІЦІЙНА СИСТЕМА ЗАЯВОК\n\nОберіть фракцію:", reply_markup=kb)

# =====================
# HANDLE FACTION + FLOW
# =====================

@dp.message(F.text.in_(FACTIONS))
async def choose_faction(message: types.Message):
    user_id = message.from_user.id

    cur.execute(
        "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
        (user_id,)
    )

    cur.execute(
        "UPDATE users SET faction=?, step=1, answers='' WHERE user_id=?",
        (message.text, user_id)
    )
    conn.commit()

    await message.answer(f"📋 Фракція обрана: {message.text}\n\n{QUESTIONS[0]}")

# =====================
# ANSWERS FLOW
# =====================

@dp.message()
async def answers(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    cur.execute("SELECT step, answers, faction FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()

    if not row:
        return

    step, answers, faction = row

    if step == 0:
        return

    answers = answers.split("|") if answers else []
    answers.append(text)

    step += 1

    # next question
    if step <= len(QUESTIONS):
        cur.execute(
            "UPDATE users SET step=?, answers=? WHERE user_id=?",
            (step, "|".join(answers), user_id)
        )
        conn.commit()

        if step < len(QUESTIONS):
            await message.answer(QUESTIONS[step - 1])
            return

    # FINISH APPLICATION
    cur.execute(
        "INSERT INTO applications (user_id, faction, data) VALUES (?, ?, ?)",
        (user_id, faction, "|".join(answers))
    )
    conn.commit()

    app_id = cur.lastrowid

    # format msg
    msg = f"📩 НОВА ЗАЯВКА #{app_id}\n\n"
    msg += f"🏷 Фракція: {faction}\n\n"

    for q, a in zip(QUESTIONS, answers):
        msg += f"{q}\n➡️ {a}\n\n"

    # admin buttons
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="✅ Accept", callback_data=f"acc_{app_id}"),
            types.InlineKeyboardButton(text="❌ Reject", callback_data=f"rej_{app_id}")
        ]
    ])

    await bot.send_message(ADMIN_ID, msg, reply_markup=kb)
    await message.answer("✅ Заявку відправлено! Очікуй рішення.")

    # reset user
    cur.execute("UPDATE users SET step=0, answers='' WHERE user_id=?", (user_id,))
    conn.commit()

# =====================
# ADMIN PANEL
# =====================

@dp.callback_query()
async def admin(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    data = call.data
    action, app_id = data.split("_")

    if action == "acc":
        status = "accepted"
        text = "✅ ACCEPTED"
    else:
        status = "rejected"
        text = "❌ REJECTED"

    cur.execute(
        "UPDATE applications SET status=? WHERE id=?",
        (status, app_id)
    )
    conn.commit()

    await call.message.edit_text(f"{text}\n\nAPP #{app_id}")
    await call.answer()

# =====================
# RUN
# =====================

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
