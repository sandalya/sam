"""
Модуль curriculum — персональний план навчання AI.
Команди: /cur, /done <N>
"""
import json
import logging
import httpx
from datetime import datetime
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from .base import DATA_DIR, client, MODEL_SMART, SAM_PERSONA

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

# Формати NotebookLM
NOTEBOOKLM_FORMATS = [
    ("🎬 Відео", "video"),
    ("🎙️ Подкаст", "podcast"),
    ("🎤 Монолог", "audio"),
    ("📋 Study guide", "study"),
    ("📄 Briefing", "briefing"),
]

FORMAT_INSTRUCTIONS = {
    "video": (
        "Створи промпт для генерації ВІДЕО у NotebookLM. "
        "Відео має бути динамічним, з чіткою структурою: вступ → основні концепти → практичне застосування → висновок. "
        "Фокус на візуальному поясненні — що можна показати, продемонструвати, зобразити схемою."
    ),
    "podcast": (
        "Створи промпт для генерації ПОДКАСТУ (діалог двох ведучих) у NotebookLM. "
        "Діалог має бути живим: один пояснює, інший задає питання як людина що вчиться. "
        "Стиль — розмовний, без зайвого академізму."
    ),
    "audio": (
        "Створи промпт для генерації АУДІО МОНОЛОГУ у NotebookLM. "
        "Один ведучий, впевнений тон, чітка структура. "
        "Як якісна лекція — послідовно, з прикладами, без води."
    ),
    "study": (
        "Створи промпт для генерації STUDY GUIDE у NotebookLM. "
        "Формат: ключові концепти → FAQ → практичні питання для самоперевірки. "
        "Матеріал для читання і повернення до нього."
    ),
    "briefing": (
        "Створи промпт для генерації BRIEFING DOC у NotebookLM. "
        "Короткий огляд: що це, навіщо, головні ідеї, практичне застосування. "
        "Максимум корисного за мінімум тексту."
    ),
}

FORMAT_NAMES = {
    "video": "🎬 Відео",
    "podcast": "🎙️ Подкаст",
    "audio": "🎤 Монолог",
    "study": "📋 Study guide",
    "briefing": "📄 Briefing",
}


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


def _item_text(item: dict, state: dict) -> str:
    icon = _status_icon(item["id"], state)
    return (
        f"{icon} *{item['id']}. {item['title']}*\n"
        f"⏱ {item['estimate']}\n\n"
        f"*Навіщо:* {item['why']}\n\n"
        f"*Почитати:* [посилання]({item['read']})\n\n"
        f"*Зробити руками:*\n{item['do']}"
    )


def _item_keyboard(item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Почав", callback_data=f"cur_start|{item_id}"),
            InlineKeyboardButton("✅ Готово", callback_data=f"cur_done|{item_id}"),
        ],
        [
            InlineKeyboardButton("🎧 NotebookLM промпт", callback_data=f"cur_nb|{item_id}"),
        ],
        [
            InlineKeyboardButton("← Назад", callback_data="cur_back"),
        ],
    ])


def _format_keyboard(item_id: int) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(label, callback_data=f"cur_nbfmt|{item_id}|{fmt}")
        for label, fmt in NOTEBOOKLM_FORMATS
    ]
    # По 2 в ряд
    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton("← Назад", callback_data=f"cur_item|{item_id}")])
    return InlineKeyboardMarkup(rows)


async def _fetch_page(url: str) -> str:
    """Завантажує текст сторінки через httpx (async)."""
    try:
        import re
        headers = {"User-Agent": "Mozilla/5.0 (compatible; SamBot/1.0)"}
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        text = re.sub(r"<[^>]+>", " ", resp.text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:8000]
    except Exception as e:
        log.error(f"Fetch error for {url}: {e}")
        return ""


def _generate_notebooklm_prompt(item: dict, fmt: str, page_text: str) -> str:
    format_instruction = FORMAT_INSTRUCTIONS[fmt]
    format_name = FORMAT_NAMES[fmt]

    system = (
        "Ти — асистент що допомагає розробнику AI-агентів вчитися ефективно. "
        "Твоє завдання — проаналізувати технічну документацію і скласти промпт(и) для NotebookLM. "
        "Розробник будує Telegram-ботів і AI-агентів на Python + Anthropic API. "
        "Рівень: вже робить production агентів, але хоче глибше розуміти теорію і архітектуру.\n\n"
        "Правила:\n"
        "1. Якщо тема складна і має кілька незалежних аспектів — роби КІЛЬКА промптів (2-3), кожен зі своїм фокусом.\n"
        "2. Якщо тема компактна — один промпт.\n"
        "3. Кожен промпт починай з '📌 Промпт N:' і давай йому назву.\n"
        "4. Промпт має бути англійською, конкретним, вказувати NotebookLM на що фокусуватись і що ігнорувати.\n"
        "5. В кінці кожного промпту додай рядок 'Контекст для NotebookLM:' з 1-2 реченнями про аудиторію.\n"
    )

    user = (
        f"Тема навчання: {item['title']}\n"
        f"Формат виводу: {format_name}\n"
        f"Інструкція по формату: {format_instruction}\n\n"
        f"Ресурс: {item['read']}\n\n"
        f"Вміст сторінки (перші 8000 символів):\n{page_text}\n\n"
        f"Склади промпт(и) для NotebookLM щоб отримати максимально корисний {format_name} "
        f"по темі '{item['title']}' для цього розробника."
    )

    full_prompt = f"{system}\n\n{user}"
    response = client.messages.create(
        model=MODEL_SMART,
        max_tokens=2000,
        system=[{"type": "text", "text": SAM_PERSONA, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": full_prompt}],
    )
    return "\n".join(b.text for b in response.content if b.type == "text")


# ── Handlers ───────────────────────────────────────────────────────────────────

async def cmd_curriculum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    lines = [f"📚 Твій AI Curriculum\n{_progress_bar(state)}\n"]

    for item in CURRICULUM:
        icon = _status_icon(item["id"], state)
        lines.append(f"{icon} {item['id']}. {item['title']} — {item['estimate']}")

    lines.append("\nОбери тему:")

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
        await update.message.reply_text("Використання: /cur")
        return
    item_id = int(args[0])
    item = next((i for i in CURRICULUM if i["id"] == item_id), None)
    if not item:
        await update.message.reply_text(f"Тема {item_id} не існує.")
        return
    state = load_state()
    await update.message.reply_text(
        _item_text(item, state),
        parse_mode="Markdown",
        reply_markup=_item_keyboard(item_id),
    )


async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Використання: /done <N>")
        return
    await _mark_done(update.message, int(args[0]))


async def cmd_start_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Використання: /start_topic <N>")
        return
    await _mark_start(update.message, int(args[0]))


async def _mark_done(msg, item_id: int):
    item = next((i for i in CURRICULUM if i["id"] == item_id), None)
    if not item:
        await msg.reply_text(f"Тема {item_id} не існує.")
        return
    state = load_state()
    if item_id not in state["completed"]:
        state["completed"].append(item_id)
    if item_id in state["started"]:
        state["started"].remove(item_id)
    state["notes"][str(item_id)] = {"completed_at": datetime.now().isoformat()}
    save_state(state)

    next_item = next((i for i in CURRICULUM if i["id"] not in state["completed"]), None)
    text = f"✅ *{item['title']}* — виконано!\n\n{_progress_bar(state)}"
    if next_item:
        text += f"\n\nНаступна тема: *{next_item['id']}. {next_item['title']}*"
    else:
        text += "\n\n🎉 Curriculum завершено!"
    await msg.reply_text(text, parse_mode="Markdown")


async def _mark_start(msg, item_id: int):
    item = next((i for i in CURRICULUM if i["id"] == item_id), None)
    if not item:
        await msg.reply_text(f"Тема {item_id} не існує.")
        return
    state = load_state()
    if item_id not in state["started"] and item_id not in state["completed"]:
        state["started"].append(item_id)
    save_state(state)
    await msg.reply_text(
        f"🔄 *{item['title']}* — в процесі. Удачі!",
        parse_mode="Markdown"
    )


# ── Callback router ────────────────────────────────────────────────────────────

async def handle_curriculum_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split("|")
    action = parts[0]

    state = load_state()

    # ── cur_item — показати картку теми (edit in place) ──
    if action == "cur_item":
        item_id = int(parts[1])
        item = next((i for i in CURRICULUM if i["id"] == item_id), None)
        if not item:
            return
        await query.edit_message_text(
            _item_text(item, state),
            parse_mode="Markdown",
            reply_markup=_item_keyboard(item_id),
        )

    # ── cur_back — повернутись до списку ──
    elif action == "cur_back":
        lines = [f"📚 Твій AI Curriculum\n{_progress_bar(state)}\n"]
        for item in CURRICULUM:
            icon = _status_icon(item["id"], state)
            lines.append(f"{icon} {item['id']}. {item['title']} — {item['estimate']}")
        lines.append("\nОбери тему:")
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                f"{_status_icon(item['id'], state)} {item['id']}",
                callback_data=f"cur_item|{item['id']}"
            )
            for item in CURRICULUM
        ]])
        await query.edit_message_text("\n".join(lines), reply_markup=keyboard)

    # ── cur_start — позначити "в процесі" ──
    elif action == "cur_start":
        item_id = int(parts[1])
        item = next((i for i in CURRICULUM if i["id"] == item_id), None)
        if not item:
            return
        if item_id not in state["started"] and item_id not in state["completed"]:
            state["started"].append(item_id)
        save_state(state)
        # Оновити картку з новим статусом
        await query.edit_message_text(
            _item_text(item, state),
            parse_mode="Markdown",
            reply_markup=_item_keyboard(item_id),
        )

    # ── cur_done — позначити виконаним ──
    elif action == "cur_done":
        item_id = int(parts[1])
        item = next((i for i in CURRICULUM if i["id"] == item_id), None)
        if not item:
            return
        if item_id not in state["completed"]:
            state["completed"].append(item_id)
        if item_id in state["started"]:
            state["started"].remove(item_id)
        state["notes"][str(item_id)] = {"completed_at": datetime.now().isoformat()}
        save_state(state)
        # Оновити картку
        await query.edit_message_text(
            _item_text(item, state),
            parse_mode="Markdown",
            reply_markup=_item_keyboard(item_id),
        )

    # ── cur_nb — показати вибір формату ──
    elif action == "cur_nb":
        item_id = int(parts[1])
        item = next((i for i in CURRICULUM if i["id"] == item_id), None)
        if not item:
            return
        await query.edit_message_text(
            f"🎧 *{item['title']}*\n\nОбери формат для NotebookLM:",
            parse_mode="Markdown",
            reply_markup=_format_keyboard(item_id),
        )

    # ── cur_nbfmt — генерувати промпт під обраний формат ──
    elif action == "cur_nbfmt":
        item_id = int(parts[1])
        fmt = parts[2]
        item = next((i for i in CURRICULUM if i["id"] == item_id), None)
        if not item:
            return

        format_name = FORMAT_NAMES.get(fmt, fmt)

        # Показуємо "читаю..."
        await query.edit_message_text(
            f"📖 Читаю ресурс по темі *{item['title']}*...\n\n"
            f"Формат: {format_name}\n\n"
            f"Зачекай хвилинку ⏳",
            parse_mode="Markdown",
        )

        # Завантажуємо сторінку
        page_text = await _fetch_page(item["read"])
        if not page_text:
            await query.message.reply_text(
                f"❌ Не вдалось прочитати сторінку: {item['read']}\n"
                "Спробуй пізніше або відкрий вручну."
            )
            return

        # Генеруємо промпт через Claude
        result = _generate_notebooklm_prompt(item, fmt, page_text)

        # Відправляємо результат окремим повідомленням
        response_text = (
            f"🎧 NotebookLM промпт — {item['title']}\n"
            f"Формат: {format_name}\n"
            f"Джерело: {item['read']}\n\n"
            f"{'─' * 30}\n\n"
            f"{result}"
        )

        await query.message.reply_text(response_text)