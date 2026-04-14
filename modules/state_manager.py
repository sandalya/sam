"""
sam/modules/state_manager.py — управління стейтом навчання.
Доповнює curriculum.json даними про artifacts і активність.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

STATE_FILE = Path(__file__).parent.parent / "data" / "learning_state.json"

ARTIFACT_ICONS = {
    "podcast":     "\U0001f399",
    "briefing":    "\U0001f4cb",
    "study_guide": "\U0001f4d8",
    "flashcards":  "\U0001f0cf",
    "video":       "\U0001f3a5",
    "infographic": "\U0001f4ca",
    "slides":      "\U0001f4d1",
}

def _load() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"topics": {}, "last_activity": None, "streak_days": 0}

def _save(state: dict):
    state["last_activity"] = datetime.now().isoformat(timespec="seconds")
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def _cur_state() -> dict:
    """Читає curriculum.json напряму."""
    p = Path(__file__).parent.parent / "data" / "curriculum.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"completed": [], "started": [], "notes": {}}

def get_current_progress() -> dict:
    """Повертає поточний стан навчання для /hub та proactive engine."""
    state = _load()
    cur = _cur_state()

    current_id = cur["started"][0] if cur["started"] else None
    topic_state = state["topics"].get(str(current_id), {}) if current_id else {}

    artifacts_consumed = topic_state.get("artifacts_consumed", [])
    artifacts_available = topic_state.get("artifacts_available", ["podcast", "briefing", "study_guide", "video"])
    artifacts_remaining = [a for a in artifacts_available if a not in artifacts_consumed]

    last = state.get("last_activity")
    days_inactive = 0
    if last:
        try:
            days_inactive = (datetime.now() - datetime.fromisoformat(last)).days
        except Exception:
            pass

    # Streak
    streak = state.get("streak_days", 0)

    return {
        "current_topic_id": current_id,
        "artifacts_consumed": artifacts_consumed,
        "artifacts_remaining": artifacts_remaining,
        "days_inactive": days_inactive,
        "streak_days": streak,
        "completed_count": len(cur["completed"]),
    }

def mark_artifact_consumed(topic_id, artifact_type: str):
    """Позначає артефакт як переглянутий."""
    state = _load()
    key = str(topic_id)
    if key not in state["topics"]:
        state["topics"][key] = {
            "artifacts_consumed": [],
            "artifacts_available": ["podcast", "briefing", "study_guide", "video"],
        }
    consumed = state["topics"][key].get("artifacts_consumed", [])
    if artifact_type not in consumed:
        consumed.append(artifact_type)
        state["topics"][key]["artifacts_consumed"] = consumed
    _update_streak(state)
    _save(state)

def touch_activity():
    """Оновлює last_activity і streak при будь-якій активності."""
    state = _load()
    _update_streak(state)
    _save(state)

def _update_streak(state: dict):
    last = state.get("last_activity")
    if not last:
        state["streak_days"] = 1
        return
    try:
        last_dt = datetime.fromisoformat(last)
        delta = (datetime.now() - last_dt).days
        if delta == 0:
            pass  # той самий день
        elif delta == 1:
            state["streak_days"] = state.get("streak_days", 0) + 1
        else:
            state["streak_days"] = 1  # streak broken
    except Exception:
        state["streak_days"] = 1
