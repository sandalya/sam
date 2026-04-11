"""
shared/digest_module.py — спільна логіка дайджесту для Sam і Garcia.
Агент задає self.topics і self.digest_label в підкласі або при ініціалізації.
"""
import asyncio
import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application

from .agent_base import AgentBase

logger = logging.getLogger("shared.digest")


class DigestModule(AgentBase):
    """
    Підклас задає:
      topics: list[str]       — теми пошуку
      digest_label: str       — назва дайджесту, напр. "AI" або "Packaging Design"
      overview_style: str     — стиль Claude для огляду (напр. "як Сем" або "як Гарсіа")
    """
    topics: list[str] = []
    digest_label: str = "Дайджест"
    overview_style: str = "коротко, чітко, з характером"

    def _build_prompt(self) -> str:
        today = datetime.now().strftime("%d %B %Y")
        topics_str = "\n".join(f"- {t}" for t in self.topics)
        profile_ctx = self.profile_to_context()
        return f"""Сьогодні {today}. Знайди 5-7 найцікавіших новин за останні 24 години по темах:
{topics_str}

{profile_ctx}

Сортуй від найцікавішої до найменш цікавої.
Відповідь ТІЛЬКИ у форматі JSON масиву, без markdown, без пояснень:
[
  {{
    "title": "Коротка назва (до 10 слів)",
    "summary": "2-3 речення: що сталось і чому важливо.",
    "url": "https://...",
    "topic_key": "категорія англійською 1-2 слова"
  }}
]
Тільки реальні новини з реальними URL. Не вигадуй."""

    def _fetch_items(self) -> list[dict]:
        return self.parse_json_response(self.call_claude_with_search(self._build_prompt()))

    def _format_item(self, item: dict, idx: int) -> str:
        return (
            f"*({idx}) {item['title']}*\n"
            f"{item['summary']}\n"
            f"[Читати далі]({item.get('url', '#')})"
        )

    def _feedback_keyboard(self, item_id: str, topic_key: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("🔥 Топ", callback_data=f"like|{item_id}|{topic_key}"),
            InlineKeyboardButton("👎 Нудно", callback_data=f"dislike|{item_id}|{topic_key}"),
        ]])

    def _build_overview(self, items: list[dict]) -> str:
        titles = "\n".join(f"({i+1}) {item['title']}: {item['summary']}" for i, item in enumerate(items))
        prompt = (
            f"Ось пронумерований список новин за сьогодні:\n{titles}\n\n"
            "Напиши вижимку українською: 3-5 речень. "
            "Що за день? Які теми домінують? Що найважливіше і чому? "
            "Дай свою суб'єктивну оцінку — що реально варто уваги, а що шум. "
            "Посилайся на новини через номери в дужках, наприклад: (2), (3). "
            f"Стиль — {self.overview_style}. Без заголовків і списків."
        )
        return self.call_claude(prompt, smart=False) or ""

    async def send(self, app: Application):
        items = self._fetch_items()
        if not items:
            await app.bot.send_message(
                chat_id=self.owner_chat_id,
                text="😶 Нічого цікавого за останні 24 год. Спробую завтра."
            )
            return
        overview = self._build_overview(items)
        header = (
            f"🤖 *{self.digest_label} Дайджест — {datetime.now().strftime('%d.%m.%Y')}*\n\n"
            f"{overview}\n\n— — —"
        )
        await app.bot.send_message(chat_id=self.owner_chat_id, text=header, parse_mode="Markdown")
        for idx, item in enumerate(items):
            item_id = f"{datetime.now().strftime('%Y%m%d')}_{idx}"
            topic_key = item.get("topic_key", "general")
            await app.bot.send_message(
                chat_id=self.owner_chat_id,
                text=self._format_item(item, idx + 1),
                parse_mode="Markdown",
                reply_markup=self._feedback_keyboard(item_id, topic_key),
                disable_web_page_preview=False,
            )
            await asyncio.sleep(0.5)

    async def handle_feedback(self, update):
        query = update.callback_query
        await query.answer()
        parts = query.data.split("|")
        action, item_id, topic_key = parts[0], parts[1], parts[2]
        if action == "like":
            self.update_score(topic_key, +1)
            await query.edit_message_reply_markup(
                InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Записав!", callback_data="done")]])
            )
        elif action == "dislike":
            self.update_score(topic_key, -1)
            await query.edit_message_reply_markup(
                InlineKeyboardMarkup([[InlineKeyboardButton("👎 Зрозумів, менше такого", callback_data="done")]])
            )

    async def send_profile(self, update: Update):
        profile = self.load_profile()
        if not profile["scores"] and not profile["notes"]:
            await update.message.reply_text(
                "📊 Профіль поки порожній.\nНатискай 🔥 і 👎 під новинами — я навчусь."
            )
            return
        lines = ["📊 *Профіль інтересів:*\n"]
        for topic, score in sorted(profile["scores"].items(), key=lambda x: x[1], reverse=True):
            bar = "🔥" * min(abs(score), 5) if score > 0 else "👎" * min(abs(score), 5)
            lines.append(f"`{topic}` {bar} ({score:+d})")
        if profile.get("notes"):
            lines.append("\n📝 *Побажання:*")
            for note in profile["notes"][-5:]:
                lines.append(f"— {note}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
