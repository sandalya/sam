"""
modules/curriculum_v2.py — нова команда /cur2 для Фази 1.

Читає data/curriculum_v2.json через shared.curriculum.storage.load()
і рендерить острови з темами. Без кнопок, без редагування — тільки перегляд.

Це мінімальний MVP для перевірки що міграція жива і дані читаються.
У Фазі 2 буде pinned панель з чекбоксами і кнопками.

Референс: sam/docs/CURRICULUM_MANIFEST.md розділ 6
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Додаємо workspace в path якщо ще немає (на випадок запуску через python main.py)
_WS = str(Path(__file__).parent.parent.parent)
if _WS not in sys.path:
    sys.path.insert(0, _WS)

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from shared.curriculum.storage import load
from shared.curriculum.models import CurriculumState, Island, Topic

# Шлях до нового курікулома (v2)
CURRICULUM_V2_PATH = Path(__file__).parent.parent / "data" / "curriculum_v2.json"

log = logging.getLogger("sam.curriculum_v2")


# ─── Іконки станів ────────────────────────────────────────────────────────────

STATE_ICON = {
    "pending": "🟡",
    "active": "🟢",
    "mastered": "✅",
}

STYLE_ICON = {
    "audio": "🎙️",
    "visual": "👁️",
}


# ─── Рендер ───────────────────────────────────────────────────────────────────

def _escape_md(text: str) -> str:
    """Мінімальне екранування для Markdown (v1), щоб не ламати вивід."""
    # ParseMode.MARKDOWN (v1) потребує екранування _ * ` [ (для безпеки всіх)
    for ch in ("_", "*", "`", "["):
        text = text.replace(ch, f"\\{ch}")
    return text


def _render_topic_line(topic: Topic) -> str:
    """
    Одна строка про тему в загальному списку.
    Формат:
      🟢 `tools-1` · Tool Use / Function Calling · 5/7 🎙️
    """
    icon = STATE_ICON.get(topic.state, "❔")
    style_icon = STYLE_ICON.get(topic.content_style, "")
    ready = topic.formats_ready_count()
    # 7 — кількість форматів у повному пайплайні (slides, podcast_nblm, podcast_tts,
    # video, infographic, flashcards, exam)
    total = 7
    title = _escape_md(topic.title)
    return f"  {icon} `{topic.id}` · {title} · {ready}/{total} {style_icon}".rstrip()


def _render_island_section(island: Island, topics: list[Topic]) -> str:
    """Заголовок острова + його теми."""
    lines = []
    title = _escape_md(island.title)
    if not topics:
        # Gap island
        desc = _escape_md(island.description) if island.description else ""
        lines.append(f"🏝️ *{title}* (прогалина)")
        if desc:
            lines.append(f"  _{desc}_")
        return "\n".join(lines)

    lines.append(f"🏝️ *{title}* ({len(topics)})")
    # Сортуємо за id в межах острова для стабільного порядку
    for t in sorted(topics, key=lambda x: x.id):
        lines.append(_render_topic_line(t))
    return "\n".join(lines)


def render_curriculum(state: CurriculumState) -> str:
    """Повний текст повідомлення /cur2."""
    counts = state.counts()
    header = [
        "📚 *Курікулом v2*",
        f"Тем: {counts['total']} · "
        f"🟡 {counts['pending']} · 🟢 {counts['active']} · ✅ {counts['mastered']}",
        f"Островів: {counts['islands']}",
    ]
    if state.learning_vector:
        vector_short = state.learning_vector[:120]
        if len(state.learning_vector) > 120:
            vector_short += "..."
        header.append("")
        header.append(f"_Vector:_ {_escape_md(vector_short)}")

    sections = [island_text for island_text in (
        _render_island_section(i, state.topics_in_island(i.id))
        for i in state.islands
    )]

    return "\n".join(header) + "\n\n" + "\n\n".join(sections)


# ─── Handler ──────────────────────────────────────────────────────────────────

async def cmd_curriculum_v2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /cur2 — показує новий курікулом v2 (з островами).
    Fallback: якщо curriculum_v2.json немає — кажемо що треба запустити міграцію.
    """
    if not CURRICULUM_V2_PATH.exists():
        await update.message.reply_text(
            "⚠️ Новий курікулом ще не створено.\n\n"
            "Запусти міграцію:\n"
            "`./venv/bin/python scripts/run_plan_migration.py`\n"
            "`./venv/bin/python scripts/run_apply_migration.py`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        state = load(CURRICULUM_V2_PATH)
    except Exception as e:
        log.exception("Failed to load curriculum_v2.json")
        await update.message.reply_text(
            f"❌ Не вдалось прочитати `curriculum_v2.json`:\n`{e}`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = render_curriculum(state)

    # Telegram ліміт — 4096 символів, у нас ~16 тем це ~1-2KB. Не ріжемо.
    # Якщо колись будуть 100+ тем — додамо пагінацію.
    try:
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
    except Exception as e:
        # Fallback без markdown якщо екранування криве
        log.warning(f"Markdown parse failed: {e}, sending plain text")
        await update.message.reply_text(
            text.replace("*", "").replace("`", "").replace("\\", ""),
            disable_web_page_preview=True,
        )
