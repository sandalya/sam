"""
curriculum/renderer.py — рендер pinned панелі для курікулома v2.

Публічний API:
- render_pinned(state, bot_username=None, now_hhmm=None) -> str
    Компактний рядок per-topic: NB · TTS · EXAM

Принципи:
- HTML parse_mode, disable_web_page_preview=True.
- NBLM URL з Topic.nblm_notebook_id.
- Deep-links: https://t.me/{bot_username}?start={payload}.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from .models import CurriculumState, Topic, Article


NB_BASE = "https://notebooklm.google.com/notebook/"

CONTENT_STYLE_ICON = {
    "audio":  "🎧",
    "visual": "👁",
}

# Іконки форматів для статтей (компактний рендер)
ARTICLE_FORMAT_ICON = {
    "slides":       "📊",
    "podcast_nblm": "🎙",
    "video":        "🎬",
    "infographic":  "📈",
    "flashcards":   "🃏",
}


def _render_article_line(article: Article) -> str:
    """Один рядок: • <a href=...>Title</a> 📊 🎙 🎬   <code>id</code>"""
    title = _escape_html(article.title)
    # Лінк: на notebook якщо є, інакше — на source URL
    if article.nblm_notebook_id:
        url = f"{NB_BASE}{article.nblm_notebook_id}"
    else:
        url = article.source_url
    title_link = f'<a href="{url}">{title}</a>'

    # Іконки готових форматів
    ready_icons = []
    for fmt, fmt_obj in article.formats.items():
        if fmt_obj.status == "ready":
            icon = ARTICLE_FORMAT_ICON.get(fmt)
            if icon:
                ready_icons.append(icon)
    icons_str = " ".join(ready_icons)

    # Короткий ID для /article_del
    short_id = article.id.replace("article_", "")
    id_str = f' <code>{short_id}</code>'

    if icons_str:
        return f"  • {title_link} {icons_str}{id_str}"
    return f"  • {title_link}{id_str}"



def _deep_link(bot_username: str, payload: str) -> str:
    return f"https://t.me/{bot_username}?start={payload}"


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _nb_link(t: Topic) -> str:
    """NB лінк на notebook або — якщо нема."""
    if t.nblm_notebook_id:
        url = f"{NB_BASE}{t.nblm_notebook_id}"
        return f'<a href="{url}">📓 NB</a>'
    for key in ("slides", "podcast_nblm", "video", "infographic", "flashcards"):
        f = t.formats.get(key)
        if f and f.status == "ready" and f.url:
            return f'<a href="{f.url}">NB</a>'
    return "\u2014"


def _tts_link(t: Topic, bot_username: Optional[str]) -> str:
    """TTS deep-link або —."""
    f = t.formats.get("podcast_tts")
    if f and f.status == "ready" and f.url and bot_username:
        return f'<a href="{_deep_link(bot_username, f"tts_{t.id}")}">🎙 TTS</a>'
    return "\u2014"


def _exam_label(t: Topic, bot_username: str = None) -> str:
    """EXAM deep-link — Phase 3."""
    f = t.formats.get("exam")
    if f and f.status == "ready":
        return "\u2705 \U0001f9e0 Exam"
    if bot_username:
        url = _deep_link(bot_username, f"exam_{t.id}")
        return f'<a href="{url}">\U0001f9e0 Exam</a>'
    return "\U0001f9e0 Exam"


def _fc_label(t: Topic, bot_username: Optional[str] = None) -> str:
    """FC (flashcards) deep-link — Phase 6.1. Кликабельний якщо ready+cards."""
    f = t.formats.get("flashcards")
    if not f or f.status != "ready" or not f.cards:
        return "FC"
    if bot_username:
        url = _deep_link(bot_username, f"fc_{t.id}")
        return f'<a href="{url}">FC</a>'
    return "FC"


def _render_topic_line(t: Topic, bot_username: Optional[str]) -> list[str]:
    """
    Два рядки теми:
      ▸ Title 🎧
         📓 NB  ·  🎙 TTS  ·  🧠 EXAM
    """
    style_icon = CONTENT_STYLE_ICON.get(t.content_style, "")
    title = _escape_html(t.title)
    nb = _nb_link(t)
    tts = _tts_link(t, bot_username)
    fc = _fc_label(t, bot_username)
    exam = _exam_label(t, bot_username)
    suffix = f" {style_icon}" if style_icon else ""
    line1 = f"  \u25b8 {title}{suffix}"
    line2 = f"     {nb}  \u00b7  {tts}  \u00b7  {fc}  \u00b7  {exam}"
    return [line1, line2]


def _islands_summary(state: CurriculumState) -> str:
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
    return "\U0001f5fa Острови: " + " | ".join(parts)


def render_pinned(
    state: CurriculumState,
    *,
    bot_username: Optional[str] = None,
    now_hhmm: Optional[str] = None,
    expanded_mastered: bool = False,
    expanded_topic_ids: Optional[set] = None,
) -> str:
    """
    Pinned панель курікулома.

    Структура:
      📚 Курікулум (N active / M mastered / K total)

      🏝 Island Title
        ▸ Topic — NB · 🎙 TTS · EXAM

      ✅ Засвоєні (M)
        topic1, topic2, ...

      🗺 Острови: ...
      🆕 Додати: /cur_add назва теми
      Оновлено: HH:MM
    """
    lines: list[str] = []

    counts = state.counts()
    lines.append(
        f"\U0001f4da <b>Курікулум</b> "
        f"({counts['active']} active / {counts['pending']} pending "
        f"/ {counts['mastered']} mastered)"
    )
    lines.append("")

    active_only = [t for t in state.topics if t.state == "active"]
    mastered = [t for t in state.topics if t.state == "mastered"]

    ordered_islands = sorted(state.islands, key=lambda i: i.order)

    for island in ordered_islands:
        topics = [t for t in active_only if t.island_id == island.id]
        if not topics:
            continue
        title = _escape_html(island.title)
        lines.append(f"\U0001f3dd <b>{title}</b>")
        for t in topics:
            lines.extend(_render_topic_line(t, bot_username))
        lines.append("")

    if mastered:
        titles = ", ".join(_escape_html(t.title) for t in mastered)
        lines.append(f"\u2705 <b>Засвоєні</b> ({len(mastered)})")
        lines.append(f"  {titles}")
        lines.append("")

    # ── Articles секція ──────────────────────────────────────────────────────
    if state.articles:
        lines.append(f"\U0001f4d1 <b>Статті</b> ({len(state.articles)})")
        for art in state.articles:
            lines.append(_render_article_line(art))
        lines.append("")

    if bot_username:
        map_url = _deep_link(bot_username, "map")
        lines.append(f'<a href="{map_url}">🗺 Карта островів</a>')
        lines.append("")

    stamp = now_hhmm or datetime.now().strftime("%H:%M")
    lines.append(f"<i>Оновлено: {stamp}</i>")

    return "\n".join(lines)
