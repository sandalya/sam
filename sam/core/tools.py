"""
sam/core/tools.py — SAM_TOOLS definitions + execute_tool handler.
Фаза 5: Tool Use через Anthropic API.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger("sam")

SAM_TOOLS = [
    {
        "name": "get_learning_state",
        "description": "Отримує поточний стан навчання: яка тема активна, що переглянуто, прогрес.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "update_progress",
        "description": "Позначає артефакт як переглянутий для певної теми.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic_id": {"type": "string", "description": "ID теми"},
                "artifact_type": {
                    "type": "string",
                    "enum": ["podcast", "briefing", "study_guide", "flashcards", "video", "infographic", "slides"]
                }
            },
            "required": ["topic_id", "artifact_type"]
        }
    },
    {
        "name": "search_notebooks",
        "description": "Шукає NotebookLM контент по назві теми або ключовим словам.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Пошуковий запит"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "advance_topic",
        "description": "Переходить до наступної теми в курикулумі.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_hub",
        "description": "Генерує dashboard повідомлення з поточним прогресом.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
]


def execute_tool(name: str, input_data: dict, data_dir: Path) -> str:
    """Виконує tool call і повертає результат як string."""
    try:
        if name == "get_learning_state":
            from modules.state_manager import get_current_progress
            return json.dumps(get_current_progress(), ensure_ascii=False)

        elif name == "update_progress":
            from modules.state_manager import mark_artifact_consumed
            mark_artifact_consumed(input_data["topic_id"], input_data["artifact_type"])
            return f"OK: {input_data['artifact_type']} для теми {input_data['topic_id']} відмічено"

        elif name == "search_notebooks":
            from shared.notebooklm_module import load_nb_state
            from modules.curriculum import _get as _get_cur, load_state as _load_cur_state
            nb_state = load_nb_state(data_dir)
            query = input_data["query"].lower()
            # Завантажуємо назви тем
            inst = _get_cur()
            cur_state = _load_cur_state()
            profile = inst.load_profile()
            all_topics = inst.get_full_curriculum(cur_state, profile)
            topic_names = {str(t["id"]): t["title"] for t in all_topics}
            results = []
            for tid, entry in nb_state.items():
                if not isinstance(entry, dict):
                    continue
                nb_id = entry.get("notebook_id")
                generated = entry.get("generated", [])
                title = topic_names.get(tid, "")
                if nb_id and (query in title.lower() or query in str(tid)):
                    results.append({"topic_id": tid, "title": title, "notebook_id": nb_id, "generated": generated})
            return json.dumps(results, ensure_ascii=False) if results else "Нічого не знайдено"

        elif name == "advance_topic":
            from modules.curriculum import _get as _get_cur, load_state as _load_cur_state
            inst = _get_cur()
            cur_state = _load_cur_state()
            profile = inst.load_profile()
            all_topics = inst.get_full_curriculum(cur_state, profile)
            completed_ids = set(cur_state.get("completed", []))
            started_ids = set(cur_state.get("started", []))
            # Знаходимо першу тему що не completed і не started
            for t in all_topics:
                if t["id"] not in completed_ids and t["id"] not in started_ids:
                    return json.dumps({"next_topic_id": t["id"], "title": t["title"]}, ensure_ascii=False)
            # Якщо всі started — беремо першу started
            for t in all_topics:
                if t["id"] in started_ids:
                    return json.dumps({"current_topic_id": t["id"], "title": t["title"]}, ensure_ascii=False)
            return "Всі теми завершено"

        elif name == "get_hub":
            from modules.state_manager import get_current_progress, _load
            progress = get_current_progress()
            state = _load()
            cur_path = data_dir / "curriculum.json"
            cur = json.loads(cur_path.read_text()) if cur_path.exists() else {}
            completed = len(cur.get("completed", []))
            total = completed + len(cur.get("started", [])) + len(cur.get("not_started", []))
            consumed = progress.get("artifacts_consumed", [])
            remaining = progress.get("artifacts_remaining", [])
            streak = progress.get("streak_days", 0)
            days_inactive = progress.get("days_inactive", 0)
            lines = [
                f"Завершено тем: {completed}",
                f"Поточна тема ID: {progress.get('current_topic_id', '—')}",
                f"Переглянуто артефактів: {', '.join(consumed) or 'нічого'}",
                f"Залишилось: {', '.join(remaining) or 'все переглянуто'}",
                f"Страйк: {streak} дн.",
                f"Неактивних днів: {days_inactive}",
            ]
            return "\n".join(lines)

        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        logger.error(f"execute_tool {name} error: {e}", exc_info=True)
        return f"Помилка виконання {name}: {e}"
