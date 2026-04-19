"""
sam/core/tools.py — SAM_TOOLS definitions + execute_tool handler.

Phase 2.6: переписано на shared.curriculum v2 API.
- curriculum.json як єдине джерело правди
- NBLM notebook_id зберігається в topic.nblm_notebook_id
- Формати: slides, podcast_nblm, podcast_tts, video, infographic, flashcards, exam
- Стани теми: pending, active, mastered
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger("sam")

CURRICULUM_FILENAME = "curriculum.json"

# Канонічний список форматів v2 (синхронізовано з shared.curriculum.ALLOWED_FORMATS)
_V2_FORMAT_KEYS = ["slides", "podcast_nblm", "podcast_tts", "video", "infographic", "flashcards", "exam"]

SAM_TOOLS = [
    {
        "name": "get_learning_state",
        "description": "Отримує поточний стан курікулома: counts (pending/active/mastered), список активних тем з коротким описом прогресу.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "update_progress",
        "description": "Позначає формат контенту як спожитий (чекбокс 'я послухав/подивився') для певної теми.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic_id": {
                    "type": "string",
                    "description": "ID теми у форматі '{island-slug}-{n}', напр. 'agent_architecture-1'"
                },
                "format_key": {
                    "type": "string",
                    "enum": _V2_FORMAT_KEYS,
                    "description": "Ключ формату (slides, podcast_nblm, podcast_tts, video, infographic, flashcards, exam)"
                }
            },
            "required": ["topic_id", "format_key"]
        }
    },
    {
        "name": "search_notebooks",
        "description": "Шукає теми які мають прив'язаний NotebookLM за назвою або ключовим словом.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Пошуковий запит (case-insensitive substring по title)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "advance_topic",
        "description": "Повертає наступну тему для вивчення. Пріоритет: pending → active. Показує title/why/read/do і стан форматів.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_hub",
        "description": "Генерує короткий dashboard: загальний стан курікулома, острови, активні теми, прогрес по форматах.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
]


def _load_state(data_dir: Path):
    """Завантажує curriculum.json через shared.curriculum.load. Повертає CurriculumState або None якщо файлу немає."""
    from shared.curriculum import load
    path = data_dir / CURRICULUM_FILENAME
    if not path.exists():
        return None
    return load(path)


def _resolve_topic_id(state, topic_id_raw) -> str | None:
    """
    Нормалізує topic_id. Приймає str ('agent_architecture-1') або int (legacy 1..18).
    Повертає нормалізований str id або None якщо не знайшли.
    """
    if isinstance(topic_id_raw, int):
        # Legacy int ID — шукаємо за legacy_id
        for t in state.topics:
            if t.legacy_id == topic_id_raw:
                return t.id
        return None
    if isinstance(topic_id_raw, str):
        # Спершу — прямий match
        if state.get_topic(topic_id_raw):
            return topic_id_raw
        # Спроба як legacy int у вигляді рядка
        try:
            lid = int(topic_id_raw)
            for t in state.topics:
                if t.legacy_id == lid:
                    return t.id
        except ValueError:
            pass
    return None


# ── Handlers для кожного tool ────────────────────────────────────────────────

def _h_get_learning_state(state) -> str:
    counts = state.counts()
    active = state.topics_by_state("active")
    lines = [
        f"Курікулом: {counts['total']} тем у {counts['islands']} островах.",
        f"Pending: {counts['pending']} | Active: {counts['active']} | Mastered: {counts['mastered']}.",
        "",
        "Активні теми:",
    ]
    for t in active:
        ready = t.formats_ready_count()
        consumed = t.formats_consumed_count()
        total_fmt = len(t.formats)
        lines.append(f"• {t.id} — {t.title} ({consumed}/{ready} спожито/готово з {total_fmt} форматів)")
    return "\n".join(lines) if active else "Немає активних тем."


def _h_update_progress(state, data_dir: Path, input_data: dict) -> str:
    from shared.curriculum import save, mark_format_consumed, ALLOWED_FORMATS

    topic_id_raw = input_data.get("topic_id")
    format_key = input_data.get("format_key")

    if not format_key or format_key not in ALLOWED_FORMATS:
        return f"Невалідний format_key: {format_key!r}. Дозволені: {', '.join(ALLOWED_FORMATS)}"

    topic_id = _resolve_topic_id(state, topic_id_raw)
    if not topic_id:
        return f"Тему {topic_id_raw!r} не знайдено."

    try:
        mark_format_consumed(state, topic_id, format_key, consumed=True)
        save(state, data_dir / CURRICULUM_FILENAME)
        topic = state.get_topic(topic_id)
        return f"Позначено як спожите: {topic.title} → {format_key}"
    except Exception as e:
        logger.error(f"mark_format_consumed failed: {e}", exc_info=True)
        return f"Помилка: {e}"


def _h_search_notebooks(state, input_data: dict) -> str:
    query = input_data.get("query", "").strip().lower()
    if not query:
        return "Порожній запит."

    results = []
    for t in state.topics:
        if not t.nblm_notebook_id:
            continue
        if query in t.title.lower() or query in t.id.lower():
            url = f"https://notebooklm.google.com/notebook/{t.nblm_notebook_id}"
            ready_formats = [k for k, f in t.formats.items() if f.status == "ready"]
            formats_str = ", ".join(ready_formats) if ready_formats else "formats pending"
            results.append(f"• {t.title} ({t.id}) — {url}\n  формати: {formats_str}")

    if not results:
        return f"Нічого не знайдено по '{query}'."
    return f"Знайдено {len(results)} notebook(s):\n\n" + "\n\n".join(results)


def _h_advance_topic(state) -> str:
    pending = state.topics_by_state("pending")
    if pending:
        t = pending[0]
        header = f"Наступна тема (pending): {t.title} [{t.id}]"
    else:
        active = state.topics_by_state("active")
        if not active:
            return "Всі теми в стані mastered. Час додати нову через /cur_add."
        t = active[0]
        header = f"Pending тем немає. Перша активна: {t.title} [{t.id}]"

    lines = [header]
    if t.why:
        lines.append(f"\nНавіщо: {t.why}")
    if t.read:
        lines.append(f"Читати: {t.read}")
    if t.do:
        lines.append(f"Практика: {t.do}")

    if t.formats:
        lines.append("\nФормати:")
        for key, fmt in t.formats.items():
            mark = "✓" if fmt.consumed else ("●" if fmt.status == "ready" else "○")
            lines.append(f"  {mark} {key}: {fmt.status}")
    else:
        lines.append("\n(формати ще не згенеровано)")

    return "\n".join(lines)


def _h_get_hub(state) -> str:
    counts = state.counts()
    lines = [
        "📚 Курікулом",
        f"Вектор: {state.learning_vector or '(не задано)'}",
        "",
        f"Всього: {counts['total']} тем у {counts['islands']} островах",
        f"  🟡 Pending: {counts['pending']}",
        f"  🟢 Active: {counts['active']}",
        f"  ✅ Mastered: {counts['mastered']}",
        "",
        "Острови:",
    ]
    for island in state.islands:
        topics_here = state.topics_in_island(island.id)
        if not topics_here:
            lines.append(f"  🏝 {island.title} (порожньо)")
            continue
        ready_sum = sum(t.formats_ready_count() for t in topics_here)
        consumed_sum = sum(t.formats_consumed_count() for t in topics_here)
        lines.append(f"  🏝 {island.title}: {len(topics_here)} тем, {consumed_sum}/{ready_sum} спожито/готово")

    active = state.topics_by_state("active")
    if active:
        lines.append("")
        lines.append("Активні теми:")
        for t in active[:5]:
            lines.append(f"  • {t.title} [{t.id}]")
        if len(active) > 5:
            lines.append(f"  … ще {len(active) - 5}")

    return "\n".join(lines)


# ── Диспетчер ────────────────────────────────────────────────────────────────

def execute_tool(name: str, input_data: dict, data_dir: Path) -> str:
    """Виконує tool call і повертає результат як string."""
    try:
        state = _load_state(data_dir)
        if state is None:
            return f"curriculum.json не знайдено в {data_dir}. Курікулом не ініціалізовано."

        if name == "get_learning_state":
            return _h_get_learning_state(state)
        elif name == "update_progress":
            return _h_update_progress(state, data_dir, input_data)
        elif name == "search_notebooks":
            return _h_search_notebooks(state, input_data)
        elif name == "advance_topic":
            return _h_advance_topic(state)
        elif name == "get_hub":
            return _h_get_hub(state)
        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        logger.error(f"execute_tool {name} error: {e}", exc_info=True)
        return f"Помилка виконання {name}: {e}"
