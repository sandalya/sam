"""
shared/catchup_module.py — ретроспектива новин за N днів.
Агент задає: catchup_topics (str, multiline), catchup_domain (str).
"""
import logging
from datetime import datetime
from telegram import Update
from .agent_base import AgentBase

logger = logging.getLogger("shared.catchup")


class CatchupModule(AgentBase):
    catchup_topics: str = ""
    catchup_domain: str = "новин"

    def _build_prompt(self, days: int) -> str:
        today = datetime.now().strftime("%d %B %Y")
        profile_ctx = self.profile_to_context()
        return f"""Сьогодні {today}. Зроби ретроспективу {self.catchup_domain} за останні {days} днів.

Теми:
{self.catchup_topics}

{profile_ctx}

Знайди 7-10 найважливіших подій за цей період. Групуй по темах.

Відповідай українською, у HTML форматі для Telegram:
🗓 <b>Catchup за {days} днів — {today}</b>

По кожній події:
<b>[Назва]</b>
2-3 речення. Чому важливо.
🔗 <a href="URL">посилання</a> якщо є

В кінці:
📌 <b>Головний висновок:</b> одне речення.

Тільки теги: <b>, <i>, <a href="...">, <code>. Без markdown. Тільки реальні події."""

    async def send_catchup(self, update: Update, days: int):
        await update.message.reply_text(f"⏳ Збираю catchup за {days} днів...")
        try:
            text = self.call_claude_with_search(self._build_prompt(days), max_tokens=3000)
            if not text:
                await update.message.reply_text("😶 Не вдалось зібрати catchup.")
                return
            chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Catchup error: {e}")
            await update.message.reply_text(f"❌ Помилка: {e}")
