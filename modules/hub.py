"""
sam/modules/hub.py — dashboard повідомлення з поточним прогресом.
"""
from modules.state_manager import get_current_progress

ARTIFACT_ICONS = {
    "podcast":     "🎙",
    "briefing":    "📋",
    "study_guide": "📘",
    "flashcards":  "🃏",
    "video":       "🎥",
    "infographic": "📊",
    "slides":      "📑",
}

def _topic_name(topic_id, curriculum_list: list) -> str:
    if not topic_id:
        return "—"
    t = next((t for t in curriculum_list if t["id"] == topic_id), None)
    return t["title"] if t else str(topic_id)

def generate_hub_message(curriculum_list: list, total_topics: int) -> str:
    progress = get_current_progress()
    completed = progress["completed_count"]
    bar_filled = int((completed / max(total_topics, 1)) * 10)
    bar = "▓" * bar_filled + "░" * (10 - bar_filled)
    topic_name = _topic_name(progress["current_topic_id"], curriculum_list)

    lines = [
        "📊 *Sam Hub*",
        f"[{bar}] {completed}/{total_topics}",
        "",
        f"📍 *Зараз:* {topic_name}",
    ]

    consumed = progress["artifacts_consumed"]
    remaining = progress["artifacts_remaining"]
    inactive = progress["days_inactive"]
    streak = progress["streak_days"]

    if consumed:
        icons = " ".join(ARTIFACT_ICONS.get(a, "✅") for a in consumed)
        lines.append(f"  ✅ Переглянуто: {icons}")

    if remaining:
        icons = " ".join(ARTIFACT_ICONS.get(a, "⬜") for a in remaining)
        lines.append(f"  ⬜ Залишилось: {icons}")

    if inactive >= 2:
        lines.append("")
        lines.append(f"⏰ Не працював {inactive} дн.")

    if streak > 1:
        lines.append(f"🔥 Streak: {streak} дн.")

    return "\n".join(lines)
