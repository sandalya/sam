"""
shared/curriculum/mutations.py — чисті функції зміни стану CurriculumState.

Всі мутації:
- приймають CurriculumState (модифікують in-place)
- оновлюють updated_at/mastered_at автоматично
- кидають ValueError на неіснуючі ID або невалідні переходи
- НЕ пишуть на диск (це робить storage.save окремо)

Pattern використання в хендлерах:
    state = load(path)
    add_topic(state, island_id="agents", title="...", why="...")
    save(state, path)

Референс: DATA_MODEL.md §1, CURRICULUM_MANIFEST.md §4.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from .models import (
    CurriculumState, Island, Topic, TopicFormat,
    TopicState, ContentStyle, FormatStatus, FormatKey,
    ALLOWED_FORMATS, ALLOWED_TOPIC_STATES, ALLOWED_CONTENT_STYLES,
    ALLOWED_FORMAT_STATUSES,
)

log = logging.getLogger("curriculum.mutations")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ─── Island mutations ─────────────────────────────────────────────────────────

def add_island(
    state: CurriculumState,
    *,
    island_id: str,
    title: str,
    description: str = "",
    order: Optional[int] = None,
) -> Island:
    """Додає новий острів. Кидає ValueError якщо id вже існує."""
    if state.get_island(island_id):
        raise ValueError(f"Island {island_id!r} already exists")
    if not island_id or " " in island_id:
        raise ValueError(f"Invalid island id: {island_id!r}")

    if order is None:
        order = max((i.order for i in state.islands), default=-1) + 1

    island = Island(
        id=island_id,
        title=title,
        description=description,
        order=order,
    )
    state.islands.append(island)
    log.info(f"Added island: {island_id} ({title})")
    return island


# ─── Topic mutations ──────────────────────────────────────────────────────────

def _next_topic_id(state: CurriculumState, island_id: str) -> str:
    """Обчислює наступний id вигляду {island_id}-{n} з гарантованою унікальністю."""
    existing = [
        t.id for t in state.topics
        if t.island_id == island_id or t.id.startswith(f"{island_id}-")
    ]
    # Знаходимо максимальний суфікс-номер
    max_n = 0
    for tid in existing:
        parts = tid.rsplit("-", 1)
        if len(parts) == 2 and parts[0] == island_id and parts[1].isdigit():
            max_n = max(max_n, int(parts[1]))
    return f"{island_id}-{max_n + 1}"


def add_topic(
    state: CurriculumState,
    *,
    island_id: str,
    title: str,
    why: str = "",
    read: str = "",
    do: str = "",
    estimate: str = "",
    content_style: ContentStyle = "audio",
    initial_state: TopicState = "pending",
    parent_topic_id: Optional[str] = None,
    crosslinks: Optional[list[str]] = None,
    topic_id: Optional[str] = None,
) -> Topic:
    """
    Додає тему в острів. Генерує id {island}-{n} якщо не передано.

    Кидає ValueError якщо:
    - острів не існує
    - topic_id явно переданий і вже зайнятий
    - parent_topic_id не існує
    """
    if not state.get_island(island_id):
        raise ValueError(f"Island {island_id!r} does not exist")
    if content_style not in ALLOWED_CONTENT_STYLES:
        raise ValueError(f"Invalid content_style: {content_style!r}")
    if initial_state not in ALLOWED_TOPIC_STATES:
        raise ValueError(f"Invalid state: {initial_state!r}")
    if parent_topic_id and not state.get_topic(parent_topic_id):
        raise ValueError(f"Parent topic {parent_topic_id!r} does not exist")

    if topic_id is None:
        topic_id = _next_topic_id(state, island_id)
    elif state.get_topic(topic_id):
        raise ValueError(f"Topic {topic_id!r} already exists")

    topic = Topic(
        id=topic_id,
        island_id=island_id,
        title=title,
        why=why,
        read=read,
        do=do,
        estimate=estimate,
        state=initial_state,
        content_style=content_style,
        parent_topic_id=parent_topic_id,
        crosslinks=list(crosslinks or []),
    )
    state.topics.append(topic)
    log.info(f"Added topic: {topic_id} ({title}) in island {island_id}")
    return topic


def set_topic_state(
    state: CurriculumState,
    topic_id: str,
    new_state: TopicState,
) -> Topic:
    """
    Міняє стан теми. Якщо new_state="mastered" — виставляє mastered_at.
    Якщо виходимо з mastered — скидаємо mastered_at.
    """
    if new_state not in ALLOWED_TOPIC_STATES:
        raise ValueError(f"Invalid state: {new_state!r}")

    topic = state.get_topic(topic_id)
    if not topic:
        raise ValueError(f"Topic {topic_id!r} does not exist")

    now = _now()
    if topic.state == new_state:
        log.debug(f"Topic {topic_id} already in state {new_state}, no-op")
        return topic

    topic.state = new_state
    topic.updated_at = now

    if new_state == "mastered":
        topic.mastered_at = now
    elif topic.mastered_at:
        topic.mastered_at = None

    log.info(f"Topic {topic_id}: state → {new_state}")
    return topic


def update_topic_fields(
    state: CurriculumState,
    topic_id: str,
    **fields,
) -> Topic:
    """
    Оновлює прості поля теми (title, why, read, do, estimate, content_style).
    Оновлює updated_at автоматично.
    """
    ALLOWED_FIELDS = {"title", "why", "read", "do", "estimate", "content_style"}
    topic = state.get_topic(topic_id)
    if not topic:
        raise ValueError(f"Topic {topic_id!r} does not exist")

    for k, v in fields.items():
        if k not in ALLOWED_FIELDS:
            raise ValueError(f"Cannot update field {k!r} via update_topic_fields")
        if k == "content_style" and v not in ALLOWED_CONTENT_STYLES:
            raise ValueError(f"Invalid content_style: {v!r}")
        setattr(topic, k, v)

    topic.updated_at = _now()
    return topic


def remove_topic(state: CurriculumState, topic_id: str) -> Topic:
    """
    Видаляє тему. Кидає ValueError якщо в теми є підтеми
    (треба спочатку видалити їх) або якщо тема згадана в crosslinks інших тем.
    """
    topic = state.get_topic(topic_id)
    if not topic:
        raise ValueError(f"Topic {topic_id!r} does not exist")

    children = state.child_topics(topic_id)
    if children:
        raise ValueError(
            f"Cannot remove {topic_id!r}: has {len(children)} subtopics"
        )

    referenced_by = [t.id for t in state.topics if topic_id in t.crosslinks]
    if referenced_by:
        raise ValueError(
            f"Cannot remove {topic_id!r}: referenced by crosslinks in {referenced_by}"
        )

    state.topics.remove(topic)
    log.info(f"Removed topic: {topic_id}")
    return topic


# ─── Format mutations ─────────────────────────────────────────────────────────

def _get_or_create_format(topic: Topic, format_key: str) -> TopicFormat:
    if format_key not in ALLOWED_FORMATS:
        raise ValueError(f"Unknown format key: {format_key!r}")
    if format_key not in topic.formats:
        topic.formats[format_key] = TopicFormat()
    return topic.formats[format_key]


def set_format_status(
    state: CurriculumState,
    topic_id: str,
    format_key: str,
    status: FormatStatus,
    *,
    url: Optional[str] = None,
    error: Optional[str] = None,
) -> TopicFormat:
    """
    Оновлює статус формату. Якщо status=ready — виставляє generated_at та url (якщо переданий).
    Якщо status=failed — пише error. Інші статуси чистять error.
    """
    if status not in ALLOWED_FORMAT_STATUSES:
        raise ValueError(f"Invalid format status: {status!r}")
    topic = state.get_topic(topic_id)
    if not topic:
        raise ValueError(f"Topic {topic_id!r} does not exist")

    fmt = _get_or_create_format(topic, format_key)
    fmt.status = status
    now = _now()

    if status == "ready":
        fmt.generated_at = now
        if url is not None:
            fmt.url = url
        fmt.error = None
    elif status == "failed":
        fmt.error = error or "unknown"
    else:
        fmt.error = None

    topic.updated_at = now
    log.info(f"Topic {topic_id}.formats[{format_key}]: status → {status}")
    return fmt


def set_format_url(
    state: CurriculumState,
    topic_id: str,
    format_key: str,
    url: str,
) -> TopicFormat:
    """Оновлює лише URL формату. Не змінює status."""
    topic = state.get_topic(topic_id)
    if not topic:
        raise ValueError(f"Topic {topic_id!r} does not exist")
    fmt = _get_or_create_format(topic, format_key)
    fmt.url = url
    topic.updated_at = _now()
    return fmt


def mark_format_consumed(
    state: CurriculumState,
    topic_id: str,
    format_key: str,
    *,
    consumed: bool = True,
) -> TopicFormat:
    """
    Позначає формат як спожитий (чекбокс "я послухав/подивився").
    Ставить consumed_at в now якщо consumed=True.
    """
    topic = state.get_topic(topic_id)
    if not topic:
        raise ValueError(f"Topic {topic_id!r} does not exist")

    fmt = _get_or_create_format(topic, format_key)
    fmt.consumed = consumed
    fmt.consumed_at = _now() if consumed else None
    topic.updated_at = _now()
    log.info(f"Topic {topic_id}.formats[{format_key}]: consumed → {consumed}")
    return fmt


def set_nblm_notebook_id(
    state: CurriculumState,
    topic_id: str,
    notebook_id: Optional[str],
) -> Topic:
    """
    Встановлює або очищує NBLM notebook_id для теми.
    Один notebook на тему — всі NBLM-формати (slides/podcast_nblm/video/...) беруть з нього.
    """
    topic = state.get_topic(topic_id)
    if not topic:
        raise ValueError(f"Topic {topic_id!r} does not exist")
    topic.nblm_notebook_id = notebook_id
    topic.updated_at = _now()
    log.info(f"Topic {topic_id}: nblm_notebook_id → {notebook_id}")
    return topic
