"""
shared/curriculum_engine.py — спільний движок curriculum для Sam і Garcia.
Агент задає CURRICULUM (list[dict]) і persona-специфічний промпт.
"""
import json
import logging
import httpx
from datetime import datetime
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from .agent_base import AgentBase, client, MODEL_SMART

log = logging.getLogger("shared.curriculum")

NOTEBOOKLM_FORMATS = [
    ("🎬 Відео", "video"),
    ("🎙️ Подкаст", "podcast"),
    ("🎤 Монолог", "audio"),
    ("📋 Study guide", "study"),
    ("📄 Briefing", "briefing"),
    ("🃏 Flashcards", "flashcards"),
    ("🧠 Mind Map", "mindmap"),
    ("📊 Slide Deck", "slides"),
    ("📈 Infographic", "infographic"),
]

FORMAT_NAMES = {
    "video": "🎬 Відео",
    "podcast": "🎙️ Подкаст",
    "audio": "🎤 Монолог",
    "study": "📋 Study guide",
    "briefing": "📄 Briefing",
    "flashcards": "🃏 Flashcards",
    "mindmap": "🧠 Mind Map",
    "slides": "📊 Slide Deck",
    "infographic": "📈 Infographic",
}

FORMAT_INSTRUCTIONS = {
    "video": "Створи промпт для генерації ВІДЕО у NotebookLM. Динамічна структура: вступ → концепти → практика → висновок.",
    "podcast": "Створи промпт для ПОДКАСТУ (діалог двох ведучих). Живий діалог, один пояснює, інший питає.",
    "audio": "Створи промпт для АУДІО МОНОЛОГУ. Впевнений тон, чітка структура, як якісна лекція.",
    "study": "Створи промпт для STUDY GUIDE. Ключові концепти → FAQ → питання для самоперевірки.",
    "briefing": "Створи промпт для BRIEFING DOC. Коротко: що це, навіщо, головні ідеї, застосування.",
    "flashcards": "Створи промпт для FLASHCARDS. Питання на одному боці, відповідь на іншому.",
    "mindmap": "Створи промпт для MIND MAP. Центральна ідея → гілки → підгілки.",
    "slides": "Створи промпт для SLIDE DECK. Кожен слайд — одна ідея.",
    "infographic": "Створи промпт для INFOGRAPHIC. Ключові цифри, порівняння, процеси у вигляді схем.",
}


class CurriculumEngine(AgentBase):
    """
    Підклас задає:
      CURRICULUM: list[dict]         — список тем
      notebooklm_context: str        — контекст аудиторії для NotebookLM промптів
      dynamic_curriculum_prompt: str — промпт для генерації динамічних тем
    """
    CURRICULUM: list[dict] = []
    notebooklm_context: str = ""
    dynamic_curriculum_prompt: str = ""

    def _state_path(self) -> Path:
        return self.data_dir / "curriculum.json"

    def _dynamic_path(self) -> Path:
        return self.data_dir / "curriculum_dynamic.json"

    def load_state(self) -> dict:
        p = self._state_path()
        return json.loads(p.read_text()) if p.exists() else {"completed": [], "started": [], "notes": {}}

    def save_state(self, state: dict):
        self._state_path().write_text(json.dumps(state, ensure_ascii=False, indent=2))

    def _load_dynamic(self) -> list:
        p = self._dynamic_path()
        return json.loads(p.read_text()) if p.exists() else []

    def _save_dynamic(self, topics: list):
        self._dynamic_path().write_text(json.dumps(topics, ensure_ascii=False, indent=2))

    def _generate_dynamic_topics(self, state: dict, profile: dict) -> list:
        if not self.dynamic_curriculum_prompt:
            return []
        completed = [i["title"] for i in self.CURRICULUM if i["id"] in state["completed"]]
        all_titles = [i["title"] for i in self.CURRICULUM]
        interests = profile.get("interests", [])
        scores = profile.get("scores", {})
        prompt = (
            self.dynamic_curriculum_prompt + "\n\n"
            f"Completed topics: {completed}\n"
            f"All seed topics: {all_titles}\n"
            f"Interests: {interests}\nScores: {scores}\n\n"
            "Return ONLY JSON array: id (start 100), title, estimate, why, read (URL), do."
        )
        try:
            response = client.messages.create(
                model=MODEL_SMART, max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "\n".join(b.text for b in response.content if b.type == "text")
            import re
            match = re.search(r"\[.*?\]", text, re.DOTALL)
            if not match:
                return []
            topics = json.loads(match.group())
            self._save_dynamic(topics)
            return topics
        except Exception as e:
            log.error(f"Dynamic curriculum error: {e}")
            return []

    def get_full_curriculum(self, state: dict, profile: dict) -> list:
        dynamic = self._load_dynamic()
        if profile.get("interests") and not dynamic:
            dynamic = self._generate_dynamic_topics(state, profile)
        return self.CURRICULUM + dynamic

    # ── UI helpers ─────────────────────────────────────────────────────────────

    def _status_icon(self, item_id: int, state: dict) -> str:
        if item_id in state["completed"]: return "✅"
        if item_id in state["started"]: return "🔄"
        return "⬜"

    def _progress_bar(self, state: dict, total_override: int = None) -> str:
        total = total_override or len(self.CURRICULUM)
        done = len(state["completed"])
        filled = round(done / total * 10) if total else 0
        return f"[{'█' * filled}{'░' * (10 - filled)}] {done}/{total}"

    def _item_text(self, item: dict, state: dict) -> str:
        icon = self._status_icon(item["id"], state)
        return (
            f"{icon} *{item['id']}. {item['title']}*\n"
            f"⏱ {item['estimate']}\n\n"
            f"*Навіщо:* {item['why']}\n\n"
            f"*Почитати:* [посилання]({item['read']})\n\n"
            f"*Зробити руками:*\n{item['do']}"
        )

    def _item_keyboard(self, item_id: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Почав", callback_data=f"cur_start|{item_id}"),
                InlineKeyboardButton("✅ Готово", callback_data=f"cur_done|{item_id}"),
            ],
            [InlineKeyboardButton("🎧 NotebookLM промпт", callback_data=f"cur_nb|{item_id}")],
            [InlineKeyboardButton("🎙️ Подкаст", callback_data=f"cur_podcast|{item_id}")],
            [InlineKeyboardButton("← Назад", callback_data="cur_back")],
        ])

    def _format_keyboard(self, item_id: int, selected: list) -> InlineKeyboardMarkup:
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

    # ── Fetch & NB prompt ─────────────────────────────────────────────────────

    async def _fetch_page(self, url: str) -> str:
        try:
            import re
            headers = {"User-Agent": "Mozilla/5.0 (compatible; AgentBot/1.0)"}
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
                resp = await c.get(url, headers=headers)
                resp.raise_for_status()
            text = re.sub(r"<[^>]+>", " ", resp.text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:8000]
        except Exception as e:
            log.error(f"Fetch error {url}: {e}")
            return ""

    def _generate_nb_prompt(self, item: dict, fmt: str, page_text: str) -> str:
        system = (
            f"Ти — асистент що допомагає вчитися ефективно. "
            f"Аудиторія: {self.notebooklm_context}\n"
            "Правила:\n"
            "1. Якщо тема складна — роби КІЛЬКА промптів (2-3) з фокусом.\n"
            "2. Кожен починай з '📌 Промпт N:' і давай назву.\n"
            "3. Промпт англійською, конкретний.\n"
            "4. В кінці: 'Контекст для NotebookLM:' 1-2 речення про аудиторію.\n"
        )
        user = (
            f"Тема: {item['title']}\nФормат: {FORMAT_NAMES[fmt]}\n"
            f"Інструкція: {FORMAT_INSTRUCTIONS[fmt]}\n\n"
            f"Ресурс: {item['read']}\n\nВміст:\n{page_text}\n\n"
            f"Склади промпт(и) для NotebookLM."
        )
        response = client.messages.create(
            model=MODEL_SMART, max_tokens=2000,
            system=[{"type": "text", "text": self.persona, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": f"{system}\n\n{user}"}],
        )
        return "\n".join(b.text for b in response.content if b.type == "text")

    # ── Command handlers ───────────────────────────────────────────────────────

    async def cmd_curriculum(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        profile = self.load_profile()
        state = self.load_state()
        all_topics = self.get_full_curriculum(state, profile)
        total, done = len(all_topics), len(state["completed"])
        filled = round(done / total * 10) if total else 0
        bar = f"[{'█' * filled}{'░' * (10 - filled)}] {done}/{total}"
        lines = [f"📚 Curriculum\n{bar}\n"]
        for item in all_topics:
            icon = self._status_icon(item["id"], state)
            tag = " ✨" if item["id"] >= 100 else ""
            lines.append(f"{icon} {item['id']}. {item['title']} — {item['estimate']}{tag}")
        lines.append("\nОбери тему:")
        btn_list = [
            InlineKeyboardButton(
                f"{self._status_icon(item['id'], state)} {item['id']}",
                callback_data=f"cur_item|{item['id']}"
            ) for item in all_topics
        ]
        rows = [btn_list[i:i+5] for i in range(0, len(btn_list), 5)]
        keyboard = InlineKeyboardMarkup(rows)
        await update.message.reply_text("\n".join(lines), reply_markup=keyboard)


    async def cmd_cur_add(self, update, context):
        """Додає нову тему в curriculum через /cur_add Назва теми."""
        args = context.args
        if not args:
            await update.message.reply_text(
                "Використання: /cur_add Назва теми\n"
                "Приклад: /cur_add Context Management & Memory Patterns"
            )
            return
        title = " ".join(args).strip()
        dynamic = self._load_dynamic()
        # ID: починаємо з 100 або наступний після останнього
        existing_ids = [t.get("id", 0) for t in dynamic]
        next_id = max(existing_ids + [99]) + 1
        new_topic = {
            "id": next_id,
            "title": title,
            "estimate": "1-3 дні",
            "why": "Додано вручну.",
            "read": "",
            "do": "",
        }
        dynamic.append(new_topic)
        self._save_dynamic(dynamic)
        await update.message.reply_text(
            f"✅ Тему додано в curriculum:\n*{title}*\n\nВикористай /cur щоб побачити оновлений план.",
            parse_mode="Markdown",
        )

    async def cmd_done(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        args = context.args
        if not args or not args[0].isdigit():
            await update.message.reply_text("Використання: /done <N>")
            return
        await self._mark_done(update.message, int(args[0]))

    async def _mark_done(self, msg, item_id: int):
        state = self.load_state()
        all_topics = self.get_full_curriculum(state, self.load_profile())
        item = next((i for i in all_topics if i["id"] == item_id), None)
        if not item:
            await msg.reply_text(f"Тема {item_id} не існує.")
            return
        if item_id not in state["completed"]:
            state["completed"].append(item_id)
        if item_id in state["started"]:
            state["started"].remove(item_id)
        state["notes"][str(item_id)] = {"completed_at": datetime.now().isoformat()}
        self.save_state(state)
        next_item = next((i for i in self.CURRICULUM if i["id"] not in state["completed"]), None)
        text = f"✅ *{item['title']}* — виконано!\n\n{self._progress_bar(state)}"
        if next_item:
            text += f"\n\nНаступна тема: *{next_item['id']}. {next_item['title']}*"
        else:
            text += "\n\n🎉 Curriculum завершено!"
        await msg.reply_text(text, parse_mode="Markdown")

    async def _generate_podcast_for_item(self, query, item: dict):
        """Генерує подкаст прямо з /cur без /podcast команди."""
        try:
            from shared.podcast_module import PodcastModule
            # Рахуємо "розмір" теми: довжина why + do + title як proxy
            content_size = len(item.get("why", "")) + len(item.get("do", "")) + len(item.get("title", ""))
            fmt = "deep" if content_size > 300 else "short"

            # Створюємо тимчасовий podcast instance з налаштуваннями поточного агента
            class _TmpPodcast(PodcastModule):
                podcast_audience = getattr(self, "podcast_audience", "AI developer")
                podcast_style = getattr(self, "podcast_style", "")
                CURRICULUM = getattr(self, "CURRICULUM", [])

            pod = _TmpPodcast.__new__(_TmpPodcast)
            pod.podcast_audience = getattr(self, "podcast_audience", "AI developer")
            pod.podcast_style = getattr(self, "podcast_style", "")
            pod.CURRICULUM = getattr(self, "CURRICULUM", [])
            pod.data_dir = self.data_dir
            pod.profile_path = self.profile_path

            import asyncio
            loop = asyncio.get_event_loop()
            script = await loop.run_in_executor(None, pod._generate_script, item, fmt)
            mp3_path = await loop.run_in_executor(None, pod._tts, script)

            label = "~8-12 хв" if fmt == "short" else "~15-20 хв"
            caption = (
                f"*{item['title']}*\n"
                f"_{label} • Curriculum #{item['id']}_\n\n"
                f"{item['why']}"
            )
            with open(mp3_path, "rb") as f:
                await query.message.reply_audio(
                    audio=f,
                    title=item["title"],
                    performer="Sam Podcast",
                    caption=caption,
                    parse_mode="Markdown",
                )
            mp3_path.unlink(missing_ok=True)
        except Exception as e:
            import logging
            logging.getLogger("shared.curriculum_engine").error(f"Podcast from cur failed: {e}", exc_info=True)
            await query.message.reply_text(f"❌ Помилка генерації подкасту: {e}")

    async def handle_curriculum_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        parts = query.data.split("|")
        action = parts[0]
        state = self.load_state()
        profile = self.load_profile()
        all_topics = self.get_full_curriculum(state, profile)

        if action == "cur_item":
            item_id = int(parts[1])
            item = next((i for i in all_topics if i["id"] == item_id), None)
            if not item: return
            await query.edit_message_text(
                self._item_text(item, state), parse_mode="Markdown",
                reply_markup=self._item_keyboard(item_id),
            )

        elif action == "cur_back":
            total, done = len(all_topics), len(state["completed"])
            filled = round(done / total * 10) if total else 0
            bar = f"[{'█' * filled}{'░' * (10 - filled)}] {done}/{total}"
            lines = [f"📚 Curriculum\n{bar}\n"]
            for item in all_topics:
                icon = self._status_icon(item["id"], state)
                tag = " ✨" if item["id"] >= 100 else ""
                lines.append(f"{icon} {item['id']}. {item['title']} — {item['estimate']}{tag}")
            lines.append("\nОбери тему:")
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    f"{self._status_icon(i['id'], state)} {i['id']}",
                    callback_data=f"cur_item|{i['id']}"
                ) for i in all_topics
            ]])
            await query.edit_message_text("\n".join(lines), reply_markup=keyboard)

        elif action == "cur_start":
            item_id = int(parts[1])
            item = next((i for i in all_topics if i["id"] == item_id), None)
            if not item: return
            if item_id not in state["started"] and item_id not in state["completed"]:
                state["started"].append(item_id)
            self.save_state(state)
            await query.edit_message_text(
                self._item_text(item, state), parse_mode="Markdown",
                reply_markup=self._item_keyboard(item_id),
            )

        elif action == "cur_done":
            item_id = int(parts[1])
            item = next((i for i in all_topics if i["id"] == item_id), None)
            if not item: return
            if item_id not in state["completed"]:
                state["completed"].append(item_id)
            if item_id in state["started"]:
                state["started"].remove(item_id)
            state["notes"][str(item_id)] = {"completed_at": datetime.now().isoformat()}
            self.save_state(state)
            await query.edit_message_text(
                self._item_text(item, state), parse_mode="Markdown",
                reply_markup=self._item_keyboard(item_id),
            )

        elif action == "cur_nb":
            item_id = int(parts[1])
            item = next((i for i in all_topics if i["id"] == item_id), None)
            if not item: return
            all_fmts = [fmt for _, fmt in NOTEBOOKLM_FORMATS]
            context.user_data[f"nb_selected_{item_id}"] = all_fmts
            await query.edit_message_text(
                f"🎧 *{item['title']}*\n\nОбери формати для NotebookLM:",
                parse_mode="Markdown",
                reply_markup=self._format_keyboard(item_id, all_fmts),
            )

        elif action == "cur_nbtoggle":
            item_id, fmt = int(parts[1]), parts[2]
            item = next((i for i in all_topics if i["id"] == item_id), None)
            if not item: return
            key = f"nb_selected_{item_id}"
            selected = context.user_data.get(key, [])
            if fmt in selected: selected.remove(fmt)
            else: selected.append(fmt)
            context.user_data[key] = selected
            await query.edit_message_text(
                f"🎧 *{item['title']}*\n\nОбери формати для NotebookLM:",
                parse_mode="Markdown",
                reply_markup=self._format_keyboard(item_id, selected),
            )

        elif action == "cur_podcast":
            item_id = int(parts[1])
            item = next((i for i in all_topics if i["id"] == item_id), None)
            if not item: return
            await query.edit_message_text(
                f"🎙️ *{item['title']}*\n\nГенерую подкаст... займе ~1-2 хв",
                parse_mode="Markdown",
            )
            import asyncio
            asyncio.create_task(self._generate_podcast_for_item(query, item))

        elif action == "cur_nbrun":
            item_id = int(parts[1])
            item = next((i for i in all_topics if i["id"] == item_id), None)
            if not item: return
            selected = context.user_data.get(f"nb_selected_{item_id}", [])
            if not selected:
                await query.answer("Обери хоча б один формат", show_alert=True)
                return
            names = ", ".join(FORMAT_NAMES.get(f, f) for f in selected)
            await query.edit_message_text(
                f"⏳ Генерую: {names}\n\nТема: *{item['title']}*", parse_mode="Markdown",
            )
            from shared.notebooklm_module import generate_and_notify, get_or_create_notebook, _run as nb_run
            import asyncio

            async def _run_all_formats(bot, chat_id, item, selected, data_dir):
                try:
                    notebook_id = await get_or_create_notebook(item["id"], item["title"], data_dir)
                except Exception as e:
                    try:
                        await bot.send_message(chat_id, f"❌ Не вдалось створити notebook: {e}")
                    except Exception:
                        pass
                    return
                if not notebook_id:
                    try:
                        await bot.send_message(chat_id, "❌ Не вдалось створити notebook.")
                    except Exception:
                        pass
                    return
                page_text = await self._fetch_page(item["read"])
                await nb_run(["source", "add", "-n", notebook_id, item["read"]])
                for fmt in selected:
                    instructions = ""
                    if page_text:
                        loop = asyncio.get_event_loop()
                        instructions = await loop.run_in_executor(None, self._generate_nb_prompt, item, fmt, page_text)
                        if "📌 Промпт 1:" in instructions:
                            instructions = instructions.split("📌 Промпт 1:")[-1].split("📌 Промпт 2:")[0].strip()
                        instructions = instructions[:500]
                    try:
                        await generate_and_notify(
                            bot=bot,
                            chat_id=chat_id,
                            topic_id=item["id"],
                            topic_title=item["title"],
                            source_url=item["read"],
                            fmt=fmt,
                            instructions=instructions,
                            skip_source=True,
                            data_dir=data_dir,
                        )
                    except Exception as e:
                        import logging
                        logging.getLogger("shared.curriculum").warning(f"generate_and_notify failed: {e}")

            asyncio.create_task(_run_all_formats(
                bot=query.get_bot(),
                chat_id=query.message.chat_id,
                item=item,
                selected=selected,
                data_dir=self.data_dir,
            ))
