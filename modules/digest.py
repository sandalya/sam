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
        now = datetime.now()
        today_str = now.strftime("%d %B %Y")
        today_iso = now.strftime("%Y-%m-%d")
        topics_str = "\n".join(f"- {t}" for t in TOPICS)
        profile_ctx = self.profile_to_context()

        return f"""Сьогодні {today_str} ({today_iso}). Знайди актуальні AI-новини по темах:
{topics_str}

{profile_ctx}

Розбий знахідки на 3 блоки:

БЛОК 1 — "hot": 3-4 новини строго за останні 24-48 годин (не старіше). Тільки свіже.
БЛОК 2 — "week": 2-3 важливі події цього тижня, які ще актуальні але можуть бути 3-7 днів тому.
БЛОК 3 — "foryou": 1-2 речі конкретно корисні для розробника AI-продуктів зараз (інструменти, техніки, практики).

ВАЖЛИВО:
- Всі поля (title, summary, detail) — виключно українською мовою
- БЛОК "hot": лише новини після {today_iso}, нічого старішого
- БЛОК "week": лише новини не старіші 7 днів від {today_iso}
- Якщо свіжих новин немає — краще менше, ніж старі
- Не вигадуй події. Не використовуй новини 2024 або раніших років

Відповідь ТІЛЬКИ у форматі JSON, без markdown, без пояснень:
{{
  "hot": [
    {{
      "title": "Коротка назва українською (до 10 слів)",
      "summary": "2-3 речення суті українською.",
      "detail": "5-7 речень детального аналізу українською: що відбулось, чому важливо, які наслідки для AI-розробників.",
      "url": "https://...",
      "topic_key": "category in english 1-2 words",
      "date_hint": "коли приблизно (напр: сьогодні, вчора, 2 дні тому)"
    }}
  ],
  "week": [ ...той самий формат... ],
  "foryou": [ ...той самий формат... ]
}}

Тільки реальні новини з реальними URL. Дата має бути точною."""

    def _fetch_items(self) -> dict:
        import re
        raw = self.call_claude_with_search(self._build_prompt(), max_tokens=3000)
        logger.info(f"RAW response (first 500): {raw[:500] if raw else 'EMPTY'}")
        # Чистимо cite-теги які Claude вставляє при web_search
        raw = re.sub(r'<cite[^>]*>|</cite>', '', raw)
        parsed = self.parse_json_response(raw)
        logger.info(f"PARSED type={type(parsed).__name__}, value={str(parsed)[:300]}")
        if isinstance(parsed, dict):
            return parsed
        return {"hot": parsed or [], "week": [], "foryou": []}

    def _build_overview(self, data: dict) -> str:
        all_items = []
        for block in ["hot", "week", "foryou"]:
            all_items.extend(data.get(block, []))

        if not all_items:
            return ""

        numbered = "\n".join(
            f"({i+1}) [{item.get('date_hint', '')}] {item['title']}: {item['summary']}"
            for i, item in enumerate(all_items)
        )
        prompt = (
            f"Ось пронумеровані AI-новини на {datetime.now().strftime('%d.%m.%Y')}:\n{numbered}\n\n"
            "Напиши міні-бріф: 3-4 речення. Що головне сьогодні? Які теми домінують? "
            "Посилайся на новини через номери в дужках: (1), (2) тощо. "
            "Стиль — як Сем: лаконічно, по ділу, з характером. Без заголовків і списків."
        )
        return self.call_claude(prompt) or ""

    def _format_item(self, item: dict, idx: int) -> str:
        date_hint = item.get("date_hint", "")
        date_tag = f" _({date_hint})_" if date_hint else ""
        return (
            f"*({idx}) {item['title']}*{date_tag}\n"
            f"{item['summary']}\n"
            f"[Читати далі]({item.get('url', '#')})"
        )

    def _detail_keyboard(self, item_id: str, topic_key: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("🔍 Детальніше", callback_data=f"detail|{item_id}|{topic_key}"),
            InlineKeyboardButton("🔥 Топ", callback_data=f"like|{item_id}|{topic_key}"),
            InlineKeyboardButton("👎 Нудно", callback_data=f"dislike|{item_id}|{topic_key}"),
        ]])

    async def send(self, app: Application):
        data = self._fetch_items()

        hot = data.get("hot", [])
        week = data.get("week", [])
        foryou = data.get("foryou", [])

        all_items = hot + week + foryou

        if not all_items:
            await app.bot.send_message(
                chat_id=self.owner_chat_id,
                text="😶 Нічого цікавого за останні 24 год. Спробую завтра."
            )
            return

        # Зберігаємо detail для callback
        self._detail_cache = {}
        for i, item in enumerate(all_items):
            item_id = f"{datetime.now().strftime('%Y%m%d')}_{i}"
            item["_id"] = item_id
            self._detail_cache[item_id] = item.get("detail", "")

        overview = self._build_overview(data)

        header = (
            f"🤖 *AI Дайджест — {datetime.now().strftime('%d.%m.%Y')}*\n\n"
            f"{overview}\n\n— — —"
        )
        await app.bot.send_message(
            chat_id=self.owner_chat_id, text=header, parse_mode="Markdown"
        )
        await asyncio.sleep(0.3)

        idx = 1

        if hot:
            await app.bot.send_message(
                chat_id=self.owner_chat_id, text="🔥 *Гаряче (24г)*", parse_mode="Markdown"
            )
            for item in hot:
                await app.bot.send_message(
                    chat_id=self.owner_chat_id,
                    text=self._format_item(item, idx),
                    parse_mode="Markdown",
                    reply_markup=self._detail_keyboard(item["_id"], item.get("topic_key", "general")),
                    disable_web_page_preview=True,
                )
                await asyncio.sleep(0.4)
                idx += 1

        if week:
            await app.bot.send_message(
                chat_id=self.owner_chat_id, text="📌 *Важливо цього тижня*", parse_mode="Markdown"
            )
            for item in week:
                await app.bot.send_message(
                    chat_id=self.owner_chat_id,
                    text=self._format_item(item, idx),
                    parse_mode="Markdown",
                    reply_markup=self._detail_keyboard(item["_id"], item.get("topic_key", "general")),
                    disable_web_page_preview=True,
                )
                await asyncio.sleep(0.4)
                idx += 1

        if foryou:
            await app.bot.send_message(
                chat_id=self.owner_chat_id, text="💡 *Для тебе зараз*", parse_mode="Markdown"
            )
            for item in foryou:
                await app.bot.send_message(
                    chat_id=self.owner_chat_id,
                    text=self._format_item(item, idx),
                    parse_mode="Markdown",
                    reply_markup=self._detail_keyboard(item["_id"], item.get("topic_key", "general")),
                    disable_web_page_preview=True,
                )
                await asyncio.sleep(0.4)
                idx += 1

    async def handle_feedback(self, update):
        query = update.callback_query
        await query.answer()

        parts = query.data.split("|")
        action = parts[0]

        if action == "detail":
            item_id = parts[1]
            topic_key = parts[2]
            detail_text = getattr(self, "_detail_cache", {}).get(item_id, "")
            if detail_text:
                original = query.message.text or ""
                title_line = original.split("\n")[0] if original else ""
                new_text = f"{title_line}\n\n{detail_text}"
                feedback_kb = InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔥 Топ", callback_data=f"like|{item_id}|{topic_key}"),
                    InlineKeyboardButton("👎 Нудно", callback_data=f"dislike|{item_id}|{topic_key}"),
                ]])
                await query.edit_message_text(
                    text=new_text,
                    reply_markup=feedback_kb,
                    parse_mode="Markdown",
                )
            else:
                await query.answer("😕 Деталі не збереглись — спробуй /digest знову.", show_alert=True)
            return

        item_id, topic_key = parts[1], parts[2]

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
