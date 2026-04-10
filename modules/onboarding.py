import re
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .base import BaseModule

logger = logging.getLogger("sam.onboarding")

TOPICS = {
    "models": "🧠 Моделі",
    "agents": "🤖 Агенти",
    "mcp": "🔌 MCP",
    "tools": "🛠 Інструменти розробника",
    "jobs": "💼 Ринок праці AI",
}

PROMPTS = {
    "models": """Поясни стан LLM-моделей станом на сьогодні для людини яка тільки входить в AI-світ.
Покрий: які основні гравці (Anthropic, OpenAI, Google, Meta, Mistral), які моделі зараз найважливіші і чим відрізняються, що таке reasoning моделі, як обирати модель для задачі, що вже застаріло і про що не варто думати.
Стиль: зрозуміло, без зайвого жаргону, з конкретними прикладами. Українська мова. Без markdown-форматування, тільки звичайний текст з емодзі.""",

    "agents": """Поясни що таке AI-агенти станом на сьогодні для людини яка тільки входить в AI-світ.
Покрий: що таке агент і чим відрізняється від простого LLM-виклику, які основні фреймворки (LangGraph, CrewAI, AutoGen та інші), де агенти вже реально працюють, які основні проблеми (надійність, cost, latency), що варто вивчити першим.
Стиль: зрозуміло, з конкретними прикладами, без зайвого хайпу. Українська мова. Без markdown-форматування, тільки звичайний текст з емодзі.""",

    "mcp": """Поясни що таке MCP (Model Context Protocol) станом на сьогодні для людини яка тільки входить в AI-світ.
Покрий: що це і навіщо придумали, як працює (servers, clients, tools), які популярні MCP-сервери вже є, як це використовують в реальних проектах, чому це важливо для розробника AI-продуктів.
Стиль: зрозуміло, з аналогіями, без зайвого жаргону. Українська мова. Без markdown-форматування, тільки звичайний текст з емодзі.""",

    "tools": """Поясни який інструментарій використовують розробники AI-продуктів станом на сьогодні.
Покрий: IDE та AI-асистенти (Cursor, Claude Code та інші), популярні бібліотеки і SDK, інструменти для evals і моніторингу, деплой і інфраструктура, що варто освоїти першим а що можна відкласти.
Стиль: практично, з конкретними назвами інструментів, без зайвого. Українська мова. Без markdown-форматування, тільки звичайний текст з емодзі.""",

    "jobs": """Поясни стан ринку праці в AI станом на сьогодні для людини яка хоче увійти в цю сферу.
Покрий: які ролі існують (AI engineer, ML engineer, prompt engineer тощо), що реально потрібно знати для кожної, які навички найбільш затребувані, де шукати роботу, який типовий шлях входу для людини з досвідом в розробці але без AI-досвіду.
Стиль: чесно, практично, без рожевих окулярів. Українська мова. Без markdown-форматування, тільки звичайний текст з емодзі.""",
}


class OnboardingModule(BaseModule):

    def _make_menu(self) -> InlineKeyboardMarkup:
        buttons = [
            [InlineKeyboardButton(label, callback_data=f"onb_{key}")]
            for key, label in TOPICS.items()
        ]
        return InlineKeyboardMarkup(buttons)

    async def send_menu(self, update: Update):
        await update.message.reply_text(
            "🎓 <b>Онбординг в AI-світ</b>\n\nОбери тему — розповім що треба знати:",
            parse_mode="HTML",
            reply_markup=self._make_menu(),
        )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        key = query.data.replace("onb_", "")
        if key not in PROMPTS:
            return

        topic_label = TOPICS[key]
        await query.edit_message_text(
            f"⏳ Готую огляд: {topic_label}...",
        )

        try:
            raw = self.call_claude_with_search(PROMPTS[key], max_tokens=4000)
            # Прибираємо markdown-символи
            text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', raw)
            text = re.sub(r'#{1,3}\s*', '', text)
            text = re.sub(r'`([^`]+)`', r'\1', text)
            if not text:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="😶 Не вдалось отримати відповідь. Спробуй ще раз."
                )
                return

            # Шлемо частинами якщо довго
            if len(text) > 4000:
                chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
                for chunk in chunks:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=chunk,
                    )
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=text,
                )

            # Показуємо меню знову
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="📋 Ще тема?",
                reply_markup=self._make_menu(),
            )

        except Exception as e:
            logger.error(f"Onboarding error: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"❌ Помилка: {e}"
            )
