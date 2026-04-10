import logging
from datetime import datetime

from telegram.ext import Application

from .base import BaseModule

logger = logging.getLogger("sam.jobs")

PROFILE_CONTEXT = """
Саша — розробник з досвідом у Python, Telegram-ботах, AI-інтеграціях (Anthropic, Gemini).
Будує AI-агентів і ботів під конкретних людей. Хоче виходити на ринок праці в AI/ML сфері.
"""


class JobsModule(BaseModule):

    def _build_prompt(self) -> str:
        today = datetime.now().strftime("%d %B %Y")
        return f"""Сьогодні {today}.

{PROFILE_CONTEXT}

Зроби аналіз ринку праці для AI-розробника у 3 блоках:

## 1. Поточний стан ринку
Що зараз шукають роботодавці в AI/ML/LLM сфері. Які ролі найбільш затребувані (AI Engineer, Prompt Engineer, ML Engineer, LLM Ops тощо). Де є попит — remote, EU, US. Рівень зарплат орієнтовно.

## 2. Що потрібно знати
Конкретні скіли, інструменти, фреймворки які зараз в тренді та часто зустрічаються у вакансіях. Чого зазвичай не вистачає кандидатам. Які сертифікати або портфоліо-проекти підвищують шанси.

## 3. План входу для Саші
Враховуючи його бекграунд (Python, AI-боти, Anthropic API, Gemini, Telegram) — конкретні наступні кроки. Що допрацювати в портфоліо, куди дивитись, з чого почати пошук.

Відповідай українською, конкретно і по ділу. Без води."""

    async def send(self, app: Application):
        await app.bot.send_message(
            chat_id=self.owner_chat_id,
            text="📊 Аналізую ринок праці, хвилинку..."
        )
        result = self.call_claude_with_search(self._build_prompt(), max_tokens=3000)

        if not result:
            await app.bot.send_message(
                chat_id=self.owner_chat_id,
                text="😶 Не вдалось зібрати аналіз. Спробуй ще раз."
            )
            return

        header = f"💼 *Ринок праці — {datetime.now().strftime('%d.%m.%Y')}*\n\n"
        await app.bot.send_message(
            chat_id=self.owner_chat_id,
            text=header + result,
            parse_mode="Markdown",
        )

    async def send_on_command(self, update, app: Application):
        await update.message.reply_text("📊 Аналізую ринок праці, хвилинку...")
        result = self.call_claude_with_search(self._build_prompt(), max_tokens=3000)

        if not result:
            await update.message.reply_text("😶 Не вдалось зібрати аналіз. Спробуй ще раз.")
            return

        header = f"💼 *Ринок праці — {datetime.now().strftime('%d.%m.%Y')}*\n\n"
        await update.message.reply_text(header + result, parse_mode="Markdown")
