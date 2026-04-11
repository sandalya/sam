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
DYNAMIC_CURRICULUM_PATH = DATA_DIR / "curriculum_dynamic.json"

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


# ── Dynamic curriculum ────────────────────────────────────────────────────────

def _load_dynamic_topics() -> list:
    if DYNAMIC_CURRICULUM_PATH.exists():
        return json.loads(DYNAMIC_CURRICULUM_PATH.read_text())
    return []


def _save_dynamic_topics(topics: list):
    DYNAMIC_CURRICULUM_PATH.write_text(json.dumps(topics, ensure_ascii=False, indent=2))


def _generate_dynamic_topics(state: dict, profile: dict) -> list:
    """Генерує 3-5 нових тем на основі профілю, інтересів і прогресу."""
    completed_titles = [i["title"] for i in CURRICULUM if i["id"] in state["completed"]]
    all_titles = [i["title"] for i in CURRICULUM]
    interests = profile.get("interests", [])
    scores = profile.get("scores", {})

    prompt = (
        "You are a personalized AI curriculum designer.\n\n"
        "The learner is a Python developer building AI agents and Telegram bots with Anthropic API.\n\n"
        f"Completed topics: {completed_titles}\n"
        f"All seed topics: {all_titles}\n"
        f"Detected interests from conversations: {interests}\n"
        f"Skill scores (0-3): {scores}\n\n"
        "Generate 3-5 NEW learning topics that logically follow from the completed work "
        "and align with detected interests. Topics should be practical and buildable.\n\n"
        "Return ONLY a JSON array of objects with fields: "
        "id (start from 100), title, estimate, why, read (URL), do. "
        "No explanation, just the JSON array."
    )

    try:
        response = client.messages.create(
            model=MODEL_SMART,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "\n".join(b.text for b in response.content if b.type == "text")
        import re
        match = re.search(r"\[.*?\]", text, re.DOTALL)
        if not match:
            return []
        topics = json.loads(match.group())
        _save_dynamic_topics(topics)
        return topics
    except Exception as e:
        log.error(f"Dynamic curriculum generation failed: {e}")
        return []


def _get_full_curriculum(state: dict, profile: dict) -> list:
    """Повертає seed + динамічні теми. Регенерує якщо є нові інтереси."""
    dynamic = _load_dynamic_topics()

    # Регенеруємо якщо є інтереси але динамічних тем ще нема
    interests = profile.get("interests", [])
    if interests and not dynamic:
        dynamic = _generate_dynamic_topics(state, profile)

    return CURRICULUM + dynamic


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


def _format_keyboard(item_id: int, selected: list) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            f"{'✅' if fmt in selected else '⬜'} {label}",
            callback_data=f"cur_nbtoggle|{item_id}|{fmt}"
        )
        for label, fmt in NOTEBOOKLM_FORMATS
    ]
    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    if selected:
        rows.append([InlineKeyboardButton(f"▶️ Генерувати ({len(selected)})", callback_data=f"cur_nbrun|{item_id}")])
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
    from .base import PROFILE_PATH
    profile = json.loads(PROFILE_PATH.read_text()) if PROFILE_PATH.exists() else {}
    profile.setdefault("interests", [])

    state = load_state()
    all_topics = _get_full_curriculum(state, profile)

    total = len(all_topics)
    done = len(state["completed"])
    filled = round(done / total * 10) if total else 0
    bar = "█" * filled + "░" * (10 - filled)
    progress = f"[{bar}] {done}/{total}"

    lines = [f"📚 Твій AI Curriculum\n{progress}\n"]
    for item in all_topics:
        icon = _status_icon(item["id"], state)
        tag = " ✨" if item["id"] >= 100 else ""
        lines.append(f"{icon} {item['id']}. {item['title']} — {item['estimate']}{tag}")

    lines.append("\nОбери тему:")

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"{_status_icon(item['id'], state)} {item['id']}",
            callback_data=f"cur_item|{item['id']}"
        )
        for item in all_topics
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
    from .base import PROFILE_PATH
    profile = json.loads(PROFILE_PATH.read_text()) if PROFILE_PATH.exists() else {}
    profile.setdefault("interests", [])
    all_topics = _get_full_curriculum(state, profile)

    # ── cur_item — показати картку теми (edit in place) ──
    if action == "cur_item":
        item_id = int(parts[1])
        item = next((i for i in all_topics if i["id"] == item_id), None)
        if not item:
            return
        await query.edit_message_text(
            _item_text(item, state),
            parse_mode="Markdown",
            reply_markup=_item_keyboard(item_id),
        )

    # ── cur_back — повернутись до списку ──
    elif action == "cur_back":
        total = len(all_topics)
        done = len(state["completed"])
        filled = round(done / total * 10) if total else 0
        bar = "█" * filled + "░" * (10 - filled)
        progress = f"[{bar}] {done}/{total}"
        lines = [f"📚 Твій AI Curriculum\n{progress}\n"]
        for item in all_topics:
            icon = _status_icon(item["id"], state)
            tag = " ✨" if item["id"] >= 100 else ""
            lines.append(f"{icon} {item['id']}. {item['title']} — {item['estimate']}{tag}")
        lines.append("\nОбери тему:")
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                f"{_status_icon(item['id'], state)} {item['id']}",
                callback_data=f"cur_item|{item['id']}"
            )
            for item in all_topics
        ]])
        await query.edit_message_text("\n".join(lines), reply_markup=keyboard)

    # ── cur_start — позначити "в процесі" ──
    elif action == "cur_start":
        item_id = int(parts[1])
        item = next((i for i in all_topics if i["id"] == item_id), None)
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
        item = next((i for i in all_topics if i["id"] == item_id), None)
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
        item = next((i for i in all_topics if i["id"] == item_id), None)
        if not item:
            return
        context.user_data[f"nb_selected_{item_id}"] = []
        await query.edit_message_text(
            f"🎧 *{item['title']}*\n\nОбери формати для NotebookLM:",
            parse_mode="Markdown",
            reply_markup=_format_keyboard(item_id, []),
        )

    # ── cur_nbtoggle — toggle формату ──
    elif action == "cur_nbtoggle":
        item_id = int(parts[1])
        fmt = parts[2]
        item = next((i for i in all_topics if i["id"] == item_id), None)
        if not item:
            return
        key = f"nb_selected_{item_id}"
        selected = context.user_data.get(key, [])
        if fmt in selected:
            selected.remove(fmt)
        else:
            selected.append(fmt)
        context.user_data[key] = selected
        await query.edit_message_text(
            f"🎧 *{item['title']}*\n\nОбери формати для NotebookLM:",
            parse_mode="Markdown",
            reply_markup=_format_keyboard(item_id, selected),
        )

    # ── cur_nbrun — запустити всі вибрані формати ──
    elif action == "cur_nbrun":
        item_id = int(parts[1])
        item = next((i for i in all_topics if i["id"] == item_id), None)
        if not item:
            return
        selected = context.user_data.get(f"nb_selected_{item_id}", [])
        if not selected:
            await query.answer("Обери хоча б один формат", show_alert=True)
            return

        names = ", ".join(FORMAT_NAMES.get(f, f) for f in selected)
        await query.edit_message_text(
            f"⏳ Генерую: {names}\n\nТема: *{item['title']}*",
            parse_mode="Markdown",
        )

        page_text = await _fetch_page(item["read"])
        from .notebooklm import generate_and_notify, get_or_create_notebook
        import asyncio

        # Створюємо notebook і додаємо джерело заздалегідь — один раз для всіх форматів
        from .notebooklm import _run as nb_run, save_nb_state, load_nb_state
        notebook_id = await get_or_create_notebook(item_id, item["title"])
        if not notebook_id:
            await query.message.reply_text("❌ Не вдалось створити notebook.")
            return

        rc, stdout, stderr = await nb_run(["source", "add", "-n", notebook_id, item["read"]])
        if rc != 0 and "already" not in stderr.lower() and "already" not in stdout.lower():
            log.warning(f"Add source warning (ignored): {stderr[:200]}")

        for fmt in selected:
            instructions = ""
            if page_text:
                instructions = _generate_notebooklm_prompt(item, fmt, page_text)
                if "📌 Промпт 1:" in instructions:
                    instructions = instructions.split("📌 Промпт 1:")[-1].split("📌 Промпт 2:")[0].strip()
                instructions = instructions[:500]
            asyncio.create_task(generate_and_notify(
                bot=query.get_bot(),
                chat_id=query.message.chat_id,
                topic_id=item_id,
                topic_title=item["title"],
                source_url=item["read"],
                fmt=fmt,
                instructions=instructions,
                skip_source=True,
            ))

