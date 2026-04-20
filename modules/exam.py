"""
modules/exam.py — Phase 3: діалоговий екзамен.

Stateful 5-question exam per topic. LLM генерує питання,
LLM оцінює відповіді. Сесія зберігається у data/exam_session.json.

Публічне API:
    start_exam(bot, chat_id, topic_id, data_dir)
    handle_exam_answer(bot, chat_id, text, data_dir) -> bool
    is_exam_active(data_dir) -> bool
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from shared.agent_base import client, MODEL_SMART
from curriculum import load, save, set_format_status, set_topic_state

log = logging.getLogger("sam.exam")

EXAM_SESSION_FILE = "exam_session.json"
NUM_QUESTIONS = 5
PASS_THRESHOLD = 3  # мінімум правильних із 5


# ── Session persistence ──────────────────────────────────────────────────────

def _session_path(data_dir: Path) -> Path:
    return data_dir / EXAM_SESSION_FILE


def _load_session(data_dir: Path) -> Optional[dict]:
    p = _session_path(data_dir)
    if not p.exists():
        return None
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return None


def _save_session(data_dir: Path, session: dict):
    p = _session_path(data_dir)
    with open(p, "w") as f:
        json.dump(session, f, ensure_ascii=False, indent=2)


def _clear_session(data_dir: Path):
    p = _session_path(data_dir)
    if p.exists():
        p.unlink()


def is_exam_active(data_dir: Path) -> bool:
    session = _load_session(data_dir)
    return session is not None and session.get("status") == "active"


# ── Question generation ──────────────────────────────────────────────────────

def _generate_questions(topic_title: str, why: str, read: str, do: str) -> list[str]:
    """Генерує 5 питань по темі через LLM."""
    prompt = f"""You are an AI tutor creating an exam for a developer learning about AI agents.

Topic: {topic_title}
Why it matters: {why}
Key resource: {read}
Practice: {do}

Generate exactly {NUM_QUESTIONS} exam questions about this topic.
Questions should test practical understanding, not just definitions.
Mix question types: conceptual, scenario-based, and implementation.
Questions should be in English.

Return ONLY a JSON array of {NUM_QUESTIONS} strings, no other text.
Example: ["Question 1?", "Question 2?", "Question 3?", "Question 4?", "Question 5?"]"""

    response = client.messages.create(
        model=MODEL_SMART,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    questions = json.loads(text)
    if not isinstance(questions, list) or len(questions) != NUM_QUESTIONS:
        raise ValueError(f"Expected {NUM_QUESTIONS} questions, got {len(questions) if isinstance(questions, list) else 'non-list'}")
    return questions


# ── Answer evaluation ────────────────────────────────────────────────────────

def _evaluate_answer(topic_title: str, question: str, answer: str) -> dict:
    """Оцінює відповідь через LLM. Повертає {correct: bool, score: int, feedback: str}."""
    prompt = f"""You are an AI tutor evaluating a developer's exam answer.

Topic: {topic_title}
Question: {question}
Student's answer: {answer}

Evaluate the answer. Be fair but rigorous — the student should demonstrate real understanding.
A partial answer can still pass if it shows correct thinking.

Return ONLY a JSON object:
{{
  "correct": true/false,
  "score": 0-10,
  "feedback": "Brief feedback in Ukrainian (2-3 sentences max)"
}}"""

    response = client.messages.create(
        model=MODEL_SMART,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return json.loads(text)


def _generate_subtopic_title(parent_title: str) -> str:
    """Генерує назву підтеми на основі слабких місць екзамену."""
    prompt = f"""A developer just failed or partially failed an exam on "{parent_title}".
Based on the topic, suggest ONE focused subtopic title that would help fill knowledge gaps.
The subtopic should be specific and actionable, not just a repeat of the parent topic.
Return ONLY the subtopic title as a plain string, no quotes, no explanation.
Example: if parent is "RAG — Retrieval Augmented Generation", subtopic might be "Chunking Strategies & Overlap Tuning"."""

    response = client.messages.create(
        model=MODEL_SMART,
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


# ── Start exam ───────────────────────────────────────────────────────────────

async def start_exam(bot, chat_id: int, topic_id: str, data_dir: Path):
    """Запускає екзамен: генерує питання, зберігає сесію, відправляє перше питання."""
    # Check no active exam
    if is_exam_active(data_dir):
        session = _load_session(data_dir)
        await bot.send_message(
            chat_id,
            f"⚠️ Вже є активний екзамен по темі <b>{session['topic_title']}</b>.\n"
            f"Заверши його або скасуй командою /exam_cancel",
            parse_mode="HTML",
        )
        return

    # Load topic
    cur_path = data_dir / "curriculum.json"
    state = load(cur_path)
    topic = state.get_topic(topic_id)
    if not topic:
        await bot.send_message(chat_id, f"❌ Тема {topic_id} не знайдена.")
        return

    await bot.send_message(
        chat_id,
        f"🧠 Генерую екзамен по темі <b>{topic.title}</b>...",
        parse_mode="HTML",
    )

    # Generate questions
    try:
        questions = _generate_questions(
            topic.title,
            topic.why or "",
            topic.read or "",
            topic.do or "",
        )
    except Exception as e:
        log.error(f"Failed to generate exam questions: {e}", exc_info=True)
        await bot.send_message(chat_id, f"❌ Не вдалось згенерувати питання: {e}")
        return

    # Mark exam as generating
    set_format_status(state, topic_id, "exam", "generating")
    save(state, cur_path)

    # Create session
    session = {
        "status": "active",
        "topic_id": topic_id,
        "topic_title": topic.title,
        "questions": questions,
        "current": 0,
        "answers": [],
        "evaluations": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_session(data_dir, session)

    # Send first question
    await _send_question(bot, chat_id, session)


async def _send_question(bot, chat_id: int, session: dict):
    """Відправляє поточне питання."""
    idx = session["current"]
    question = session["questions"][idx]
    await bot.send_message(
        chat_id,
        f"📝 Питання {idx + 1}/{NUM_QUESTIONS}\n\n{question}",
    )


# ── Handle answer ────────────────────────────────────────────────────────────

async def handle_exam_answer(bot, chat_id: int, text: str, data_dir: Path) -> bool:
    """
    Обробляє відповідь на поточне питання.
    Повертає True якщо повідомлення оброблено як exam answer.
    """
    session = _load_session(data_dir)
    if not session or session.get("status") != "active":
        return False

    idx = session["current"]
    question = session["questions"][idx]
    topic_title = session["topic_title"]

    # Evaluate
    try:
        evaluation = _evaluate_answer(topic_title, question, text)
    except Exception as e:
        log.error(f"Exam evaluation failed: {e}", exc_info=True)
        await bot.send_message(chat_id, f"⚠️ Помилка оцінки: {e}\nСпробуй відповісти ще раз.")
        return True

    # Save answer + evaluation
    session["answers"].append(text)
    session["evaluations"].append(evaluation)
    session["current"] = idx + 1

    # Send feedback
    correct = evaluation.get("correct", False)
    score = evaluation.get("score", 0)
    feedback = evaluation.get("feedback", "")
    icon = "✅" if correct else "❌"
    await bot.send_message(
        chat_id,
        f"{icon} <b>{score}/10</b>\n{feedback}",
        parse_mode="HTML",
    )

    # Next question or finish
    if session["current"] < NUM_QUESTIONS:
        _save_session(data_dir, session)
        await _send_question(bot, chat_id, session)
    else:
        await _finish_exam(bot, chat_id, session, data_dir)

    return True


# ── Finish exam ──────────────────────────────────────────────────────────────

async def _finish_exam(bot, chat_id: int, session: dict, data_dir: Path):
    """Підсумок екзамену + кнопка mastered."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    topic_id = session["topic_id"]
    topic_title = session["topic_title"]
    evaluations = session["evaluations"]

    correct_count = sum(1 for e in evaluations if e.get("correct"))
    total_score = sum(e.get("score", 0) for e in evaluations)
    avg_score = total_score / NUM_QUESTIONS if evaluations else 0
    passed = correct_count >= PASS_THRESHOLD

    # Update curriculum
    cur_path = data_dir / "curriculum.json"
    state = load(cur_path)
    status = "ready" if passed else "failed"
    set_format_status(state, topic_id, "exam", status)
    save(state, cur_path)

    # Build result message
    lines = [
        f"🏁 <b>Екзамен завершено: {topic_title}</b>\n",
        f"Правильних: {correct_count}/{NUM_QUESTIONS}",
        f"Середній бал: {avg_score:.1f}/10",
        "",
    ]

    for i, (q, ev) in enumerate(zip(session["questions"], evaluations)):
        icon = "✅" if ev.get("correct") else "❌"
        lines.append(f"{icon} Q{i+1}: {ev.get('score', 0)}/10")

    # Знаходимо слабкі теми для підтем
    weak_questions = [
        session["questions"][i]
        for i, ev in enumerate(evaluations)
        if not ev.get("correct")
    ]

    if passed:
        lines.append(f"\n🎉 <b>Пройдено!</b>")
        if weak_questions:
            lines.append(f"\n💡 Але є прогалини — можеш додати підтему для поглиблення.")
    else:
        lines.append(f"\n😔 Не пройдено. Спробуй ще раз після повторення матеріалу.")
        if weak_questions:
            lines.append(f"\n💡 Рекомендую додати підтему по слабких місцях.")

    # Keyboard
    keyboard = []
    if passed:
        keyboard.append([InlineKeyboardButton(
            "✅ Mastered",
            callback_data=f"exam_mastered_{topic_id}",
        )])
    if weak_questions:
        keyboard.append([InlineKeyboardButton(
            "➕ Додати підтему по прогалині",
            callback_data=f"exam_subtopic_{topic_id}",
        )])
    keyboard.append([InlineKeyboardButton(
        "🔄 Повторити екзамен",
        callback_data=f"exam_retry_{topic_id}",
    )])

    await bot.send_message(
        chat_id,
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    # Clear session
    _clear_session(data_dir)


# ── Cancel exam ──────────────────────────────────────────────────────────────

async def cancel_exam(bot, chat_id: int, data_dir: Path):
    """Скасовує активний екзамен."""
    session = _load_session(data_dir)
    if not session or session.get("status") != "active":
        await bot.send_message(chat_id, "Немає активного екзамену.")
        return

    topic_id = session["topic_id"]

    # Reset exam format to pending
    cur_path = data_dir / "curriculum.json"
    state = load(cur_path)
    if state.get_topic(topic_id):
        set_format_status(state, topic_id, "exam", "pending")
        save(state, cur_path)

    _clear_session(data_dir)
    await bot.send_message(chat_id, "🚫 Екзамен скасовано.")


# ── Callback handlers ────────────────────────────────────────────────────────

async def handle_exam_callback(update, context):
    """Обробляє inline-кнопки після екзамену."""
    from modules.base import DATA_DIR
    from modules.pinned import refresh_pinned

    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id

    if data.startswith("exam_mastered_"):
        topic_id = data[len("exam_mastered_"):]
        cur_path = DATA_DIR / "curriculum.json"
        state = load(cur_path)
        try:
            set_topic_state(state, topic_id, "mastered")
            save(state, cur_path)
            await query.message.reply_text(
                f"🏆 Тему позначено як <b>mastered</b>!",
                parse_mode="HTML",
            )
            await refresh_pinned(context.bot, chat_id, DATA_DIR)
        except Exception as e:
            log.error(f"exam_mastered failed: {e}", exc_info=True)
            await query.message.reply_text(f"❌ Помилка: {e}")

    elif data.startswith("exam_subtopic_"):
        topic_id = data[len("exam_subtopic_"):]
        cur_path = DATA_DIR / "curriculum.json"
        state = load(cur_path)
        topic = state.get_topic(topic_id)
        if not topic:
            await query.message.reply_text(f"❌ Тема {topic_id} не знайдена.")
            return

        # Генеруємо назву підтеми через LLM на основі слабких місць
        try:
            subtopic_title = _generate_subtopic_title(topic.title)
            await query.message.reply_text(
                f"➕ Додаю підтему: <b>{subtopic_title}</b>\n"
                f"Використай /cur_add {subtopic_title}",
                parse_mode="HTML",
            )
        except Exception as e:
            log.error(f"Subtopic generation failed: {e}", exc_info=True)
            await query.message.reply_text(f"❌ Помилка: {e}")

    elif data.startswith("exam_retry_"):
        topic_id = data[len("exam_retry_"):]
        await start_exam(context.bot, chat_id, topic_id, DATA_DIR)
