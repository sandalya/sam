"""
shared/curriculum/renderer.py — рендер pinned панелі для курікулома v2.

Публічний API:
- render(state, bot_username=None, now_hhmm=None) -> str
    Legacy: показує тільки active, згруповані по островах. Використовується
    поточним modules/pinned.py до переключення на render_pinned.
- render_pinned(state, bot_username=None, now_hhmm=None, expanded_mastered=False) -> str
    Phase 2: групування за станами (🟢/🟡/✅), лічильники форматів N/7 ✓✓✓○○○○,
    summary по островах. Згідно CURRICULUM_MANIFEST.md §6.1.
- build_keyboard(state, expanded_mastered=False) -> InlineKeyboardMarkup
    Phase 2: поки тільки static-кнопки [🆕 Нова тема] [🗺 Карта].
    Per-topic toggle + fmt-check — пункт (2) Phase 2, не тут.

Принципи:
- HTML parse_mode, disable_web_page_preview=True.
- NBLM URL беремо з TopicFormat.url (міграція поклала туди).
- Deep-links у бот: https://t.me/{bot_username}?start={payload}.

Референс: CURRICULUM_MANIFEST.md §6, BOOTSTRAP_DIALOG.md Акт 6.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from .models import CurriculumState, Topic

if TYPE_CHECKING:
    # щоб не плодити імпорт telegram на рівні модуля (рендер може викликатись і в тестах)
    from telegram import InlineKeyboardMarkup


NB_BASE = "https://notebooklm.google.com/notebook/"


# Порядок форматів — consistent, незалежно від dict-порядку.
# 7 форматів усього (slides + podcast_nblm + podcast_tts + video + infographic + flashcards + exam).
# exam рахується у лічильник, але він не генерується пайплайном — маркер ✓ коли Саша пройшов тест.
FORMAT_ORDER = [
    "slides",
    "podcast_nblm",
    "podcast_tts",
    "video",
    "infographic",
    "flashcards",
]

# Всі 7 форматів для лічильника N/7 (включно з exam).
ALL_FORMATS_FOR_COUNTER = FORMAT_ORDER + ["exam"]

FORMAT_LABELS = {
    "slides":       "📊 Slides",
    "podcast_nblm": "🎙 Pod",
    "podcast_tts":  "🔊 TTS",
    "video":        "🎬 Video",
    "infographic":  "📈 Info",
    "flashcards":   "🃏 Flash",
    "exam":         "🧠 Exam",
}

CONTENT_STYLE_ICON = {
    "audio":  "🎧",
    "visual": "👁",
}


def _deep_link(bot_username: str, payload: str) -> str:
    return f"https://t.me/{bot_username}?start={payload}"


def _escape_html(text: str) -> str:
    """Мінімальний HTML-escape для Telegram."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _notebook_url_from_topic(t: Topic) -> Optional[str]:
    """
    Для показу "📓 NB" у шапці теми: беремо url будь-якого готового NBLM-формату.
    Усі NBLM-формати теми ділять один notebook, так що перший ready — ok.
    """
    nblm_format_keys = ("slides", "podcast_nblm", "video", "infographic", "flashcards")
    for key in nblm_format_keys:
        f = t.formats.get(key)
        if f and f.status == "ready" and f.url:
            return f.url
    return None


# ─────────────────────────────────────────────────────────────────────────────
# LEGACY API — не чіпати. Використовується поточним modules/pinned.py.
# ─────────────────────────────────────────────────────────────────────────────

def _render_topic(t: Topic, bot_username: Optional[str]) -> list[str]:
    """Повертає список рядків для однієї теми.

    Формат рядка під темою:
      📓 NB (лінк на нотбук) · наявне: 📊 🎙 🎬 📈 🃏
    Якщо у теми є лише TTS podcast — окремий лінк "🔊 TTS" замість NB.
    Якщо нічого не згенеровано — "(поки немає контенту)".
    """
    style_icon = CONTENT_STYLE_ICON.get(t.content_style, "")
    title = _escape_html(t.title)
    head = f"  ▸ {title} {style_icon}".rstrip()
    lines = [head]

    # Іконки форматів які в стані ready (без TTS — у нього окремий URL)
    content_icons: list[str] = []
    for key in FORMAT_ORDER:
        if key == "podcast_tts":
            continue
        f = t.formats.get(key)
        if f and f.status == "ready":
            icon_map = {
                "slides": "📊",
                "podcast_nblm": "🎙",
                "video": "🎬",
                "infographic": "📈",
                "flashcards": "🃏",
            }
            content_icons.append(icon_map.get(key, ""))

    parts: list[str] = []
    nb_url = _notebook_url_from_topic(t)
    if nb_url:
        parts.append(f'<a href="{nb_url}">📓 NB</a>')
    if content_icons:
        parts.append("наявне: " + " ".join(content_icons))

    tts_f = t.formats.get("podcast_tts")
    if tts_f and tts_f.status == "ready" and bot_username:
        parts.append(f'<a href="{_deep_link(bot_username, f"tts_{t.id}")}">🔊 TTS</a>')

    if parts:
        lines.append("     " + " · ".join(parts))
    else:
        lines.append("     <i>(поки немає контенту)</i>")

    return lines


def render(
    state: CurriculumState,
    *,
    bot_username: Optional[str] = None,
    now_hhmm: Optional[str] = None,
) -> str:
    """
    Legacy рендер: тільки active-теми, згруповані по островах.
    Використовується поточним modules/pinned.py до переключення на render_pinned.
    """
    total = len(state.topics)
    mastered = sum(1 for t in state.topics if t.state == "mastered")

    lines: list[str] = []
    lines.append(f"📚 <b>Курікулом</b> — {mastered}/{total} засвоєно")
    lines.append("")

    ordered = sorted(state.islands, key=lambda i: i.order)

    active_islands = []
    gap_islands = []
    for island in ordered:
        topics_in_island = [
            t for t in state.topics
            if t.island_id == island.id and t.state == "active"
        ]
        if topics_in_island:
            active_islands.append((island, topics_in_island))
        else:
            gap_islands.append(island)

    for island, topics in active_islands:
        title = _escape_html(island.title)
        lines.append(f"🏝 <b>{title}</b>")
        for t in topics:
            lines.extend(_render_topic(t, bot_username))
        lines.append("")

    if gap_islands:
        gap_titles = ", ".join(_escape_html(i.title) for i in gap_islands)
        lines.append(f"⚠️ <b>Прогалини</b> ({len(gap_islands)}): {gap_titles}")
        lines.append("")

    stamp = now_hhmm or datetime.now().strftime("%H:%M")
    lines.append(f"<i>Оновлено: {stamp}</i>")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 API — render_pinned + build_keyboard.
# Використовується пізніше: коли переключимо modules/pinned.py.
# ─────────────────────────────────────────────────────────────────────────────

def _format_counter(t: Topic) -> tuple[int, int, str]:
    """
    Рахує (consumed, total, bar) для теми.

    total = 7 (всі формати з ALL_FORMATS_FOR_COUNTER).
    consumed = скільки з них позначені як consumed.
    bar = рядок з 7 символів:
      ✓ — consumed
      ● — ready, не consumed
      ○ — pending/generating/failed (ще не готово для споживання)

    Порядок символів у bar відповідає ALL_FORMATS_FOR_COUNTER.
    """
    symbols: list[str] = []
    consumed = 0
    for key in ALL_FORMATS_FOR_COUNTER:
        f = t.formats.get(key)
        if f is None:
            symbols.append("○")
            continue
        if getattr(f, "consumed", False):
            symbols.append("✓")
            consumed += 1
        elif f.status == "ready":
            symbols.append("●")
        else:
            symbols.append("○")
    return consumed, len(ALL_FORMATS_FOR_COUNTER), "".join(symbols)


def _render_topic_v2(t: Topic, bot_username: Optional[str]) -> list[str]:
    """
    Phase 2 рендер теми з лічильником.

    Формат:
      ▸ RAG chunking 🎧 — 3/7 ✓✓✓○○○○
         📓 NB · 🔊 TTS                                    (якщо є ready контент)
    """
    style_icon = CONTENT_STYLE_ICON.get(t.content_style, "")
    title = _escape_html(t.title)
    consumed, total, bar = _format_counter(t)

    head_parts = [f"  ▸ {title}"]
    if style_icon:
        head_parts.append(style_icon)
    head_parts.append(f"— {consumed}/{total} {bar}")
    lines = [" ".join(head_parts)]

    # Другий рядок — клікабельні посилання на контент що доступний.
    parts: list[str] = []
    nb_url = _notebook_url_from_topic(t)
    if nb_url:
        parts.append(f'<a href="{nb_url}">📓 NB</a>')

    tts_f = t.formats.get("podcast_tts")
    if tts_f and tts_f.status == "ready" and bot_username:
        parts.append(f'<a href="{_deep_link(bot_username, f"tts_{t.id}")}">🔊 TTS</a>')

    if parts:
        lines.append("     " + " · ".join(parts))

    return lines


def _islands_summary(state: CurriculumState) -> str:
    """
    Рядок виду: 🗺 Острови: RAG (4) | Agents (5) | Evals (2) | Production (3)

    Рахує ВСІ теми на острові (будь-який state), не тільки active.
    Пропускає острови без тем взагалі.
    """
    ordered = sorted(state.islands, key=lambda i: i.order)
    parts: list[str] = []
    for island in ordered:
        count = sum(1 for t in state.topics if t.island_id == island.id)
        if count == 0:
            continue
        title = _escape_html(island.title)
        parts.append(f"{title} ({count})")
    if not parts:
        return ""
    return "🗺 Острови: " + " | ".join(parts)


def render_pinned(
    state: CurriculumState,
    *,
    bot_username: Optional[str] = None,
    now_hhmm: Optional[str] = None,
    expanded_mastered: bool = False,
) -> str:
    """
    Phase 2 pinned рендер згідно CURRICULUM_MANIFEST.md §6.1.

    Структура:
      📚 Курікулом
      🟢 В процесі (N)
        ▸ тема — counter
      🟡 Готові, не розпочаті (N)
        • тема
      ✅ Засвоєні (N) ▸                              (collapsed за замовчуванням)
      🗺 Острови: ...
      ⚠️ Прогалини (N): ...                         (острови без тем взагалі)
      <i>Оновлено: HH:MM</i>
    """
    lines: list[str] = []
    lines.append("📚 <b>Курікулом</b>")
    lines.append("")

    active = [t for t in state.topics if t.state == "active"]
    pending = [t for t in state.topics if t.state == "pending"]
    mastered = [t for t in state.topics if t.state == "mastered"]

    # 🟢 Active
    lines.append(f"🟢 <b>В процесі</b> ({len(active)})")
    if active:
        for t in active:
            lines.extend(_render_topic_v2(t, bot_username))
    else:
        lines.append("  <i>(поки немає активних тем)</i>")
    lines.append("")

    # 🟡 Pending
    lines.append(f"🟡 <b>Готові, не розпочаті</b> ({len(pending)})")
    if pending:
        for t in pending:
            style_icon = CONTENT_STYLE_ICON.get(t.content_style, "")
            title = _escape_html(t.title)
            suffix = f" {style_icon}" if style_icon else ""
            lines.append(f"  • {title}{suffix}")
    lines.append("")

    # ✅ Mastered
    mastered_header = f"✅ <b>Засвоєні</b> ({len(mastered)})"
    if expanded_mastered and mastered:
        lines.append(mastered_header)
        for t in mastered:
            title = _escape_html(t.title)
            lines.append(f"  • {title}")
    else:
        # collapsed — показуємо тільки заголовок з маркером "▸"
        marker = " ▸" if mastered else ""
        lines.append(f"{mastered_header}{marker}")
    lines.append("")

    # 🗺 Острови
    summary = _islands_summary(state)
    if summary:
        lines.append(summary)

    # ⚠️ Прогалини — острови, в яких взагалі немає тем
    gap_islands = [
        i for i in sorted(state.islands, key=lambda x: x.order)
        if not any(t.island_id == i.id for t in state.topics)
    ]
    if gap_islands:
        gap_titles = ", ".join(_escape_html(i.title) for i in gap_islands)
        lines.append(f"⚠️ <b>Прогалини</b> ({len(gap_islands)}): {gap_titles}")

    lines.append("")
    stamp = now_hhmm or datetime.now().strftime("%H:%M")
    lines.append(f"<i>Оновлено: {stamp}</i>")

    return "\n".join(lines)


def build_keyboard(
    state: CurriculumState,
    *,
    expanded_mastered: bool = False,
) -> "InlineKeyboardMarkup":
    """
    Phase 2 клавіатура для pinned панелі.

    Поки тільки static-кнопки: [🆕 Нова тема] [🗺 Карта].
    Per-topic toggle (`cur_toggle_{id}`), pipeline launch (`cur_pipeline_{id}`),
    fmt-check (`fmt_check_{id}_{fmt}`), mastered-expand — пункт (2) Phase 2,
    додамо у наступному кроці разом з callback-handlers.

    Параметр expanded_mastered залишаємо у сигнатурі для форвард-сумісності
    з пунктом (2), зараз не використовується.
    """
    # Імпорт на рівні функції — щоб модуль рендера можна було імпортити у тестах
    # без встановленого python-telegram-bot.
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    _ = expanded_mastered  # placeholder — буде використано у пункті (2)
    _ = state

    rows = [
        [
            InlineKeyboardButton("🆕 Нова тема", callback_data="cur_new"),
            InlineKeyboardButton("🗺 Карта", callback_data="cur_map"),
        ],
    ]
    return InlineKeyboardMarkup(rows)
