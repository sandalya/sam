"""
sam/modules/state_manager.py — activity & streak tracking + зручний фасад
для proactive engine.

Після Phase 2.7:
  - Activity (last_activity, streak_days) живе у data/learning_state.json.
  - Curriculum-стан (active topics, formats, consumed) читається з
    shared.curriculum (єдине джерело правди).
  - Legacy `mark_artifact_consumed` видалений — його роль виконує
    shared.curriculum.mark_format_consumed, який викликають tools.
  - Legacy `_cur_state` видалений — прямо читаємо v2 state.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("sam")

STATE_FILE = Path(__file__).parent.parent / "data" / "learning_state.json"
DATA_DIR   = Path(__file__).parent.parent / "data"

# ── Іконки форматів ────────────────────────────────────────────────────────────
# v2-ключі — канонічні (ALLOWED_FORMATS з shared.curriculum).
# legacy-ключі лишаються як fallback: старі записи у learning_state.json
# (якщо які і дотягнули) та proactive.ARTIFACT_ICONS.get(a, ...) не впаде.
ARTIFACT_ICONS = {
    # v2
    "slides":        "\U0001f4d1",  # 📑
    "podcast_nblm":  "\U0001f399",  # 🎙
    "podcast_tts":   "\U0001f3a7",  # 🎧
    "video":         "\U0001f3a5",  # 🎥
    "infographic":   "\U0001f4ca",  # 📊
    "flashcards":    "\U0001f0cf",  # 🃏
    "exam":          "\U0001f4dd",  # 📝
    # legacy fallback
    "podcast":       "\U0001f399",  # 🎙
    "briefing":      "\U0001f4cb",  # 📋
    "study_guide":   "\U0001f4d8",  # 📘
}


# ── Activity state (learning_state.json) ───────────────────────────────────────
def _load() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"state_manager: cannot parse {STATE_FILE.name}: {e}")
    return {"topics": {}, "last_activity": None, "streak_days": 0}


def _save(state: dict):
    state["last_activity"] = datetime.now().isoformat(timespec="seconds")
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _update_streak(state: dict):
    last = state.get("last_activity")
    if not last:
        state["streak_days"] = 1
        return
    try:
        last_dt = datetime.fromisoformat(last)
        delta = (datetime.now() - last_dt).days
        if delta == 0:
            pass  # той самий день — streak не чіпаємо
        elif delta == 1:
            state["streak_days"] = state.get("streak_days", 0) + 1
        else:
            state["streak_days"] = 1  # streak broken
    except Exception:
        state["streak_days"] = 1


def touch_activity():
    """Оновлює last_activity і streak при будь-якій активності."""
    state = _load()
    _update_streak(state)
    _save(state)


# ── Progress facade для proactive engine ──────────────────────────────────────
def get_current_progress() -> dict:
    """Повертає поточний стан навчання для proactive engine.

    Контракт (dict-поля, стабільні для proactive.py):
      - current_topic_id: str | None — перша active тема (legacy behavior).
      - artifacts_consumed: list[str] — формат-ключі, що позначені consumed.
      - artifacts_remaining: list[str] — формат-ключі зі status='ready' і
        ще не consumed (тільки реально доступні матеріали).
      - days_inactive: int — днів з last_activity.
      - streak_days: int.
      - completed_count: int — загальна кількість mastered тем.
    """
    # Activity
    state = _load()
    last = state.get("last_activity")
    days_inactive = 0
    if last:
        try:
            days_inactive = (datetime.now() - datetime.fromisoformat(last)).days
        except Exception:
            pass
    streak = state.get("streak_days", 0)

    # Curriculum (v2)
    current_id = None
    artifacts_consumed: list[str] = []
    artifacts_remaining: list[str] = []
    completed_count = 0
    try:
        from shared.curriculum import load as load_curriculum
        cur = load_curriculum(DATA_DIR / "curriculum.json")
        active_topics = cur.topics_by_state("active")
        if active_topics:
            topic = active_topics[0]
            current_id = topic.id
            for key, fmt in topic.formats.items():
                if fmt.consumed:
                    artifacts_consumed.append(key)
                elif fmt.status == "ready":
                    artifacts_remaining.append(key)
        completed_count = len(cur.topics_by_state("mastered"))
    except Exception as e:
        logger.warning(f"state_manager: curriculum load failed: {e}")

    return {
        "current_topic_id": current_id,
        "artifacts_consumed": artifacts_consumed,
        "artifacts_remaining": artifacts_remaining,
        "days_inactive": days_inactive,
        "streak_days": streak,
        "completed_count": completed_count,
    }
