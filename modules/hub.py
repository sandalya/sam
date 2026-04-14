"""
sam/modules/hub.py — навігаційний центр.
"""
import json
from pathlib import Path
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

NB_BASE = "https://notebooklm.google.com/notebook/"
NB_FILE = Path(__file__).parent.parent / "data" / "notebooklm_notebooks.json"
CUR_FILE = Path(__file__).parent.parent / "data" / "curriculum.json"

PAGE_SIZE = 8

ARTIFACT_LABEL = {
    "podcast":     "\U0001f399 NbLM Pod",
    "video":       "\U0001f3a5 Video",
    "flashcards":  "\U0001f0cf Flash",
    "slides":      "\U0001f4d1 Slides",
    "infographic": "\U0001f4ca Info",
    "tts":         "\U0001f50a TTS Pod",
    "briefing":    "\U0001f4cb Brief",
    "study":       "\U0001f4d8 Study",
    "study_guide": "\U0001f4d8 Study",
}

POD_FILE = Path(__file__).parent.parent / "data" / "podcasts_state.json"

def _load_notebooks() -> dict:
    if NB_FILE.exists():
        return json.loads(NB_FILE.read_text(encoding="utf-8"))
    return {}

def _load_tts_podcasts() -> set:
    """Повертає set topic_id для яких є TTS подкаст."""
    if not POD_FILE.exists():
        return set()
    data = json.loads(POD_FILE.read_text(encoding="utf-8"))
    return {int(k) for k, v in data.items() if v.get("short") or v.get("deep")}

def _load_cur_state() -> dict:
    if CUR_FILE.exists():
        return json.loads(CUR_FILE.read_text(encoding="utf-8"))
    return {"completed": [], "started": [], "notes": {}}

def _status_icon(topic_id: int, state: dict) -> str:
    if topic_id in state["completed"]: return "\u2705"
    if topic_id in state["started"]: return "\U0001f504"
    return "\u2b1c"

def hub_page(all_topics: list, page: int = 0) -> tuple:
    notebooks = _load_notebooks()
    state = _load_cur_state()

    total_pages = max(1, (len(all_topics) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    chunk = all_topics[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

    completed = len(state["completed"])
    total = len(all_topics)
    bar_filled = int((completed / max(total, 1)) * 10)
    bar = "\u2593" * bar_filled + "\u2591" * (10 - bar_filled)

    lines = [
        f"\U0001f4ca [{bar}] {completed}/{total}",
        "",
    ]

    tts_pods = _load_tts_podcasts()

    for t in chunk:
        tid = t["id"]
        icon = _status_icon(tid, state)
        nb = notebooks.get(str(tid), {})
        nb_id = nb.get("notebook_id")
        generated = nb.get("generated", [])

        lines.append(f"{icon} {tid}. {t['title']}")

        links = []
        if nb_id:
            links.append(f"[\U0001f4d3 NB]({NB_BASE}{nb_id})")
        for art in generated:
            label = ARTIFACT_LABEL.get(art, art)
            if nb_id:
                links.append(f"[{label}]({NB_BASE}{nb_id})")
        if tid in tts_pods:
            links.append(f"[\U0001f50a TTS](/podcast_{tid})")
        if links:
            lines.append("    " + "      ".join(links))
        lines.append("")

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(
            f"\u2190 {page}/{total_pages}",
            callback_data=f"hub_page|{page-1}"
        ))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(
            f"{page+2}/{total_pages} \u2192",
            callback_data=f"hub_page|{page+1}"
        ))

    kb = InlineKeyboardMarkup([nav_buttons]) if nav_buttons else None
    return "\n".join(lines), kb
