import os
import logging
from datetime import time

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from modules.digest import DigestModule
from modules.science import ScienceModule
from modules.curriculum import (
    cmd_curriculum, cmd_curriculum_item, cmd_done,
    cmd_start_topic, handle_curriculum_callback,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("sam")

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
OWNER_CHAT_ID = int(os.environ["OWNER_CHAT_ID"])

# ── Модулі ─────────────────────────────────────────────────────────────────────

digest = DigestModule(owner_chat_id=OWNER_CHAT_ID)
science = ScienceModule(owner_chat_id=OWNER_CHAT_ID)

# ── Core handlers ──────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привіт, я Sam — твій персональний агент.\n\n"
        "Що вмію зараз:\n"
        "🤖 /digest — AI дайджест (останні 24 год)\n"
        "🔬 /science — науковий дайджест тижня\n"
        "📊 /profile — твій профіль інтересів\n"
        "📚 /cur — план навчання AI\n\n"
        "Просто пиши мені — запам'ятаю побажання.\n"
        "Більше функцій з'явиться згодом 🚀"
    )


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != OWNER_CHAT_ID:
        return
    await digest.send_profile(update)


async def cmd_digest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != OWNER_CHAT_ID:
        return
    await update.message.reply_text("⏳ Збираю AI дайджест, хвилинку...")
    await digest.send(context.application)


async def cmd_science(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != OWNER_CHAT_ID:
        return
    await update.message.reply_text("⏳ Збираю науковий дайджест...")
    await science.send(context.application)


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await digest.handle_feedback(update)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вільний текст → зберігаємо як побажання до профілю"""
    if update.effective_chat.id != OWNER_CHAT_ID:
        return
    text = update.message.text.strip()
    if len(text) > 10:
        digest.add_note(text)
        await update.message.reply_text("📝 Записав! Врахую при наступному дайджесті.")


# ── Scheduled jobs ─────────────────────────────────────────────────────────────

async def job_daily_digest(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running daily digest job")
    await digest.send(context.application)


async def job_weekly_science(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running weekly science job")
    await science.send(context.application)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("digest", cmd_digest))
    app.add_handler(CommandHandler("science", cmd_science))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("cur", cmd_curriculum))
    app.add_handler(CommandHandler("cur_item", cmd_curriculum_item))
    app.add_handler(CommandHandler("done", cmd_done))
    app.add_handler(CommandHandler("start_topic", cmd_start_topic))

    # Callbacks
    app.add_handler(CallbackQueryHandler(handle_curriculum_callback, pattern=r"^cur_(start|done)\|"))
    app.add_handler(CallbackQueryHandler(handle_feedback, pattern=r"^(like|dislike)\|"))

    # Free text
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Jobs — Kyiv time UTC+3
    jq = app.job_queue
    jq.run_daily(job_daily_digest, time=time(6, 0, 0))        # 09:00 Kyiv
    jq.run_daily(job_weekly_science, time=time(7, 0, 0), days=(5,))  # субота 10:00 Kyiv

    logger.info("Sam is running 🚀")
    app.run_polling()


if __name__ == "__main__":
    main()
