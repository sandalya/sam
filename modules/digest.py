import asyncio
import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application

from .base import BaseModule

logger = logging.getLogger("sam.digest")

TOPICS = [
    "AI agents frameworks architectures 2025",
    "MCP Model Context Protocol new servers integrations",
    "LLM new models releases Anthropic OpenAI Google",
    "AI agents real world use cases products",
    "LLM developer tooling prompting evals",
]


class DigestModule(BaseModule):

    def _build_prompt(self) -> str:
        today = datetime.now().strftime("%d %B %Y")
        topics_str = "\n".join(f"- {t}" for t in TOPICS)
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
        raw = self.call_claude_with_search(self._build_prompt())
        return self.parse_json_response(raw)

    def _format_item(self, item: dict) -> str:
        return (
            f"🤖 *{item['title']}*\n"
            f"{item['summary']}\n"
            f"[Читати далі]({item.get('url', '#')})"
        )

    def _feedback_keyboard(self, item_id: str, topic_key: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("🔥 Топ", callback_data=f"like|{item_id}|{topic_key}"),
            InlineKeyboardButton("👎 Нудно", callback_data=f"dislike|{item_id}|{topic_key}"),
        ]])

    async def send(self, app: Application):
        items = self._fetch_items()
        if not items:
            await app.bot.send_message(
                chat_id=self.owner_chat_id,
                text="😶 Нічого цікавого за останні 24 год. Спробую завтра."
            )
            return

        header = (
            f"🤖 *AI Дайджест — {datetime.now().strftime('%d.%m.%Y')}*\n"
            f"Найцікавіше за останні 24 години:"
        )
        await app.bot.send_message(chat_id=self.owner_chat_id, text=header, parse_mode="Markdown")

        for idx, item in enumerate(items):
            item_id = f"{datetime.now().strftime('%Y%m%d')}_{idx}"
            topic_key = item.get("topic_key", "general")
            await app.bot.send_message(
                chat_id=self.owner_chat_id,
                text=self._format_item(item),
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
        sorted_t = sorted(profile["scores"].items(), key=lambda x: x[1], reverse=True)
        for topic, score in sorted_t:
            bar = "🔥" * min(abs(score), 5) if score > 0 else "👎" * min(abs(score), 5)
            lines.append(f"`{topic}` {bar} ({score:+d})")

        if profile["notes"]:
            lines.append("\n📝 *Побажання:*")
            for note in profile["notes"][-5:]:
                lines.append(f"— {note}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
