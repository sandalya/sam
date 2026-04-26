"""
sam/modules/article.py — standalone NotebookLM pipeline для довільних статтей.

Команди:
  /article <URL>           — додати статтю, вибрати формат через кнопки
  /article_del <short_id>  — видалити статтю (short_id з pinned, без префікса "article_")

Pipeline:
  1. fetch HTML (httpx) → витяг <title> та ~5k chars тексту
  2. Claude API (MODEL_SMART) аналізує → JSON {summary, recommended_formats}
  3. add_article() в curriculum → save → refresh_pinned (стаття з'явиться у секції 📑 Статті)
  4. показ картки з 5 кнопками форматів (✨ біля рекомендованих)
  5. callback art_<id>_<fmt> → Claude генерує instructions під формат + статтю
                            → generate_and_notify(kind="article", ...)
                            → refresh_pinned після ready
"""
import asyncio
import hashlib
import json
import logging
import re
from pathlib import Path

import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from shared.agent_base import client, MODEL_SMART
from curriculum import (
    load, save,
    add_article, remove_article,
)
from .base import DATA_DIR
from .pinned import refresh_pinned
from .notebooklm import generate_and_notify

log = logging.getLogger("modules.article")

# ── Константи ────────────────────────────────────────────────────────────────

NBLM_FORMATS = ["slides", "podcast_nblm", "video", "infographic", "flashcards"]

FORMAT_LABEL = {
    "slides":       "📊 Слайди",
    "podcast_nblm": "🎙 Подкаст",
    "video":        "🎬 Відео",
    "infographic":  "📈 Інфографіка",
    "flashcards":   "🃏 Флешкартки",
}

# Порядок генерації — audio-first (як в curriculum/pipeline.py AUDIO_FIRST_ORDER)
# Послідовно: спочатку швидкі і безпечні щодо rate-limit, потім важкі.
ARTICLE_FORMAT_ORDER = [
    "slides",        # швидкий
    "podcast_nblm",  # пріоритет за use-case (прогулянка)
    "infographic",
    "flashcards",
    "video",         # найповільніший, найбільший risk rate-limit — в кінці
]

MAX_CONTENT_CHARS = 5000  # для аналізу — beyond цього зріз
HTTP_TIMEOUT = 20.0

# In-memory selections: (chat_id, article_id) -> set[fmt]
# Втрачається при рестарті сервісу — це окей: користувач перезапустить /article.
_selections: dict[tuple[int, str], set[str]] = {}


# ── Утиліти ──────────────────────────────────────────────────────────────────

def _make_article_id(url: str) -> str:
    """article_<sha1[:8]> детермінований ID від URL — повторне додавання дає той самий ID."""
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    return f"article_{h}"


def _strip_html(html: str) -> str:
    """Грубо: прибирає теги, скрипти, стилі. Без зайвих залежностей."""
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def _extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.DOTALL | re.IGNORECASE)
    if not m:
        return "Untitled"
    title = re.sub(r"\s+", " ", m.group(1)).strip()
    # Розетковий формат "Title | Site Name" — беремо лівий шматок
    if " | " in title and len(title) > 50:
        title = title.split(" | ")[0].strip()
    return title[:200] or "Untitled"


async def _fetch_url(url: str) -> tuple[str, str]:
    """Returns (title, content_text). Raises на помилку."""
    headers = {"User-Agent": "Mozilla/5.0 (Sam Article Bot) AppleWebKit/537.36"}
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as c:
        resp = await c.get(url, headers=headers)
        resp.raise_for_status()
        html = resp.text
    title = _extract_title(html)
    text = _strip_html(html)[:MAX_CONTENT_CHARS]
    return title, text


# ── Claude calls ─────────────────────────────────────────────────────────────

ANALYSIS_SYSTEM = (
    "You analyze articles to help a developer (Sam's owner) decide which NotebookLM "
    "format would best fit the content. Reply with strict JSON only — no markdown, no preamble."
)

ANALYSIS_PROMPT_TMPL = """Article title: {title}
URL: {url}

Article content (truncated):
{content}

Analyze this article and return JSON in this exact shape:
{{
  "summary": "1-2 sentence summary in Ukrainian, capturing the core insight",
  "recommended_formats": ["fmt1", "fmt2"]
}}

Available formats: slides, podcast_nblm, video, infographic, flashcards.
Pick TOP 2 most suitable for THIS specific content:
- slides       — for structured comparisons, frameworks, step-by-step content
- podcast_nblm — for narrative, conceptual, discussion-worthy material
- video        — for visual processes, demos, broad overviews
- infographic  — for data-heavy, statistics, comparisons of many things
- flashcards   — for memorizable concepts, definitions, term-heavy content

Return ONLY the JSON object, nothing else."""


async def _analyze_article(url: str, title: str, content: str) -> dict:
    """Claude API call. Returns {summary, recommended_formats}."""
    prompt = ANALYSIS_PROMPT_TMPL.format(title=title, url=url, content=content)
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.messages.create(
            model=MODEL_SMART,
            max_tokens=500,
            system=ANALYSIS_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        ),
    )
    raw = "".join(b.text for b in response.content if b.type == "text").strip()
    # Strip markdown code fences if model added them
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```\s*$", "", raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        log.warning(f"Analysis JSON parse failed: {e}. Raw: {raw[:200]}")
        return {"summary": title, "recommended_formats": ["podcast_nblm"]}
    # Валідація
    summary = str(data.get("summary", "")).strip() or title
    formats = data.get("recommended_formats") or []
    formats = [f for f in formats if f in NBLM_FORMATS][:2]
    if not formats:
        formats = ["podcast_nblm"]
    return {"summary": summary[:500], "recommended_formats": formats}


PROMPT_GEN_SYSTEM = (
    "You generate focused instruction prompts for NotebookLM to produce content from "
    "a source article. Output the prompt directly — no preamble, no markdown, no quotes around it."
)

PROMPT_GEN_TMPL = """Generate a NotebookLM instruction prompt for format: {format}.

Source article title: {title}
Brief summary: {summary}
Format goal: {format_goal}

Audience: experienced Python developer building AI agents and Telegram bots, wants deeper understanding of theory and architecture.

The instruction prompt should:
- be in English (NotebookLM works better in English for generation)
- be 3-6 sentences
- guide NotebookLM to focus on the most useful aspects for this audience
- request concrete examples and actionable insights
- avoid generic intros / outros

Return ONLY the prompt text, nothing else."""

FORMAT_GOAL = {
    "slides":       "structured slide-deck with comparisons and frameworks",
    "podcast_nblm": "natural 2-host audio discussion exploring the topic in depth",
    "video":        "video overview with visual explanations of key concepts",
    "infographic":  "data-rich visual summary of the article's key points",
    "flashcards":   "memorizable Q&A cards covering core terms and concepts",
}


async def _generate_format_instructions(title: str, summary: str, fmt: str) -> str:
    """Returns ready-to-pass instructions string for NotebookLM."""
    prompt = PROMPT_GEN_TMPL.format(
        format=fmt, title=title, summary=summary,
        format_goal=FORMAT_GOAL.get(fmt, fmt),
    )
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.messages.create(
            model=MODEL_SMART,
            max_tokens=400,
            system=PROMPT_GEN_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        ),
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()


# ── UI: format keyboard ──────────────────────────────────────────────────────

def _format_keyboard(
    article_id: str,
    recommended: list[str],
    selected: set[str] | None = None,
) -> InlineKeyboardMarkup:
    """Чекбоксна клавіатура. ☑/☐ перед іконкою формату, ✨ біля рекомендованих.
    Кнопка '🚀 Згенерувати (N)' зʼявляється тільки якщо вибрано ≥1 формат."""
    if selected is None:
        selected = set()
    short_id = article_id.replace("article_", "")
    rows = []
    for fmt in NBLM_FORMATS:
        check = "☑" if fmt in selected else "☐"
        rec_mark = "✨ " if fmt in recommended else ""
        label = f"{check} {rec_mark}{FORMAT_LABEL[fmt]}"
        rows.append([InlineKeyboardButton(label, callback_data=f"art_{short_id}_toggle_{fmt}")])
    if selected:
        rows.append([InlineKeyboardButton(
            f"🚀 Згенерувати ({len(selected)})",
            callback_data=f"art_{short_id}_go",
        )])
    return InlineKeyboardMarkup(rows)


# ── /article handler ─────────────────────────────────────────────────────────

async def cmd_article(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat_id = update.effective_chat.id
    args = context.args

    if not args:
        await msg.reply_text(
            "Використання: <code>/article &lt;URL&gt;</code>\n\n"
            "Я проаналізую статтю і запропоную оптимальні NotebookLM формати.",
            parse_mode="HTML",
        )
        return

    url = args[0].strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await msg.reply_text("URL має починатись з http:// або https://")
        return

    article_id = _make_article_id(url)

    # Перевірка дублікату
    state = load(DATA_DIR / "curriculum.json")
    existing = state.get_article(article_id)
    if existing:
        short_id = article_id.replace("article_", "")
        await msg.reply_text(
            f"📑 Стаття вже додана: <b>{existing.title}</b>\n"
            f"<code>{short_id}</code>\n\n"
            f"Вибери формат:",
            parse_mode="HTML",
            reply_markup=_format_keyboard(article_id, []),
            disable_web_page_preview=True,
        )
        return

    status_msg = await msg.reply_text("⏳ Завантажую статтю...")

    # Fetch
    try:
        title, content = await _fetch_url(url)
    except Exception as e:
        log.error(f"Fetch failed for {url}: {e}")
        await status_msg.edit_text(f"❌ Не вдалось завантажити: {e}")
        return

    await status_msg.edit_text(f"⏳ Аналізую: <b>{title[:80]}</b>...", parse_mode="HTML")

    # Analyze
    try:
        analysis = await _analyze_article(url, title, content)
    except Exception as e:
        log.error(f"Analysis failed: {e}")
        await status_msg.edit_text(f"❌ Аналіз провалився: {e}")
        return

    summary = analysis["summary"]
    recommended = analysis["recommended_formats"]

    # Save в curriculum
    add_article(state, article_id, title, url, summary)
    save(state, DATA_DIR / "curriculum.json")
    log.info(f"Article {article_id} saved: {title[:60]}")

    # Refresh pinned (стаття з'явиться в секції 📑 Статті)
    try:
        await refresh_pinned(context.bot, chat_id, DATA_DIR)
    except Exception as e:
        log.warning(f"refresh_pinned failed: {e}")

    # Картка з кнопками
    short_id = article_id.replace("article_", "")
    rec_str = ", ".join(FORMAT_LABEL[f].split(" ", 1)[1] for f in recommended)
    text = (
        f"📑 <b>{title}</b>\n"
        f"<code>{short_id}</code>\n\n"
        f"<i>{summary}</i>\n\n"
        f"💡 Рекомендую: <b>{rec_str}</b>\n"
        f"Вибери формат для генерації:"
    )
    await status_msg.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=_format_keyboard(article_id, recommended),
        disable_web_page_preview=True,
    )


# ── Callback handler: art_<short_id>_(toggle_<fmt>|go) ──────────────────────

def _parse_callback(data: str) -> tuple[str | None, str, str | None]:
    """Returns (short_id, action, fmt). action: 'toggle' | 'go'. fmt: only for toggle."""
    if not data.startswith("art_"):
        return None, "", None
    rest = data[len("art_"):]
    if rest.endswith("_go"):
        return rest[: -len("_go")], "go", None
    # toggle_<fmt>: fmt може мати підкреслення (podcast_nblm)
    for f in NBLM_FORMATS:
        suffix = f"_toggle_{f}"
        if rest.endswith(suffix):
            return rest[: -len(suffix)], "toggle", f
    return None, "", None


async def _run_generation_queue(
    bot, chat_id: int, article_id: str, article_title: str,
    article_summary: str, source_url: str, formats: list[str],
) -> None:
    """Послідовно генерує всі вибрані формати (mirror _run_regen).
    Один summary в кінці. generate_and_notify сам надсилає per-format ready/failed."""
    ok, failed = 0, 0
    for fmt in formats:
        try:
            instructions = await _generate_format_instructions(article_title, article_summary, fmt)
        except Exception as e:
            log.error(f"Prompt gen failed for {article_id}/{fmt}: {e}")
            await bot.send_message(chat_id, f"⚠️ {FORMAT_LABEL[fmt]}: prompt gen failed: {e}")
            failed += 1
            continue
        try:
            await generate_and_notify(
                bot=bot, chat_id=chat_id,
                topic_id=article_id, topic_title=article_title,
                source_url=source_url, fmt=fmt,
                instructions=instructions, kind="article",
            )
            ok += 1
        except Exception as e:
            log.error(f"generate_and_notify failed for {article_id}/{fmt}: {e}")
            await bot.send_message(chat_id, f"⚠️ {FORMAT_LABEL[fmt]}: {e}")
            failed += 1
    # Refresh pinned один раз в кінці — там зʼявляться всі готові іконки
    try:
        await refresh_pinned(bot, chat_id, DATA_DIR)
    except Exception as e:
        log.warning(f"refresh_pinned post-queue failed: {e}")
    # Summary
    summary = f"🏁 Готово: {ok}/{len(formats)} форматів"
    if failed:
        summary += f" ({failed} провалились)"
    await bot.send_message(chat_id, summary)


async def handle_article_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    short_id, action, fmt = _parse_callback(query.data)
    if not short_id:
        await query.edit_message_text(f"❌ Не зрозумів callback: {query.data}")
        return

    article_id = f"article_{short_id}"
    chat_id = update.effective_chat.id
    sel_key = (chat_id, article_id)

    state = load(DATA_DIR / "curriculum.json")
    article = state.get_article(article_id)
    if not article:
        await query.edit_message_text(f"❌ Статтю <code>{short_id}</code> не знайдено", parse_mode="HTML")
        _selections.pop(sel_key, None)
        return

    # ── ACTION: toggle ──
    if action == "toggle":
        selected = _selections.setdefault(sel_key, set())
        if fmt in selected:
            selected.discard(fmt)
        else:
            selected.add(fmt)
        # Reuse рекомендацій — їх в Article ми не зберігаємо, тож просто без ✨
        # (✨ важливо тільки на старті; коли юзер вже клікає, рекомендації вже видно)
        # Краще зберегти рекомендації — для цього reload не треба, recompute з summary не варто.
        # Залишимо без ✨ при оновленні (мінус) АБО зберегти список у _selections як кортеж.
        # Простіше — recover через ARTICLE_FORMAT_ORDER не вийде, тож просто без ✨ після першого toggle.
        await query.edit_message_reply_markup(
            reply_markup=_format_keyboard(article_id, [], selected=selected),
        )
        return

    # ── ACTION: go ──
    if action == "go":
        selected = _selections.get(sel_key, set())
        if not selected:
            await query.answer("Спочатку виберіть хоча б один формат", show_alert=True)
            return
        # Сортуємо за ARTICLE_FORMAT_ORDER (швидкі/безпечні спочатку)
        ordered = [f for f in ARTICLE_FORMAT_ORDER if f in selected]
        labels = ", ".join(FORMAT_LABEL[f] for f in ordered)
        await query.edit_message_text(
            f"⏳ Генерую {len(ordered)} формат(и) послідовно для:\n"
            f"<b>{article.title}</b>\n\n"
            f"Черга: {labels}\n\n"
            f"Кожен формат повідомить окремо коли готово.",
            parse_mode="HTML",
        )
        # Очищаємо вибір — щоб не запустилось двічі при випадковому повторному кліку
        _selections.pop(sel_key, None)
        # Запускаємо чергу в background
        asyncio.create_task(_run_generation_queue(
            bot=context.bot, chat_id=chat_id,
            article_id=article_id, article_title=article.title,
            article_summary=article.summary, source_url=article.source_url,
            formats=ordered,
        ))
        return


# ── /article_del handler ─────────────────────────────────────────────────────

async def cmd_article_del(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat_id = update.effective_chat.id
    args = context.args

    if not args:
        await msg.reply_text(
            "Використання: <code>/article_del &lt;short_id&gt;</code>\n\n"
            "short_id видно у pinned поряд зі статтею (8 символів).",
            parse_mode="HTML",
        )
        return

    short_id = args[0].strip().replace("article_", "")
    article_id = f"article_{short_id}"

    state = load(DATA_DIR / "curriculum.json")
    article = state.get_article(article_id)
    if not article:
        await msg.reply_text(f"❌ Статтю <code>{short_id}</code> не знайдено", parse_mode="HTML")
        return

    title = article.title
    remove_article(state, article_id)
    save(state, DATA_DIR / "curriculum.json")
    log.info(f"Article {article_id} deleted: {title[:60]}")

    try:
        await refresh_pinned(context.bot, chat_id, DATA_DIR)
    except Exception as e:
        log.warning(f"refresh_pinned after delete failed: {e}")

    await msg.reply_text(f"✅ Видалено: <b>{title}</b>", parse_mode="HTML")
