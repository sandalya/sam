import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from .base import BaseModule

logger = logging.getLogger("sam.catchup")

PERIOD_OPTIONS = {
    "3d": ("3 дні", 3),
    "7d": ("тиждень", 7),
    "14d": ("2 тижні", 14),
    "30d": ("місяць", 30),
    "60d": ("2 місяці", 60),
    "180d": ("пів року", 180),
    "365d": ("рік", 365),
}


class CatchupModule(BaseModule):

    def _build_prompt(self, days: int) -> str:
        today = datetime.now().strftime("%d %B %Y")
        topics_str = """- AI agents frameworks architectures
- MCP Model Context Protocol
- LLM new models releases Anthropic OpenAI Google
- AI developer tooling
- AI real world products use cases"""
        profile_ctx = self.profile_to_context()

        return f"""Сьогодні {today}. Зроби ретроспективу AI-новин за останні {days} днів.

Теми:
{topics_str}

{profile_ctx}

Знайди 7-10 найважливіших подій за цей період. Групуй по темах якщо є кілька з однієї області.

Відповідай українською, у HTML форматі для Telegram:

🗓 <b>Catchup за {days} днів — {today}</b>

По кожній події:
<b>[Назва]</b>
Що сталось (2-3 речення). Чому важливо для розробника AI-продуктів.
🔗 <a href="URL">посилання</a> якщо є

В кінці:
📌 <b>Головний висновок:</b> одне речення — що найважливіше знати після цього періоду.

Використовуй тільки теги: <b>, <i>, <a href="...">, <code>. Без markdown, без зірочок.

Тільки реальні події. Не вигадуй."""

    async def send_catchup(self, update: Update, days: int):
        await update.message.reply_text(
            f"⏳ Збираю catchup за {days} днів, це може зайняти хвилину..."
        )
        try:
            text = self.call_claude_with_search(self._build_prompt(days), max_tokens=3000)
            if not text:
                await update.message.reply_text("😶 Не вдалось зібрати catchup. Спробуй ще раз.")
                return

            if len(text) > 4000:
                chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode="HTML")
            else:
                await update.message.reply_text(text, parse_mode="HTML")

        except Exception as e:
            logger.error(f"Catchup error: {e}")
            await update.message.reply_text(f"❌ Помилка: {e}")
