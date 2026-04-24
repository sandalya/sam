"""
modules/flashcards.py — Flashcards interactive FSM (Phase 6.1).

Два режими презентації одного deck:
  - flashcard mode: recall (показати відповідь / знаю / не знаю)
  - quiz mode:      recognition (4 варіанти, клікнути)

Публічне API:
    start_flashcards(bot, chat_id, topic_id, data_dir)
    handle_flashcards_callback(update, context)

Callback-data формат:
    fc_mode_{topic_id}_{card|quiz}
    fc_show_{topic_id}_{idx}         — показати відповідь (flashcard mode)
    fc_know_{topic_id}_{idx}
    fc_dunno_{topic_id}_{idx}
    fc_pick_{topic_id}_{idx}_{choice}   — обрати варіант 0-3 (quiz mode)
    fc_next_{topic_id}_{idx}
    fc_retry_{topic_id}
    fc_switch_{topic_id}_{card|quiz}   — переключити deck у інший режим після фіналу
    fc_exit_{topic_id}
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from curriculum.storage import load as load_curriculum

log = logging.getLogger("sam.flashcards")


@dataclass
class _Session:
    topic_id: str
    topic_title: str
    mode: str                        # "card" or "quiz"
    cards: list[dict] = field(default_factory=list)
    current_idx: int = 0
    known: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    shown_answer: bool = False
    shuffle_map: dict = field(default_factory=dict)   # idx -> permutation list[int]


_SESSIONS: dict[int, _Session] = {}   # chat_id -> session


def _get_curriculum_path(data_dir: Path) -> Path:
    return data_dir / "curriculum.json"


def _build_shuffle(card_idx: int, session: _Session) -> list[int]:
    """Determine permutation: position_in_UI -> source_index (0=correct, 1..3=distractors)."""
    if card_idx in session.shuffle_map:
        return session.shuffle_map[card_idx]
    perm = [0, 1, 2, 3]
    random.shuffle(perm)
    session.shuffle_map[card_idx] = perm
    return perm


async def start_flashcards(bot, chat_id: int, topic_id: str, data_dir: Path) -> None:
    """Entry point from deep-link. Shows mode picker or errors out."""
    cur_path = _get_curriculum_path(data_dir)
    state = load_curriculum(cur_path)
    topic = state.get_topic(topic_id)
    if not topic:
        await bot.send_message(chat_id, f"Тема не знайдена: {topic_id}")
        return

    fmt = topic.formats.get("flashcards")
    if not fmt or fmt.status != "ready" or not fmt.cards:
        await bot.send_message(
            chat_id,
            f"Flashcards для <b>{topic.title}</b> ще не готові.",
            parse_mode="HTML",
        )
        return

    # Mode picker
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📇 Флешкартки", callback_data=f"fc_mode_{topic_id}_card"),
        InlineKeyboardButton("🎯 Тест", callback_data=f"fc_mode_{topic_id}_quiz"),
    ]])
    await bot.send_message(
        chat_id,
        text=("📚 <b>{}</b>\n{} карток у deck\n\nОберіть режим:").format(
            _html_escape(topic.title), len(fmt.cards),
        ),
        reply_markup=kb,
        parse_mode="HTML",
    )


def _html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def handle_flashcards_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Main FSM dispatcher. Routes by callback_data prefix."""
    from modules.base import DATA_DIR
    q = update.callback_query
    data = q.data
    chat_id = update.effective_chat.id
    log.info(f"fc callback: chat={chat_id} data={data!r}")

    try:
        await q.answer()
    except Exception:
        pass

    try:
        if data.startswith("fc_mode_"):
            await _on_mode_pick(q, chat_id, data, DATA_DIR)
        elif data.startswith("fc_show_"):
            await _on_show_answer(q, chat_id, data)
        elif data.startswith("fc_know_") or data.startswith("fc_dunno_"):
            await _on_self_eval(q, chat_id, data)
        elif data.startswith("fc_pick_"):
            await _on_quiz_pick(q, chat_id, data)
        elif data.startswith("fc_next_"):
            await _on_next(q, chat_id, data)
        elif data.startswith("fc_retry_"):
            await _on_retry(q, chat_id, data)
        elif data.startswith("fc_switch_"):
            await _on_switch_mode(q, chat_id, data, DATA_DIR)
        elif data.startswith("fc_exit_"):
            await _on_exit(q, chat_id, data)
        else:
            log.warning(f"Unknown fc callback: {data}")
    except Exception as e:
        log.error(f"fc callback {data!r} failed: {e}", exc_info=True)


# ── Handlers ──────────────────────────────────────────────────────────────

async def _on_mode_pick(q, chat_id: int, data: str, data_dir: Path) -> None:
    log.info(f"fc mode_pick: chat={chat_id} data={data!r}")
    # fc_mode_{topic_id}_{card|quiz}
    rest = data[len("fc_mode_"):]
    if rest.endswith("_card"):
        mode = "card"
        topic_id = rest[:-len("_card")]
    elif rest.endswith("_quiz"):
        mode = "quiz"
        topic_id = rest[:-len("_quiz")]
    else:
        log.warning(f"Bad mode payload: {data}")
        return

    cur_path = _get_curriculum_path(data_dir)
    state = load_curriculum(cur_path)
    topic = state.get_topic(topic_id)
    if not topic or not topic.formats.get("flashcards") or not topic.formats["flashcards"].cards:
        await q.edit_message_text("Картки зникли. Спробуйте заново з pinned панелі.")
        return

    cards = list(topic.formats["flashcards"].cards)
    session = _Session(
        topic_id=topic_id,
        topic_title=topic.title,
        mode=mode,
        cards=cards,
    )
    _SESSIONS[chat_id] = session
    await _render_card(q, session)


async def _on_show_answer(q, chat_id: int, data: str) -> None:
    log.info(f"fc show_answer: chat={chat_id} data={data!r}")
    session = _SESSIONS.get(chat_id)
    if not session or session.mode != "card":
        await q.edit_message_text("Сесія завершена. Почніть заново з pinned.")
        return
    session.shown_answer = True
    await _render_card(q, session)


async def _on_self_eval(q, chat_id: int, data: str) -> None:
    log.info(f"fc self_eval: chat={chat_id} data={data!r}")
    session = _SESSIONS.get(chat_id)
    if not session or session.mode != "card":
        await q.edit_message_text("Сесія завершена.")
        return
    known = data.startswith("fc_know_")
    card = session.cards[session.current_idx]
    if known:
        session.known.append(card["id"])
    else:
        session.unknown.append(card["id"])
    session.current_idx += 1
    session.shown_answer = False
    if session.current_idx >= len(session.cards):
        await _render_final(q, session)
    else:
        await _render_card(q, session)


async def _on_quiz_pick(q, chat_id: int, data: str) -> None:
    log.info(f"fc quiz_pick: chat={chat_id} data={data!r}")
    # fc_pick_{topic_id}_{card_idx}_{choice_idx}
    session = _SESSIONS.get(chat_id)
    if not session or session.mode != "quiz":
        await q.edit_message_text("Сесія завершена.")
        return
    parts = data.split("_")
    # ["fc","pick",...topic_parts...,"{idx}","{choice}"]
    try:
        choice_idx = int(parts[-1])
        card_idx = int(parts[-2])
    except Exception:
        log.warning(f"Bad pick payload: {data}")
        return
    if card_idx != session.current_idx:
        # користувач клікнув стару картку — ігноруємо
        return
    perm = session.shuffle_map.get(card_idx, [0, 1, 2, 3])
    correct_pos = perm.index(0)
    card = session.cards[card_idx]
    is_correct = (choice_idx == correct_pos)
    if is_correct:
        session.known.append(card["id"])
    else:
        session.unknown.append(card["id"])
    await _render_quiz_feedback(q, session, card_idx, choice_idx, correct_pos, is_correct)


async def _on_next(q, chat_id: int, data: str) -> None:
    log.info(f"fc next: chat={chat_id} data={data!r}")
    session = _SESSIONS.get(chat_id)
    if not session:
        await q.edit_message_text("Сесія завершена.")
        return
    session.current_idx += 1
    session.shown_answer = False
    if session.current_idx >= len(session.cards):
        await _render_final(q, session)
    else:
        await _render_card(q, session)


async def _on_retry(q, chat_id: int, data: str) -> None:
    log.info(f"fc retry: chat={chat_id} data={data!r}")
    session = _SESSIONS.get(chat_id)
    if not session:
        await q.edit_message_text("Сесія завершена.")
        return
    unknown_ids = set(session.unknown)
    retry_cards = [c for c in session.cards if c["id"] in unknown_ids]
    if not retry_cards:
        await q.edit_message_text("Немає карток для повтору.")
        return
    session.cards = retry_cards
    session.current_idx = 0
    session.known = []
    session.unknown = []
    session.shown_answer = False
    session.shuffle_map = {}
    await _render_card(q, session)


async def _on_switch_mode(q, chat_id: int, data: str, data_dir: Path) -> None:
    log.info(f"fc switch_mode: chat={chat_id} data={data!r}")
    # fc_switch_{topic_id}_{card|quiz}
    rest = data[len("fc_switch_"):]
    if rest.endswith("_card"):
        mode = "card"
        topic_id = rest[:-len("_card")]
    elif rest.endswith("_quiz"):
        mode = "quiz"
        topic_id = rest[:-len("_quiz")]
    else:
        return
    cur_path = _get_curriculum_path(data_dir)
    state = load_curriculum(cur_path)
    topic = state.get_topic(topic_id)
    if not topic or not topic.formats.get("flashcards") or not topic.formats["flashcards"].cards:
        return
    cards = list(topic.formats["flashcards"].cards)
    session = _Session(topic_id=topic_id, topic_title=topic.title, mode=mode, cards=cards)
    _SESSIONS[chat_id] = session
    await _render_card(q, session)


async def _on_exit(q, chat_id: int, data: str) -> None:
    log.info(f"fc exit: chat={chat_id} data={data!r}")
    _SESSIONS.pop(chat_id, None)
    await q.edit_message_text("Сесію flashcards завершено.")


# ── Renderers ─────────────────────────────────────────────────────────────

async def _render_card(q, session: _Session) -> None:
    idx = session.current_idx
    card = session.cards[idx]
    total = len(session.cards)
    header = f"Картка {idx + 1}/{total}"
    topic_id = session.topic_id

    if session.mode == "card":
        if not session.shown_answer:
            text = f"{header}\n\n❓ {_html_escape(card['q'])}"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("👀 Показати відповідь", callback_data=f"fc_show_{topic_id}_{idx}")],
                [InlineKeyboardButton("🚪 Вийти", callback_data=f"fc_exit_{topic_id}")],
            ])
        else:
            text = f"{header}\n\n❓ {_html_escape(card['q'])}\n\n✅ {_html_escape(card['a'])}"
            kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Знаю", callback_data=f"fc_know_{topic_id}_{idx}"),
                    InlineKeyboardButton("❌ Не знаю", callback_data=f"fc_dunno_{topic_id}_{idx}"),
                ],
                [InlineKeyboardButton("🚪 Вийти", callback_data=f"fc_exit_{topic_id}")],
            ])
    else:  # quiz
        perm = _build_shuffle(idx, session)
        # perm[position] -> source index (0=correct, 1..3=distractors[0..2])
        source_texts = [card["a"]] + list(card["distractors"])
        options = [source_texts[perm[pos]] for pos in range(4)]
        lines = [header, "", f"❓ {_html_escape(card['q'])}"]
        text = "\n".join(lines)
        rows = []
        for pos, opt in enumerate(options):
            label = f"{pos + 1}. {opt[:55]}" if len(opt) > 55 else f"{pos + 1}. {opt}"
            rows.append([InlineKeyboardButton(label, callback_data=f"fc_pick_{topic_id}_{idx}_{pos}")])
        rows.append([InlineKeyboardButton("🚪 Вийти", callback_data=f"fc_exit_{topic_id}")])
        kb = InlineKeyboardMarkup(rows)

    await q.edit_message_text(text=text, reply_markup=kb, parse_mode="HTML")


async def _render_quiz_feedback(q, session: _Session, card_idx: int, choice_idx: int, correct_pos: int, is_correct: bool) -> None:
    card = session.cards[card_idx]
    total = len(session.cards)
    header = f"Картка {card_idx + 1}/{total}"
    if is_correct:
        text = f"{header}\n\n✅ <b>Правильно!</b>"
    else:
        text = (
            f"{header}\n\n"
            f"❌ <b>Неправильно.</b>\n\n"
            f"Правильна відповідь: {_html_escape(card['a'])}"
        )
    topic_id = session.topic_id
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Далі", callback_data=f"fc_next_{topic_id}_{card_idx}")],
        [InlineKeyboardButton("🚪 Вийти", callback_data=f"fc_exit_{topic_id}")],
    ])
    await q.edit_message_text(text=text, reply_markup=kb, parse_mode="HTML")


async def _render_final(q, session: _Session) -> None:
    topic_id = session.topic_id
    total = len(session.cards)
    n_known = len(session.known)
    n_unknown = len(session.unknown)
    lines = [
        "🏁 <b>Сесія завершена!</b>",
        "",
        f"Deck: {_html_escape(session.topic_title)}",
        f"Режим: {'Флешкартки' if session.mode == 'card' else 'Тест'}",
        f"Всього: {total}",
        f"✅ Знаю: {n_known}",
        f"❌ Не знаю: {n_unknown}",
    ]
    text = "\n".join(lines)
    rows = []
    if n_unknown > 0:
        rows.append([InlineKeyboardButton("🔄 Повторити невідомі", callback_data=f"fc_retry_{topic_id}")])
    # Переключення режимів на той самий deck
    if session.mode == "card":
        rows.append([InlineKeyboardButton("🎯 Цей deck як тест", callback_data=f"fc_switch_{topic_id}_quiz")])
    else:
        rows.append([InlineKeyboardButton("📇 Цей deck як флешкартки", callback_data=f"fc_switch_{topic_id}_card")])
    rows.append([InlineKeyboardButton("🚪 Вийти", callback_data=f"fc_exit_{topic_id}")])
    kb = InlineKeyboardMarkup(rows)
    await q.edit_message_text(text=text, reply_markup=kb, parse_mode="HTML")
