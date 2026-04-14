"""
sam/modules/hub.py — навігаційний центр / рендер /cur.
"""
import json
from pathlib import Path
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

NB_BASE = "https://notebooklm.google.com/notebook/"
BOT_USERNAME = "sashoks_assistant1_sam_bot"
BOT_DEEP = f"https://t.me/{BOT_USERNAME}?start="
# Шляхи встановлюються динамічно через hub_page(data_dir=...)
NB_FILE = None
CUR_FILE = None
POD_FILE = None

PAGE_SIZE = 8

TRACKED_FORMATS = ["video", "podcast", "flashcards", "slides", "infographic"]

ARTIFACT_LABEL = {
    "video":       "🎬 Video",
    "podcast":     "🎙️ Pod",
    "flashcards":  "🃏 Flash",
    "slides":      "📊 Slides",
    "infographic": "📈 Info",
}


def _load_notebooks(p=None) -> dict:
    if p and p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def _load_tts_podcasts(p=None) -> dict:
    if not p or not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    result = {}
    for k, v in data.items():
        has_short = bool(v.get("short", {}).get("file_id"))
        has_deep = bool(v.get("deep", {}).get("file_id"))
        if has_short or has_deep:
            result[int(k)] = {"short": has_short, "deep": has_deep}
    return result


def _load_cur_state(p=None) -> dict:
    if p and p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"completed": [], "started": [], "notes": {}}


def _status_icon(topic_id: int, state: dict) -> str:
    if topic_id in state["completed"]: return "✅"
    if topic_id in state["started"]: return "🔄"
    return "⬜"


def _artifacts_line(tid: int, nb: dict, tts_pods: dict) -> str:
    nb_id = nb.get("notebook_id")
    generated = [f for f in nb.get("generated", []) if f in TRACKED_FORMATS]
    tts = tts_pods.get(tid)
    parts = []
    if nb_id:
        parts.append(f'<a href="{NB_BASE}{nb_id}">📓 NB</a>')
    if tts:
        parts.append(f'<a href="{BOT_DEEP}tts_{tid}">🔊 послухати</a>')
    missing = [f for f in TRACKED_FORMATS if f not in generated]
    if missing:
        parts.append(f'<a href="{BOT_DEEP}gen_{tid}">✨ згенерувати</a>')
    if not parts:
        return ""
    return "   " + " · ".join(parts)


def hub_page(all_topics: list, page: int = 0, data_dir: Path = None) -> tuple:
    _nb_file = (data_dir / "notebooklm_notebooks.json") if data_dir else NB_FILE
    _cur_file = (data_dir / "curriculum.json") if data_dir else CUR_FILE
    _pod_file = (data_dir / "podcasts_state.json") if data_dir else POD_FILE
    notebooks = _load_notebooks(_nb_file)
    state = _load_cur_state(_cur_file)
    tts_pods = _load_tts_podcasts(_pod_file)

    total_pages = max(1, (len(all_topics) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    chunk = all_topics[page * PAGE_SIZE: (page + 1) * PAGE_SIZE]

    completed = len(state["completed"])
    total = len(all_topics)
    bar_filled = int((completed / max(total, 1)) * 10)
    bar = "█" * bar_filled + "░" * (10 - bar_filled)

    lines = [
        f"📚 [{bar}] {completed}/{total}",
        "",
    ]

    for t in chunk:
        tid = t["id"]
        icon = _status_icon(tid, state)
        nb = notebooks.get(str(tid), {})

        lines.append(f"{icon} <b>{tid}.</b> {t['title']} — <i>{t['estimate']}</i>")
        art_line = _artifacts_line(tid, nb, tts_pods)
        if art_line:
            lines.append(art_line)
        lines.append("")


    btn_row = [
        InlineKeyboardButton(
            f"{_status_icon(t['id'], state)}{t['id']}",
            callback_data=f"cur_item|{t['id']}"
        )
        for t in chunk
    ]
    rows = [btn_row[i:i+4] for i in range(0, len(btn_row), 4)]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(f"← {page}/{total_pages}", callback_data=f"hub_page|{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(f"{page+2}/{total_pages} →", callback_data=f"hub_page|{page+1}"))
    if nav:
        rows.append(nav)

    kb = InlineKeyboardMarkup(rows) if rows else None
    return "\n".join(lines), kb
