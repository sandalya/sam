"""
Модуль curriculum — персональний план навчання AI.
Команди: /curriculum, /done <N>
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from .base import DATA_DIR

log = logging.getLogger("sam.curriculum")

CURRICULUM_STATE_PATH = DATA_DIR / "curriculum.json"

CURRICULUM = [
    {
        "id": 1,
        "title": "Tool Use / Function Calling",
        "estimate": "1-2 дні",
        "why": "Ти вже робиш це вручну через JSON. Нативний tool use — інший рівень контролю.",
        "read": "https://docs.anthropic.com/en/docs/build-with-claude/tool-use",
        "do": "Переписати один action з Meggy (add_to_shopping) на нативний tool use.",
    },
    {
        "id": 2,
        "title": "Agentic Loops",
        "estimate": "2-3 дні",
        "why": "Агент що сам вирішує скільки кроків зробити — це якісний стрибок від бота.",
        "read": "https://www.anthropic.com/research/building-effective-agents",
        "do": "Додати в Sam модуль що сам вирішує — одного пошуку достатньо чи треба ще.",
    },
    {
        "id": 3,
        "title": "Evals",
        "estimate": "1-2 дні",
        "why": "Без evals не знаєш чи агент став кращим або гіршим після змін.",
        "read": "https://docs.anthropic.com/en/docs/build-with-claude/evals",
        "do": "Написати 10 тест-кейсів для InSilver з очікуваною відповіддю і score функцією.",
    },
    {
        "id": 4,
        "title": "RAG — Retrieval Augmented Generation",
        "estimate": "3-4 дні",
        "why": "Векторний пошук замість grep — агент знаходить релевантне навіть при неточному запиті.",
        "read": "https://docs.anthropic.com/en/docs/build-with-claude/embeddings",
        "do": "Додати chromadb в InSilver knowledge.py. Локально, безкоштовно.",
    },
    {
        "id": 5,
        "title": "Multi-agent координація",
        "estimate": "3-5 днів",
        "why": "Оркестратор + субагенти — архітектура складних продуктів.",
        "read": "https://docs.anthropic.com/en/docs/build-with-claude/multiagent-network",
        "do": "Sam делегує дизайн-питання Abby і повертає відповідь. Оркестратор + субагент.",
    },
]


# ── State ──────────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if CURRICULUM_STATE_PATH.exists():
        return json.loads(CURRICULUM_STATE_PATH.read_text())
    return {"completed": [], "started": [], "notes": {}}


def save_state(state: dict):
    CURRICULUM_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _status_icon(item_id: int, state: dict) -> str:
    if item_id in state["completed"]:
        return "✅"
    if item_id in state["started"]:
        return "🔄"
    return "⬜"


def _progress_bar(state: dict) -> str:
    total = len(CURRICULUM)
    done = len(state["completed"])
    filled = round(done / total * 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"[{bar}] {done}/{total}"


# ── Handlers ───────────────────────────────────────────────────────────────────

async def cmd_curriculum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    lines = [f"📚 Твій AI Curriculum\n{_progress_bar(state)}\n"]

    for item in CURRICULUM:
        icon = _status_icon(item["id"], state)
        lines.append(f"{icon} {item['id']}. {item['title']} — {item['estimate']}")

    lines.append("\n/done N — виконано | /begin N — почав")

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"{_status_icon(item['id'], state)} {item['id']}",
            callback_data=f"cur_item|{item['id']}"
        )
        for item in CURRICULUM
    ]])

    await update.message.reply_text("\n".join(lines), reply_markup=keyboard)


async def cmd_curriculum_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Використання: /curriculum\\_item <N>", parse_mode="Markdown")
        return

    item_id = int(args[0])
    item = next((i for i in CURRICULUM if i["id"] == item_id), None)
    if not item:
        await update.message.reply_text(f"Тема {item_id} не існує.")
        return

    state = load_state()
    icon = _status_icon(item_id, state)

    text = (
        f"{icon} *{item['id']}. {item['title']}*\n"
        f"⏱ {item['estimate']}\n\n"
        f"*Навіщо:* {item['why']}\n\n"
        f"*Почитати:* [посилання]({item['read']})\n\n"
        f"*Зробити руками:*\n{item['do']}"
    )

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Почав", callback_data=f"cur_start|{item_id}"),
        InlineKeyboardButton("✅ Готово", callback_data=f"cur_done|{item_id}"),
    ]])

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Використання: /done <N>")
        return
    await _mark(update, int(args[0]), "done")


async def cmd_start_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Використання: /start <N>")
        return
    await _mark(update, int(args[0]), "start")


async def _mark(update: Update, item_id: int, action: str):
    item = next((i for i in CURRICULUM if i["id"] == item_id), None)
    if not item:
        await update.message.reply_text(f"Тема {item_id} не існує.")
        return

    state = load_state()

    if action == "done":
        if item_id not in state["completed"]:
            state["completed"].append(item_id)
        if item_id in state["started"]:
            state["started"].remove(item_id)
        state["notes"][str(item_id)] = {"completed_at": datetime.now().isoformat()}
        save_state(state)

        next_item = next((i for i in CURRICULUM if i["id"] not in state["completed"]), None)
        msg = f"✅ *{item['title']}* — виконано!\n\n{_progress_bar(state)}"
        if next_item:
            msg += f"\n\nНаступна тема: *{next_item['id']}. {next_item['title']}*\n/curriculum_item {next_item['id']}"
        else:
            msg += "\n\n🎉 Curriculum завершено! Ти тепер знаєш більше ніж 90% людей що 'вивчають AI'."

        await update.message.reply_text(msg, parse_mode="Markdown")

    elif action == "start":
        if item_id not in state["started"] and item_id not in state["completed"]:
            state["started"].append(item_id)
        save_state(state)
        await update.message.reply_text(
            f"🔄 *{item['title']}* — в процесі.\nУдачі! /curriculum_item {item_id} якщо треба деталі.",
            parse_mode="Markdown"
        )


async def handle_curriculum_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("|")
    action, item_id = parts[0], int(parts[1])

    state = load_state()
    item = next((i for i in CURRICULUM if i["id"] == item_id), None)
    if not item:
        return

    if action == "cur_item":
        item = next((i for i in CURRICULUM if i["id"] == item_id), None)
        if not item:
            return
        icon = _status_icon(item_id, state)
        text = (
            f"{icon} *{item['id']}. {item['title']}*\n"
            f"⏱ {item['estimate']}\n\n"
            f"*Навіщо:* {item['why']}\n\n"
            f"*Почитати:* [посилання]({item['read']})\n\n"
            f"*Зробити руками:*\n{item['do']}"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Почав", callback_data=f"cur_start|{item_id}"),
            InlineKeyboardButton("✅ Готово", callback_data=f"cur_done|{item_id}"),
        ]])
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)

    elif action == "cur_done":
        if item_id not in state["completed"]:
            state["completed"].append(item_id)
        if item_id in state["started"]:
            state["started"].remove(item_id)
        state["notes"][str(item_id)] = {"completed_at": datetime.now().isoformat()}
        save_state(state)
        await query.edit_message_reply_markup(
            InlineKeyboardMarkup([[InlineKeyboardButton("✅ Виконано!", callback_data="done")]])
        )

    elif action == "cur_start":
        if item_id not in state["started"] and item_id not in state["completed"]:
            state["started"].append(item_id)
        save_state(state)
        await query.edit_message_reply_markup(
            InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 В процесі", callback_data="done"),
                InlineKeyboardButton("✅ Готово", callback_data=f"cur_done|{item_id}"),
            ]])
        )