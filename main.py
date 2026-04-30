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
    cmd_done,
    cmd_cur_add,
    cmd_status,
    cmd_regen,
)
from modules.state_manager import touch_activity
from modules.exam import start_exam, handle_exam_answer, is_exam_active, cancel_exam, handle_exam_callback
from modules.activate import cmd_activate, handle_activate_callback

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
    # Deep-link dispatch: /start <payload> від кліків у pinned
    if context.args:
        await _handle_deep_link(update, context, context.args[0])
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
    from modules.base import DATA_DIR
    from modules.pinned import _render_current
    text = _render_current(DATA_DIR)
    await update.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)

async def cmd_pin(update, context):
    if update.effective_chat.id != OWNER_CHAT_ID:
        return
    from modules.base import DATA_DIR
    from modules.pinned import refresh_pinned
    msg_id = await refresh_pinned(context.bot, update.effective_chat.id, DATA_DIR)
    if msg_id:
        await update.message.reply_text("📌 Закріплено. Тепер /hub буде автооновлюватися вгорі чату.")
    else:
        await update.message.reply_text("❌ Не вдалося закріпити. Перевір логи.")


async def cmd_unpin(update, context):
    if update.effective_chat.id != OWNER_CHAT_ID:
        return
    from modules.base import DATA_DIR
    from modules.pinned import unpin
    ok = await unpin(context.bot, update.effective_chat.id, DATA_DIR)
    if ok:
        await update.message.reply_text("📌 Знято.")
    else:
        await update.message.reply_text("📌 Нічого не було закріплено.")


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
    from modules.base import DATA_DIR

    data_dir = DATA_DIR
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
            result = execute_tool(tc.name, tc.input, data_dir, bot=update.get_bot(), chat_id=update.effective_chat.id)
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

    # Exam intercept — якщо активний екзамен, всі текстові повідомлення йдуть туди
    from modules.base import DATA_DIR as _data_dir
    if is_exam_active(_data_dir):
        await handle_exam_answer(update.get_bot(), update.effective_chat.id, text, _data_dir)
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


async def cmd_dbg_nblm_sync(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Debug hook: /dbg_nblm_sync — синхронізує orphan notebooks як bonus episodes."""
    if update.effective_chat.id != OWNER_CHAT_ID:
        return
    from core.nblm_orphan_sync import sync_orphan_audio
    await update.message.reply_text("⏳ Синхронізую orphan notebooks... (~1-2 хв)")
    try:
        result = sync_orphan_audio()
        items = result.get("orphan_items", [])
        lines = [
            f"Orphan sync done: {len(items)} episodes",
            f"Skipped (curriculum): {result.get('skipped_curriculum', '?')}",
            f"Skipped (no audio): {result.get('skipped_no_audio', '?')}",
        ]
        if items:
            lines.append("Titles:")
            for it in items:
                lines.append(f"  • {it['title'][:60]}")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"ERROR: {e}")


async def cmd_dbg_rss_server(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Debug hook: /dbg_rss_server — тестує HTTP-ендпоінти RSS-сервера."""
    if update.effective_chat.id != OWNER_CHAT_ID:
        return
    import aiohttp
    BASE = "http://100.86.239.46:8765"
    lines = []
    timeout = aiohttp.ClientTimeout(total=5)

    async with aiohttp.ClientSession() as session:
        # /healthz
        try:
            async with session.get(f"{BASE}/healthz", timeout=timeout) as r:
                body = await r.text()
                lines.append(f"healthz: {r.status} {body.strip()}")
        except Exception as e:
            lines.append(f"healthz: ERROR {e}")

        # /feed.xml
        try:
            async with session.get(f"{BASE}/feed.xml", timeout=timeout) as r:
                body = await r.text()
                ct = r.headers.get("Content-Type", "")
                lines.append(f"feed: {r.status} ct={ct} len={len(body)}")
        except Exception as e:
            lines.append(f"feed: ERROR {e}")

        # /audio/agent_architecture-1.mp3
        try:
            async with session.get(f"{BASE}/audio/agent_architecture-1.mp3", timeout=timeout) as r:
                ct = r.headers.get("Content-Type", "")
                cl = r.headers.get("Content-Length", "0")
                ar = r.headers.get("Accept-Ranges", "")
                await r.release()
                lines.append(f"audio: {r.status} ct={ct} length={cl} accept-ranges={ar}")
        except Exception as e:
            lines.append(f"audio: ERROR {e}")

        # 404 for missing file
        try:
            async with session.get(f"{BASE}/audio/nonexistent.mp3", timeout=timeout) as r:
                await r.release()
                lines.append(f"audio_404: {r.status}")
        except Exception as e:
            lines.append(f"audio_404: ERROR {e}")

    await update.message.reply_text("\n".join(lines))


async def cmd_dbg_rss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Debug hook: /dbg_rss — тестує rss_feed.generate_feed()."""
    if update.effective_chat.id != OWNER_CHAT_ID:
        return
    from modules.base import DATA_DIR
    from core.rss_feed import generate_feed
    import xml.etree.ElementTree as ET

    try:
        feed_path = generate_feed(
            curriculum_path=DATA_DIR / "curriculum.json",
            audio_dir=DATA_DIR / "audio",
            output_xml=DATA_DIR / "feed.xml",
        )
        tree = ET.parse(str(feed_path))
        channel = tree.getroot().find("channel")
        title = channel.findtext("title") or ""
        description = channel.findtext("description") or ""
        language = channel.findtext("language") or ""
        items = channel.findall("item")
        guids = [it.findtext("guid") or "" for it in items]
        enclosures = [it.find("enclosure") for it in items]
        enc_urls = [e.get("url", "") if e is not None else "" for e in enclosures]
        enc_lengths = [e.get("length", "0") if e is not None else "0" for e in enclosures]
        lines = [
            f"FEED OK",
            f"title={title}",
            f"description={description[:40]}",
            f"language={language}",
            f"items={len(items)}",
        ]
        for i, (guid, url, length) in enumerate(zip(guids, enc_urls, enc_lengths)):
            lines.append(f"item[{i}] guid={guid} url={url} length={length}")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"FEED ERROR: {e}")


async def cmd_dbg_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Debug hook: /dbg_download <notebook_id> [force] — тестує audio_downloader."""
    if update.effective_chat.id != OWNER_CHAT_ID:
        return
    from modules.base import DATA_DIR
    from core.audio_downloader import download_podcast_audio

    args = context.args
    if not args:
        await update.message.reply_text("Usage: /dbg_download <notebook_id> [force]")
        return

    notebook_id = args[0]
    force = len(args) > 1 and args[1] == "force"
    output_dir = DATA_DIR / "audio"
    output_name = f"test_{notebook_id[:8]}"
    existed_before = (output_dir / f"{output_name}.mp3").exists()

    result = download_podcast_audio(notebook_id, output_dir, output_name, force=force)

    if result is None:
        await update.message.reply_text(f"RESULT: None\nnotebook_id={notebook_id}")
    elif existed_before and not force:
        await update.message.reply_text(
            f"RESULT: SKIPPED\npath={result}\nsize={result.stat().st_size}"
        )
    else:
        await update.message.reply_text(
            f"RESULT: DOWNLOADED\npath={result}\nsize={result.stat().st_size}"
        )


def main():
    async def post_init(application):
        from telegram import BotCommand
        await application.bot.set_my_commands([
            BotCommand("cur",        "📚 План навчання AI"),
            BotCommand("jobs",       "💼 Ринок праці"),
            BotCommand("notebooks",  "📓 NotebookLM notebooks"),
            BotCommand("article",    "📑 Стаття через NotebookLM"),
            BotCommand("status",     "📊 Стан генерації"),
            BotCommand("regen",      "🔄 Дорегенерація форматів"),
            BotCommand("activate",   "🎯 Активувати/деактивувати теми"),
        ])

        # Phase 6.2: lazy re-attach orphaned generating tasks (post-restart recovery)
        try:
            import asyncio as _asyncio
            from modules.base import DATA_DIR as _DD
            from curriculum.storage import load as _load_cur
            from core.notebooklm_module import generate_and_notify as _gan

            _state = _load_cur(_DD / "curriculum.json")
            _orphans = []
            for _t in _state.topics:
                for _fname, _f in _t.formats.items():
                    if _f.status == "generating" and _f.task_id:
                        _orphans.append(("topic", _t, _fname))
            for _a in _state.articles:
                for _fname, _f in _a.formats.items():
                    if _f.status == "generating" and _f.task_id:
                        _orphans.append(("article", _a, _fname))

            if _orphans:
                logger.info(f"Lazy re-attach: scheduling {len(_orphans)} orphaned task(s)")
                for _kind, _owner, _fname in _orphans:
                    _src = getattr(_owner, "source_url", None) or getattr(_owner, "url", "") or ""
                    logger.info(f"Lazy re-attach: {_kind} {_owner.id} fmt={_fname} task={_owner.formats[_fname].task_id}")
                    _asyncio.create_task(_gan(
                        bot=application.bot,
                        chat_id=OWNER_CHAT_ID,
                        topic_id=_owner.id,
                        topic_title=_owner.title,
                        source_url=_src,
                        fmt=_fname,
                        instructions="",
                        skip_source=True,
                        data_dir=_DD,
                        kind=_kind,
                    ))
            else:
                logger.info("Lazy re-attach: no orphaned tasks")
        except Exception as _e:
            logger.exception(f"Lazy re-attach failed: {_e}")

    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("pin", cmd_pin))
    app.add_handler(CommandHandler("unpin", cmd_unpin))
    app.add_handler(CommandHandler("cost", cmd_cost))
    app.add_handler(CommandHandler("digest", cmd_digest))
    app.add_handler(CommandHandler("science", cmd_science))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("cur", cmd_hub))
    app.add_handler(CommandHandler("podcast", cmd_podcast))
    app.add_handler(CommandHandler("notebooks", cmd_notebooks))
    from modules.article import cmd_article, cmd_article_del, handle_article_callback
    app.add_handler(CommandHandler("article", cmd_article))
    app.add_handler(CommandHandler("article_del", cmd_article_del))
    app.add_handler(CallbackQueryHandler(handle_article_callback, pattern=r"^art_"))
    app.add_handler(CommandHandler("getfileid", cmd_getfileid))
    app.add_handler(CommandHandler("dbg_download", cmd_dbg_download))
    app.add_handler(CommandHandler("dbg_rss", cmd_dbg_rss))
    app.add_handler(CommandHandler("dbg_rss_server", cmd_dbg_rss_server))
    app.add_handler(CommandHandler("dbg_nblm_sync", cmd_dbg_nblm_sync))
    app.add_handler(CommandHandler("done", cmd_done))
    app.add_handler(CommandHandler("cur_add", cmd_cur_add))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("regen", cmd_regen))
    app.add_handler(CommandHandler("activate", cmd_activate))
    app.add_handler(CallbackQueryHandler(handle_activate_callback, pattern=r"^act_"))
    app.add_handler(CommandHandler("exam_cancel", lambda u, c: cancel_exam(u.get_bot(), u.effective_chat.id, DATA_DIR)))
    app.add_handler(CallbackQueryHandler(handle_exam_callback, pattern=r"^exam_"))
    from modules.flashcards import handle_flashcards_callback
    app.add_handler(CallbackQueryHandler(handle_flashcards_callback, pattern=r"^fc_"))
    app.add_handler(CommandHandler("catchup", cmd_catchup))
    app.add_handler(CommandHandler("jobs", cmd_jobs))
    app.add_handler(CommandHandler("onboarding", cmd_onboarding))
    app.add_handler(CallbackQueryHandler(handle_onboarding_callback, pattern=r"^onb_"))

    # Callbacks
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




# ── Deep-link handlers (pinned panel clicks) ─────────────────────────────────

async def _handle_deep_link(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: str):
    """
    Dispatch deep-link payload від pinned-панелі.
    Після дії — refresh pinned + silent delete юзерської команди.
    """
    from modules.base import DATA_DIR
    from modules.pinned import (
        refresh_pinned,
    )
    from curriculum.storage import load as load_curriculum
    from curriculum.mutations import mark_format_consumed
    from curriculum.storage import save

    chat_id = update.effective_chat.id
    if chat_id != OWNER_CHAT_ID:
        return

    handled = False

    if payload.startswith("fmtcheck_"):
        # fmtcheck_{topic_id}_{format_key}
        # format_key може містити _ (podcast_nblm, podcast_tts)
        rest = payload[len("fmtcheck_"):]
        fmt_key = None
        for candidate in ("podcast_nblm", "podcast_tts"):
            if rest.endswith("_" + candidate):
                fmt_key = candidate
                topic_id = rest[:-(len(candidate) + 1)]
                break
        if not fmt_key:
            parts = rest.rsplit("_", 1)
            if len(parts) == 2:
                topic_id, fmt_key = parts
            else:
                logger.warning(f"Bad fmtcheck payload: {payload}")
                return
        try:
            cur_path = DATA_DIR / "curriculum.json"
            state = load_curriculum(cur_path)
            mark_format_consumed(state, topic_id, fmt_key, consumed=True)
            save(state, cur_path)
            logger.info(f"fmtcheck: {topic_id} / {fmt_key} marked consumed")
            handled = True
        except Exception as e:
            logger.error(f"fmtcheck failed: {e}", exc_info=True)

    elif payload.startswith("pipeline_"):
        topic_id = payload[len("pipeline_"):]
        logger.info(f"pipeline deep-link: {topic_id}")
        import asyncio
        from curriculum.pipeline import run_pipeline
        asyncio.create_task(run_pipeline(context.bot, chat_id, topic_id, DATA_DIR))
        handled = True

    elif payload.startswith("exam_"):
        topic_id = payload[len("exam_"):]
        logger.info(f"exam deep-link: {topic_id}")
        from modules.base import DATA_DIR
        await start_exam(context.bot, chat_id, topic_id, DATA_DIR)
        handled = True

    elif payload.startswith("fc_"):
        topic_id = payload[len("fc_"):]
        logger.info(f"flashcards deep-link: {topic_id}")
        from modules.base import DATA_DIR
        from modules.flashcards import start_flashcards
        await start_flashcards(context.bot, chat_id, topic_id, DATA_DIR)
        handled = True
    elif payload == "map":
        logger.info("map deep-link")
        try:
            from modules.island_map import render_island_map
            from modules.base import DATA_DIR
            map_text = render_island_map(DATA_DIR)
            await context.bot.send_message(
                chat_id=chat_id,
                text=map_text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error(f"map render failed: {e}", exc_info=True)
            await context.bot.send_message(chat_id=chat_id, text=f"❌ {e}")
        handled = True

    elif payload.startswith("tts_"):
        topic_id = payload[len("tts_"):]
        logger.info(f"tts deep-link: {topic_id}")
        try:
            cur_path = DATA_DIR / "curriculum.json"
            state = load_curriculum(cur_path)
            topic = state.get_topic(topic_id)
            if not topic:
                await context.bot.send_message(chat_id, f"❌ Тема не знайдена: {topic_id}")
                return
            fmt = topic.formats.get("podcast_tts")
            if not fmt or fmt.status != "ready" or not fmt.url:
                await context.bot.send_message(
                    chat_id,
                    f"❌ TTS подкаст ще не готовий для «{topic.title}»",
                )
                return
            await context.bot.send_audio(
                chat_id=chat_id,
                audio=fmt.url,
                title=topic.title[:64],
                caption=f"🎙 {topic.title}",
            )
            mark_format_consumed(state, topic_id, "podcast_tts", consumed=True)
            save(state, cur_path)
            handled = True
        except Exception as e:
            logger.error(f"tts send failed: {e}", exc_info=True)
            await context.bot.send_message(chat_id, f"❌ Не вдалось надіслати TTS: {e}")

    if handled:
        # Refresh pinned
        try:
            await refresh_pinned(context.bot, chat_id, DATA_DIR)
        except Exception as e:
            logger.error(f"refresh after deep-link failed: {e}")

        # Silent delete — видаляємо юзерську /start команду
        try:
            await update.message.delete()
        except Exception:
            pass


if __name__ == "__main__":
    main()
