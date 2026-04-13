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
from modules.catchup import CatchupModule
from modules.onboarding import OnboardingModule
from modules.science import ScienceModule
from modules.jobs import JobsModule
from modules.podcast import cmd_podcast
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).parent.parent))
from shared.token_logger import get_stats
from modules.notebooklm import cmd_notebooks
from modules.curriculum import (
    cmd_curriculum, cmd_curriculum_item, cmd_done,
    cmd_start_topic, handle_curriculum_callback, cmd_cur_add,
)

import sys as _sys
_sys.path.insert(0, os.path.expanduser("~/.openclaw/workspace"))
from shared.logger import setup_logging
setup_logging(agent="sam")  # без файлу — systemd journal достатньо
logger = logging.getLogger("sam")

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
OWNER_CHAT_ID = int(os.environ["OWNER_CHAT_ID"])

# ── Модулі ─────────────────────────────────────────────────────────────────────

digest = DigestModule(owner_chat_id=OWNER_CHAT_ID)
science = ScienceModule(owner_chat_id=OWNER_CHAT_ID)
catchup = CatchupModule(owner_chat_id=OWNER_CHAT_ID)
onboarding = OnboardingModule(owner_chat_id=OWNER_CHAT_ID)
jobs = JobsModule(owner_chat_id=OWNER_CHAT_ID)

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



async def cmd_cost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != OWNER_CHAT_ID:
        return
    stats = get_stats(since_days=30)
    total = stats["total_cost_usd"]
    calls = stats["total_calls"]
    lines = [f"💰 Витрати за 30 днів: ${total:.4f}", f"📞 Всього викликів: {calls}", ""]
    for agent, d in sorted(stats["by_agent"].items(), key=lambda x: -x[1]["cost_usd"]):
        lines.append(f"• {agent}: ${d['cost_usd']:.4f} ({d['calls']} calls)")
        lines.append(f"  in={d['input']} out={d['output']} cache={d['cache_read']}")
    await update.message.reply_text("\n".join(lines) if lines else "Даних ще немає")

async def cmd_digest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != OWNER_CHAT_ID:
        return
    await update.message.reply_text("⏳ Збираю AI дайджест, хвилинку...")
    try:
        await digest.send(context.application)
    except Exception as e:
        logger.error(f"Digest error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Помилка дайджесту: {e}")


async def cmd_science(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != OWNER_CHAT_ID:
        return
    await update.message.reply_text("⏳ Збираю науковий дайджест...")
    await science.send(context.application)


async def cmd_catchup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != OWNER_CHAT_ID:
        return
    args = context.args
    period = args[0] if args else "7d"
    from modules.catchup import PERIOD_OPTIONS
    if period not in PERIOD_OPTIONS:
        await update.message.reply_text(
            "Використання: /catchup [період]\n"
            "Доступні: 3d, 7d, 14d, 30d, 60d, 180d, 365d"
        )
        return
    _, days = PERIOD_OPTIONS[period]
    await catchup.send_catchup(update, days)


async def cmd_jobs(update, context):
    if update.effective_chat.id != OWNER_CHAT_ID:
        return
    await jobs.send_on_command(update, context.application)


async def cmd_onboarding(update, context):
    if update.effective_chat.id != OWNER_CHAT_ID:
        return
    await onboarding.send_menu(update)


async def handle_onboarding_callback(update, context):
    await onboarding.handle_callback(update, context)


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await digest.handle_feedback(update)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != OWNER_CHAT_ID:
        return
    text = update.message.text.strip()
    if not text:
        return

    await update.message.chat.send_action("typing")
    answer = digest.call_claude_chat(text, max_tokens=1500)
    await update.message.reply_text(answer or "Не зміг відповісти, спробуй ще раз.")


async def _extract_interests(user_text: str, bot_answer: str):
    try:
        prompt = (
            "Analyze this conversation fragment and extract any AI/ML/programming topics "
            "the user seems interested in or is asking about.\n\n"
            f"User: {user_text}\nAssistant: {bot_answer}\n\n"
            "Return ONLY a JSON array of short topic strings (2-4 words max each). "
            "Example: [\"RAG\", \"vector search\", \"streaming responses\"] "
            "If no clear technical interest — return empty array []. "
            "No explanation, just the JSON array."
        )
        result = digest.call_claude(prompt, smart=False)
        if not result:
            return
        import json, re
        match = re.search(r"\[.*?\]", result, re.DOTALL)
        if not match:
            return
        interests = json.loads(match.group())
        if interests:
            digest.update_interests(interests)
            logger.info(f"Interests updated: {interests}")
    except Exception as e:
        logger.warning(f"Interest extraction failed: {e}")


# ── Scheduled jobs ─────────────────────────────────────────────────────────────

async def job_daily_digest(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running daily digest job")
    await digest.send(context.application)


async def job_weekly_jobs(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running weekly jobs analysis")
    await jobs.send(context.application)


async def job_weekly_science(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running weekly science job")
    await science.send(context.application)


# ── Main ───────────────────────────────────────────────────────────────────────

async def cmd_getfileid(update, context):
    msg = update.message.reply_to_message
    if not msg or not msg.audio:
        await update.message.reply_text("Відповідай на аудіо повідомлення командою /getfileid")
        return
    await update.message.reply_text(f"`{msg.audio.file_id}`", parse_mode="Markdown")

def main():
    async def post_init(application):
        from telegram import BotCommand
        await application.bot.set_my_commands([
            BotCommand("start",      "👋 Привіт і список команд"),
            BotCommand("digest",     "🤖 AI дайджест за 24 год"),
            BotCommand("science",    "🔬 Науковий дайджест тижня"),
            BotCommand("cur",        "📚 План навчання AI"),
            BotCommand("catchup",    "📊 Catchup за період"),
            BotCommand("jobs",       "💼 Ринок праці"),
            BotCommand("onboarding", "🗺️ Онбординг"),
            BotCommand("profile",    "👤 Профіль інтересів"),
            BotCommand("podcast",    "🎙️ Подкаст по curriculum"),
            BotCommand("notebooks",  "📓 Мої NotebookLM notebooks"),
        ])

    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("cost", cmd_cost))
    app.add_handler(CommandHandler("digest", cmd_digest))
    app.add_handler(CommandHandler("science", cmd_science))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("cur", cmd_curriculum))
    app.add_handler(CommandHandler("cur_item", cmd_curriculum_item))
    app.add_handler(CommandHandler("podcast", cmd_podcast))
    app.add_handler(CommandHandler("notebooks", cmd_notebooks))
    app.add_handler(CommandHandler("getfileid", cmd_getfileid))
    app.add_handler(CommandHandler("done", cmd_done))
    app.add_handler(CommandHandler("cur_add", cmd_cur_add))
    app.add_handler(CommandHandler("start_topic", cmd_start_topic))
    app.add_handler(CommandHandler("catchup", cmd_catchup))
    app.add_handler(CommandHandler("jobs", cmd_jobs))
    app.add_handler(CommandHandler("onboarding", cmd_onboarding))
    app.add_handler(CallbackQueryHandler(handle_onboarding_callback, pattern=r"^onb_"))

    # Callbacks
    app.add_handler(CallbackQueryHandler(handle_curriculum_callback, pattern=r"^cur_"))
    app.add_handler(CallbackQueryHandler(handle_curriculum_callback, pattern=r"^cur_nbtoggle|cur_nbrun"))
    app.add_handler(CallbackQueryHandler(handle_feedback, pattern=r"^(like|dislike|detail)\|"))

    # Free text
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Jobs — Kyiv time UTC+3
    jq = app.job_queue
    jq.run_daily(job_daily_digest, time=time(6, 0, 0))        # 09:00 Kyiv
    jq.run_daily(job_weekly_science, time=time(7, 0, 0), days=(5,))  # субота 10:00 Kyiv
    jq.run_daily(job_weekly_jobs, time=time(7, 0, 0), days=(6,))  # неділя 10:00 Kyiv

    logger.info("Sam is running 🚀")
    app.run_polling()


if __name__ == "__main__":
    main()
