import asyncio
import logging
from datetime import datetime

from telegram.ext import Application

from .base import BaseModule

logger = logging.getLogger("sam.science")

TOPICS = [
    "quantum computing breakthrough 2025",
    "CRISPR biology medicine breakthrough this week",
    "NASA SpaceX space discovery 2025",
    "Nature Science top research papers this week",
    "longevity aging science research 2025",
]


class ScienceModule(BaseModule):

    def _build_prompt(self) -> str:
        today = datetime.now().strftime("%d %B %Y")
        topics_str = "\n".join(f"- {t}" for t in TOPICS)

        return f"""Сьогодні {today}. Знайди 5-7 найцікавіших наукових новин за останній тиждень по темах:
{topics_str}

Сортуй від найбільш проривної до менш важливої.
Відповідь ТІЛЬКИ у форматі JSON масиву, без markdown, без пояснень:
[
  {{
    "title": "Коротка назва (до 10 слів)",
    "summary": "2-3 речення: що відкрили/досягли і чому це важливо для науки.",
    "url": "https://...",
    "field": "галузь науки одним словом"
  }}
]

Тільки реальні новини з реальними URL. Не вигадуй."""

    def _fetch_items(self) -> list[dict]:
        raw = self.call_claude_with_search(self._build_prompt())
        return self.parse_json_response(raw)

    def _format_item(self, item: dict) -> str:
        field_emoji = {
            "physics": "⚛️", "biology": "🧬", "medicine": "💊",
            "space": "🚀", "chemistry": "🧪", "math": "📐",
        }.get(item.get("field", "").lower(), "🔬")

        return (
            f"{field_emoji} *{item['title']}*\n"
            f"{item['summary']}\n"
            f"[Читати далі]({item.get('url', '#')})"
        )

    async def send(self, app: Application):
        items = self._fetch_items()
        if not items:
            await app.bot.send_message(
                chat_id=self.owner_chat_id,
                text="🔬 Нічого проривного за цей тиждень. Спробую наступної суботи."
            )
            return

        header = (
            f"🔬 *Наука тижня — {datetime.now().strftime('%d.%m.%Y')}*\n"
            f"Найцікавіше з наукового світу:"
        )
        await app.bot.send_message(chat_id=self.owner_chat_id, text=header, parse_mode="Markdown")

        for item in items:
            await app.bot.send_message(
                chat_id=self.owner_chat_id,
                text=self._format_item(item),
                parse_mode="Markdown",
                disable_web_page_preview=False,
            )
            await asyncio.sleep(0.5)
