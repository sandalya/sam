"""
/activate — інлайн-клавіатура для переключення стану тем (pending ↔ active).

Mastered теми показуються іконкою ✅ але не редагуються через цей модуль —
керуй через /exam.

Callback patterns:
  act_islands              — назад до списку островів
  act_island_{island_id}   — показати теми острова
  act_toggle_{topic_id}    — перемкнути pending ↔ active
"""
from __future__ import annotations

import logging
from collections import defaultdict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from curriculum.storage import load, save
from curriculum.mutations import set_topic_state
from modules.base import DATA_DIR

log = logging.getLogger(__name__)

CURRICULUM_PATH = DATA_DIR / "curriculum.json"

STATE_ICONS = {"pending": "⚪", "active": "🟢", "mastered": "✅"}


def _build_islands_keyboard(state) -> InlineKeyboardMarkup:
    """Клавіатура з островами + лічильниками."""
    topics_by_island: dict[str, list] = defaultdict(list)
    for t in state.topics:
        topics_by_island[t.island_id].append(t)

    rows = []
    for island in sorted(state.islands, key=lambda x: x.order):
        topics = topics_by_island.get(island.id, [])
        if not topics:
            continue
        active_n = sum(1 for t in topics if t.state == "active")
        pending_n = sum(1 for t in topics if t.state == "pending")
        mastered_n = sum(1 for t in topics if t.state == "mastered")
        label = f"🏝 {island.title}  {active_n}🟢 / {pending_n}⚪ / {mastered_n}✅"
        rows.append([InlineKeyboardButton(label, callback_data=f"act_island_{island.id}")])

    return InlineKeyboardMarkup(rows)


def _build_topics_keyboard(state, island_id: str) -> InlineKeyboardMarkup:
    """Клавіатура з темами острова."""
    topics = [t for t in state.topics if t.island_id == island_id]
    topics.sort(key=lambda t: t.id)

    rows = []
    for topic in topics:
        icon = STATE_ICONS.get(topic.state, "?")
        # обрізаємо занадто довгі назви
        title = topic.title if len(topic.title) <= 40 else topic.title[:37] + "..."
        label = f"{icon} {title}"
        rows.append([InlineKeyboardButton(label, callback_data=f"act_toggle_{topic.id}")])

    rows.append([InlineKeyboardButton("← Назад до островів", callback_data="act_islands")])
    return InlineKeyboardMarkup(rows)


def _islands_text(state) -> str:
    return (
        "🎯 <b>Активація тем</b>\n\n"
        "Обери острів щоб побачити теми. "
        "Клік по темі → перемикає <code>pending ↔ active</code>.\n"
        "Mastered-теми недоступні для редагування тут (використовуй /exam).\n\n"
        f"📊 Всього: {len(state.topics)} тем у {len(state.islands)} островах"
    )


def _topics_text(state, island_id: str) -> str:
    island = next((i for i in state.islands if i.id == island_id), None)
    if not island:
        return "❌ Острів не знайдено"
    topics = [t for t in state.topics if t.island_id == island_id]
    active_n = sum(1 for t in topics if t.state == "active")
    pending_n = sum(1 for t in topics if t.state == "pending")
    mastered_n = sum(1 for t in topics if t.state == "mastered")
    return (
        f"🏝 <b>{island.title}</b>\n\n"
        f"{island.description}\n\n"
        f"📊 {active_n}🟢 active · {pending_n}⚪ pending · {mastered_n}✅ mastered\n"
        f"Клік по темі → toggle pending/active."
    )


async def cmd_activate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /activate — показує список островів."""
    state = load(CURRICULUM_PATH)
    await update.message.reply_text(
        _islands_text(state),
        reply_markup=_build_islands_keyboard(state),
        parse_mode="HTML",
    )


async def handle_activate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Роутер для всіх act_* callbacks."""
    query = update.callback_query
    data = query.data

    state = load(CURRICULUM_PATH)

    # Назад до списку островів
    if data == "act_islands":
        await query.answer()
        await query.edit_message_text(
            _islands_text(state),
            reply_markup=_build_islands_keyboard(state),
            parse_mode="HTML",
        )
        return

    # Показати теми острова
    if data.startswith("act_island_"):
        island_id = data[len("act_island_"):]
        await query.answer()
        await query.edit_message_text(
            _topics_text(state, island_id),
            reply_markup=_build_topics_keyboard(state, island_id),
            parse_mode="HTML",
        )
        return

    # Toggle стану теми
    if data.startswith("act_toggle_"):
        topic_id = data[len("act_toggle_"):]
        topic = next((t for t in state.topics if t.id == topic_id), None)

        if not topic:
            await query.answer("❌ Тема не знайдена", show_alert=True)
            return

        if topic.state == "mastered":
            await query.answer(
                "✅ Тема mastered — керуй через /exam",
                show_alert=True,
            )
            return

        # pending ↔ active
        new_state = "active" if topic.state == "pending" else "pending"
        set_topic_state(state, topic_id, new_state)
        save(state, CURRICULUM_PATH)

        log.info(f"/activate: {topic_id} {topic.state} → {new_state}")

        icon = STATE_ICONS[new_state]
        await query.answer(f"{icon} {topic.title[:30]} → {new_state}")

        # Перечитуємо стан і оновлюємо клавіатуру
        state = load(CURRICULUM_PATH)
        await query.edit_message_text(
            _topics_text(state, topic.island_id),
            reply_markup=_build_topics_keyboard(state, topic.island_id),
            parse_mode="HTML",
        )
        return

    await query.answer("Unknown callback")
