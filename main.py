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
import sys as _sys, os as _os
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).parent.parent))
from shared.token_tracker import TokenTracker as _TokenTracker
_cost_tracker = _TokenTracker(
    log_path=_os.path.expanduser("~/.openclaw/workspace/shared/token_log.jsonl"),
    agent="sam",
)
from modules.notebooklm import cmd_notebooks
from modules.curriculum import (
    cmd_curriculum, cmd_curriculum_item, cmd_done,
    cmd_start_topic, handle_curriculum_callback, cmd_cur_add,
    CURRICULUM,
)
from shared.hub_renderer import hub_page
from modules.state_manager import touch_activity

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
    # Deep link handling: /start gen_1 або /start tts_1
    args = context.args
    if args:
        param = args[0]
        if param.startswith("gen_") and param[4:].isdigit():
            context.args = [param[4:]]
            await cmd_gen(update, context)
            return
        if param.startswith("tts_") and param[4:].isdigit():
            await cmd_tts_play(update, context, int(param[4:]))
            return
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



async def cmd_hub(update, context):
    if update.effective_chat.id != OWNER_CHAT_ID:
        return
    from modules.curriculum import _get as _get_cur, load_state as _load_cur_state
    _cur_inst = _get_cur()
    _cur_state = _load_cur_state()
    _profile = _cur_inst.load_profile()
    all_topics = _cur_inst.get_full_curriculum(_cur_state, _profile)
    text, kb = hub_page(all_topics, page=0, data_dir=_cur_inst.data_dir)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)

async def handle_hub_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("hub_page|"):
        page = int(data.split("|")[1])
        from modules.curriculum import _get as _get_cur2, load_state as _load_cur_state2
        _cur_inst2 = _get_cur2()
        _cur_state2 = _load_cur_state2()
        _profile2 = _cur_inst2.load_profile()
        _all_topics2 = _cur_inst2.get_full_curriculum(_cur_state2, _profile2)
        text, kb = hub_page(_all_topics2, page=page, data_dir=_cur_inst2.data_dir)
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
        return

    if data.startswith("hub_podcast|"):
        tid = data.split("|")[1]
        await query.message.reply_text(f"\U0001f399 Запускаю подкаст для теми {tid}...")
        from modules.podcast import cmd_podcast
        context.args = [tid]
        await cmd_podcast(update, context)
        return
    if data.startswith("hub_gen|"):
        tid = int(data.split("|")[1])
        context.args = [str(tid)]
        await cmd_gen(update, context)
        return
    if data.startswith("hub_tts|"):
        tid = int(data.split("|")[1])
        await cmd_tts_play(update, context, tid)
        return
    if data.startswith("hub_gen|"):
        tid = int(data.split("|")[1])
        context.args = [str(tid)]
        await cmd_gen(update, context)
        return
    if data.startswith("hub_tts|"):
        tid = int(data.split("|")[1])
        await cmd_tts_play(update, context, tid)
        return

async def cmd_cost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != OWNER_CHAT_ID:
        return
    s = _cost_tracker.get_stats(days=30)
    if not s:
        await update.message.reply_text("Даних ще немає")
        return
    lines = [
        f"💰 Витрати за 30 днів: ${s['total_cost']:.4f}",
        f"📞 Запитів: {s['total_requests']}",
        f"🗃 Кеш: {s['cache_hit_rate']}% | зекономлено: ${s['total_saved']:.4f}",
        f"📈 in={s['total_input']:,} out={s['total_output']:,} cache_r={s['total_cache_read']:,}",
    ]
    await update.message.reply_text("\n".join(lines))

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


async def handle_chat_with_tools(update, text: str) -> str:
    """Agentic loop: chat з SAM_TOOLS, до 3 ітерацій tool use."""
    from shared.agent_base import client, MODEL_SMART
    from core.tools import SAM_TOOLS, execute_tool
    from modules.curriculum import _get as _get_cur

    inst = _get_cur()
    data_dir = inst.data_dir
    system = digest._build_system(include_memory=True, include_conversation=False)
    messages = [{"role": "user", "content": text}]

    for iteration in range(3):
        response = client.messages.create(
            model=MODEL_SMART,
            max_tokens=1500,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            tools=SAM_TOOLS,
        )

        tool_calls = [b for b in response.content if b.type == "tool_use"]

        if not tool_calls:
            # Фінальна відповідь
            texts = [b.text for b in response.content if b.type == "text"]
            return texts[-1] if texts else ""

        logger.info(f"Tool use iteration {iteration+1}: {[t.name for t in tool_calls]}")

        # Виконуємо tools
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for tc in tool_calls:
            result = execute_tool(tc.name, tc.input, data_dir)
            logger.info(f"Tool {tc.name} -> {result[:80]}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": result,
            })
        messages.append({"role": "user", "content": tool_results})

    # Якщо loop не завершився — просто звичайний чат
    return digest.call_claude_chat(text, max_tokens=1500)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != OWNER_CHAT_ID:
        return
    text = update.message.text.strip()
    if not text:
        return

    from modules.router import route_message
    route = route_message(text)
    intent = route.get("intent", "chat")
    confidence = route.get("confidence", 0.5)

    logger.info(f"Router: intent={intent} conf={confidence:.2f} text={text[:40]}")

    await update.message.chat.send_action("typing")
    touch_activity()

    if confidence >= 0.5:
        # Важкі генерації — прямі команди
        if intent == "digest":
            await cmd_digest(update, context); return
        elif intent == "science":
            await cmd_science(update, context); return
        elif intent == "catchup":
            await cmd_catchup(update, context); return
        elif intent == "jobs":
            await cmd_jobs(update, context); return
        elif intent == "cost":
            await cmd_cost(update, context); return
        # hub, curriculum, notebooks — через agentic loop з tools

    # Fallback — agentic chat з tools
    answer = await handle_chat_with_tools(update, text)
    if answer:
        await update.message.reply_text(answer)
    else:
        await update.message.reply_text("Не зміг відповісти, спробуй ще раз.")


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

# Глобальний set активних тасків генерації (topic_id)
_active_gen_tasks: set = set()

async def startup_check(application):
    """При старті відновлює перервані генерації."""
    import json
    import asyncio
    from modules.curriculum import _get as _get_cur, load_state as _load_state
    from shared.notebooklm_module import load_nb_state

    inst = _get_cur()
    nb_state_path = inst.data_dir / "notebooklm_notebooks.json"
    if not nb_state_path.exists():
        return
    try:
        nb_state = load_nb_state(inst.data_dir)
    except Exception as e:
        logger.warning(f"Startup: could not load nb_state: {e}")
        return

    # Збираємо in_progress
    broken = {tid: entry for tid, entry in nb_state.items()
              if isinstance(entry, dict) and entry.get("status") == "in_progress"}
    if not broken:
        return

    logger.warning(f"Startup: found {len(broken)} in_progress tasks, resuming...")

    # Завантажуємо всі теми одноразово
    try:
        state = _load_state()
        profile = inst.load_profile()
        all_topics = inst.get_full_curriculum(state, profile)
    except Exception as e:
        logger.error(f"Startup: could not load curriculum: {e}")
        return

    resumed = []
    for tid, entry in broken.items():
        # Пропускаємо якщо вже є активний таск
        if tid in _active_gen_tasks:
            logger.info(f"Startup: topic {tid} already queued, skipping")
            continue

        pending = entry.get("pending", [])
        if not pending:
            continue

        item = next((t for t in all_topics if t["id"] == int(tid)), None)
        if not item:
            logger.warning(f"Startup: topic {tid} not found in curriculum")
            continue

        _active_gen_tasks.add(tid)

        async def _gen_task(item=item, pending=pending, tid=tid):
            try:
                await inst._run_formats_with_backoff(
                    bot=application.bot,
                    chat_id=OWNER_CHAT_ID,
                    item=item,
                    selected=pending,
                    data_dir=inst.data_dir,
                )
            finally:
                _active_gen_tasks.discard(tid)

        asyncio.create_task(_gen_task())
        resumed.append(f"  • {item['title']}: {', '.join(pending)}")
        logger.info(f"Startup: resumed task for topic {tid} ({pending})")

    if resumed:
        logger.info(f"Startup: resumed {len(resumed)} tasks: {resumed}")


async def job_daily_digest(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running daily digest job")
    from modules.proactive import generate_proactive_message
    try:
        msg = generate_proactive_message()
        if msg:
            await context.bot.send_message(chat_id=OWNER_CHAT_ID, text=msg)
            logger.info("Proactive message sent")
    except Exception as e:
        logger.warning(f"Proactive engine error: {e}")
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


async def cmd_gen(update, context):
    """Генерує відсутні NbLM формати для теми /gen_N."""
    if update.effective_chat.id != OWNER_CHAT_ID:
        return
    import re as _re
    # Спочатку context.args (deep link або прямий виклик), потім message.text
    if context.args and context.args[0].isdigit():
        item_id = int(context.args[0])
    else:
        text = update.message.text or ""
        m = _re.search(r"/gen_?(\d+)", text)
        if not m:
            await update.message.reply_text("Використання: /gen_1")
            return
        item_id = int(m.group(1))
    from modules.curriculum import _get as _get_cur, load_state as _load_state
    inst = _get_cur(update.effective_user.id)
    state = _load_state()
    profile = inst.load_profile()
    all_topics = inst.get_full_curriculum(state, profile)
    item = next((t for t in all_topics if t["id"] == item_id), None)
    if not item:
        await update.message.reply_text(f"Тема {item_id} не знайдена")
        return
    from shared.notebooklm_module import load_nb_state
    from modules.hub import TRACKED_FORMATS
    nb_state = load_nb_state(inst.data_dir)
    entry = nb_state.get(str(item_id), {})
    generated = [f for f in entry.get("generated", []) if f in TRACKED_FORMATS]
    missing = [f for f in TRACKED_FORMATS if f not in generated]
    if not missing:
        await update.message.reply_text(f"\u2705 Всі формати вже згенеровані для теми {item_id}")
        return
    from shared.curriculum_engine import FORMAT_NAMES
    names = ", ".join(FORMAT_NAMES.get(f, f) for f in missing)
    await update.message.reply_text(f"\u23f3 Генерую для *{item['title']}*:\n{names}", parse_mode="Markdown")
    import asyncio
    asyncio.create_task(inst._run_all_formats_task(
        bot=update.get_bot(),
        chat_id=update.effective_chat.id,
        item=item,
        selected=missing,
        data_dir=inst.data_dir,
    ))


async def cmd_tts_play(update, context, item_id: int = None):
    """Відтворює TTS подкаст для теми."""
    if update.effective_chat.id != OWNER_CHAT_ID:
        return
    if item_id is None:
        import re as _re
        m = _re.search(r"tts_?(\d+)", update.message.text or "")
        if not m:
            return
        item_id = int(m.group(1))
    from modules.curriculum import _get as _get_cur
    inst = _get_cur(update.effective_user.id)
    ps = inst._load_podcast_state()
    entry = ps.get(str(item_id), {})
    # Беремо deep якщо є, інакше short
    for fmt in ("deep", "short"):
        file_id = entry.get(fmt, {}).get("file_id")
        if file_id:
            state = inst.load_state()
            profile = inst.load_profile()
            all_topics = inst.get_full_curriculum(state, profile)
            item = next((t for t in all_topics if t["id"] == item_id), None)
            label = "~15-20 хв" if fmt == "deep" else "~8-12 хв"
            caption = f"<b>{item['title'] if item else item_id}</b>\n<i>{label} • Curriculum #{item_id}</i>"
            await update.message.reply_audio(audio=file_id, caption=caption, parse_mode="HTML")
            return
    await update.message.reply_text(f"TTS подкаст для теми {item_id} ще не згенеровано")

def main():
    async def post_init(application):
        from telegram import BotCommand
        await startup_check(application)
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
    app.add_handler(CommandHandler("hub", cmd_hub))
    app.add_handler(CallbackQueryHandler(handle_hub_callback, pattern=r"^hub_"))
    app.add_handler(CommandHandler("cost", cmd_cost))
    app.add_handler(CommandHandler("digest", cmd_digest))
    app.add_handler(CommandHandler("science", cmd_science))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("cur", cmd_hub))
    app.add_handler(CommandHandler("cur_item", cmd_curriculum_item))
    app.add_handler(CommandHandler("podcast", cmd_podcast))
    app.add_handler(CommandHandler("notebooks", cmd_notebooks))
    app.add_handler(CommandHandler("getfileid", cmd_getfileid))
    app.add_handler(CommandHandler("done", cmd_done))
    app.add_handler(CommandHandler("cur_add", cmd_cur_add))
    app.add_handler(MessageHandler(filters.Regex(r"^/gen_\d+"), cmd_gen))
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
