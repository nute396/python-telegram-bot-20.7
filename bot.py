мimport os
import time
import sqlite3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# =====================
# CONFIG
# =====================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 123456789  # <-- твій Telegram ID

FACTIONS = {
    "ДБР": -5042162172,
    "НПС": -1003797046749,
    "СБС": -5173873867,
    "НАБС": -5156309034,
}

QUESTIONS = [
    "XP у поліції:",
    "Досвід роботи:",
    "Активність (1-10):",
    "Адекватність (1-10):",
    "Ім'я:",
    "Вік:",
    "Чому хочеш вступити?",
]

# =====================
# DB
# =====================

conn = sqlite3.connect("apps.db", check_same_thread=False)
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
conn.commit()

# =====================
# ANTI SPAM
# =====================

cooldowns = {}
COOLDOWN = 25

def anti_spam(uid):
    now = time.time()
    if uid in cooldowns and now - cooldowns[uid] < COOLDOWN:
        return False
    cooldowns[uid] = now
    return True

# =====================
# STATES
# =====================

CHOICE, ANSWERS = range(2)

logging.basicConfig(level=logging.INFO)

# =====================
# START
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not anti_spam(uid):
        await update.message.reply_text("⏳ Антиспам активний")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("🔎 ДБР", callback_data="ДБР")],
        [InlineKeyboardButton("👮 НПС", callback_data="НПС")],
        [InlineKeyboardButton("🛡 СБС", callback_data="СБС")],
        [InlineKeyboardButton("⚖️ НАБС", callback_data="НАБС")],
    ]

    await update.message.reply_text(
        "🔥 Обери фракцію:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return CHOICE

# =====================
# CHOOSE FACTION
# =====================

async def choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    context.user_data["faction"] = q.data
    context.user_data["answers"] = []
    context.user_data["i"] = 0

    await q.edit_message_text(
        f"📋 Анкета {q.data}\n\n{QUESTIONS[0]}"
    )

    return ANSWERS

# =====================
# ANSWERS
# =====================

async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    answers = context.user_data["answers"]
    i = context.user_data["i"]

    answers.append(text)
    i += 1

    context.user_data["answers"] = answers
    context.user_data["i"] = i

    if i < len(QUESTIONS):
        await update.message.reply_text(QUESTIONS[i])
        return ANSWERS

    faction = context.user_data["faction"]

    # save DB
    cur.execute(
        "INSERT INTO applications (user_id, faction, data) VALUES (?, ?, ?)",
        (update.effective_user.id, faction, str(answers))
    )
    conn.commit()

    app_id = cur.lastrowid

    # build message
    msg = f"📩 ЗАЯВКА #{app_id} ({faction})\n\n"
    for q, a in zip(QUESTIONS, answers):
        msg += f"{q}\n➡️ {a}\n\n"

    # admin buttons
    keyboard = [
        [
            InlineKeyboardButton("✅ Accept", callback_data=f"acc_{app_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"rej_{app_id}")
        ]
    ]

    # send to faction chat
    try:
        await context.bot.send_message(FACTIONS[faction], msg)
    except:
        pass

    # send to admin
    await context.bot.send_message(
        ADMIN_ID,
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await update.message.reply_text("✅ Заявку відправлено!")

    return ConversationHandler.END

# =====================
# ADMIN PANEL
# =====================

async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_ID:
        return

    data = q.data
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

    await q.edit_message_text(f"{text}\n\nAPP #{app_id}")

# =====================
# STATS
# =====================

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

# =====================
# MAIN
# =====================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOICE: [CallbackQueryHandler(choose)],
            ANSWERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, answer)],
        },
        fallbacks=[],
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(admin_buttons))
    app.add_handler(CommandHandler("stats", stats))

    print("🔥 ULTRA BOT RUNNING")
    app.run_polling()

if __name__ == "__main__":
    main()
