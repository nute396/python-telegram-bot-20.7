import os
import time
import sqlite3
import logging
import traceback

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# =========================
# CONFIG (SAFE)
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_TOKEN_HERE")
ADMIN_ID = 5959832681

FACTIONS = {
    "ДБР": -5042162172,
    "НПС": -1003797046749,
    "СБС": -5173873867,
    "НАБС": -5156309034,
}

QUESTIONS = [
    "XP у поліції?",
    "Досвід роботи?",
    "Активність (1-10)?",
    "Адекватність (1-10)?",
    "Ім'я?",
    "Вік?",
    "Чому хочеш вступити?",
]

logging.basicConfig(level=logging.INFO)

# =========================
# DB SAFE INIT
# =========================

conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    faction TEXT,
    data TEXT,
    status TEXT DEFAULT 'pending'
)
""")
conn.commit()

# =========================
# ANTI-SPAM
# =========================

cooldowns = {}
COOLDOWN = 20

def anti_spam(uid):
    now = time.time()
    if uid in cooldowns and now - cooldowns[uid] < COOLDOWN:
        return False
    cooldowns[uid] = now
    return True

# =========================
# STATES
# =========================

CHOOSE, ANSWER = range(2)

# =========================
# SAFE START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = update.effective_user.id

        if not anti_spam(uid):
            await update.message.reply_text("⏳ Антиспам активний")
            return ConversationHandler.END

        keyboard = [
            [InlineKeyboardButton("🔎 ДБР", callback_data="ДБР"),
             InlineKeyboardButton("👮 НПС", callback_data="НПС")],
            [InlineKeyboardButton("🛡 СБС", callback_data="СБС"),
             InlineKeyboardButton("⚖️ НАБС", callback_data="НАБС")],
        ]

        await update.message.reply_text(
            "🔥 Обери фракцію:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        return CHOOSE

    except Exception:
        traceback.print_exc()
        return ConversationHandler.END


# =========================
# CHOOSE FACTION
# =========================

async def choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        q = update.callback_query
        await q.answer()

        context.user_data["faction"] = q.data
        context.user_data["answers"] = []
        context.user_data["i"] = 0

        await q.edit_message_text(f"📋 Починаємо анкету {q.data}\n\n{QUESTIONS[0]}")

        return ANSWER

    except Exception:
        traceback.print_exc()
        return ConversationHandler.END


# =========================
# ANSWERS FLOW
# =========================

async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text

        i = context.user_data.get("i", 0)
        answers = context.user_data.get("answers", [])

        answers.append(text)
        i += 1

        context.user_data["i"] = i
        context.user_data["answers"] = answers

        if i < len(QUESTIONS):
            await update.message.reply_text(QUESTIONS[i])
            return ANSWER

        # =========================
        # FINAL SAFE BUILD
        # =========================

        faction = context.user_data.get("faction", "UNKNOWN")
        user = update.effective_user

        msg = f"📩 НОВА ЗАЯВКА ({faction})\n"
        msg += f"User: @{user.username or 'no_username'}\n\n"

        for q, a in zip(QUESTIONS, answers):
            msg += f"{q}\n➡️ {a}\n\n"

        # save DB safely
        try:
            cur.execute(
                "INSERT INTO applications (user_id, username, faction, data) VALUES (?, ?, ?, ?)",
                (user.id, user.username, faction, str(answers))
            )
            conn.commit()
            app_id = cur.lastrowid
        except Exception:
            traceback.print_exc()
            app_id = 0

        # admin buttons
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Accept", callback_data=f"acc_{app_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"rej_{app_id}")
            ]
        ])

        # send to faction SAFE
        try:
            chat_id = FACTIONS.get(faction)
            if chat_id:
                await context.bot.send_message(chat_id, msg)
        except Exception:
            traceback.print_exc()

        # send to admin SAFE
        try:
            await context.bot.send_message(ADMIN_ID, msg, reply_markup=keyboard)
        except Exception:
            traceback.print_exc()

        await update.message.reply_text("✅ Заявку відправлено!")

        return ConversationHandler.END

    except Exception:
        traceback.print_exc()
        return ConversationHandler.END


# =========================
# ADMIN PANEL SAFE
# =========================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        q = update.callback_query
        await q.answer()

        if update.effective_user.id != ADMIN_ID:
            return

        data = q.data
        action, app_id = data.split("_")

        status = "accepted" if action == "acc" else "rejected"

        try:
            cur.execute("UPDATE applications SET status=? WHERE id=?", (status, app_id))
            conn.commit()
        except Exception:
            traceback.print_exc()

        await q.edit_message_text(f"📌 APP #{app_id}\nSTATUS: {status}")

    except Exception:
        traceback.print_exc()


# =========================
# STATS
# =========================

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.effective_user.id != ADMIN_ID:
            return

        cur.execute("SELECT status FROM applications")
        rows = cur.fetchall()

        total = len(rows)
        acc = len([r for r in rows if r[0] == "accepted"])
        rej = len([r for r in rows if r[0] == "rejected"])

        await update.message.reply_text(
            f"📊 STATS\n\nTotal: {total}\nAccepted: {acc}\nRejected: {rej}"
        )

    except Exception:
        traceback.print_exc()


# =========================
# MAIN SAFE CORE
# =========================

def main():
    if not BOT_TOKEN or BOT_TOKEN == "PUT_TOKEN_HERE":
        print("❌ BOT TOKEN NOT SET")
        return

    try:
        app = Application.builder().token(BOT_TOKEN).build()

        conv = ConversationHandler(
            entry_points=[CommandHandler("start", start)],
            states={
                CHOOSE: [CallbackQueryHandler(choose)],
                ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, answer)],
            },
            fallbacks=[],
        )

        app.add_handler(conv)
        app.add_handler(CallbackQueryHandler(admin))
        app.add_handler(CommandHandler("stats", stats))

        print("🔥 ULTRA BOT RUNNING 24/7 SAFE MODE")
        app.run_polling(drop_pending_updates=True)

    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    main()
