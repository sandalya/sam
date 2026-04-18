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
    ("🎙️ Подкаст NbLM", "podcast"),
    ("🃏 Flashcards", "flashcards"),
    ("📊 Slide Deck", "slides"),
    ("📈 Infographic", "infographic"),
]

FORMAT_NAMES = {
    "video":       "🎬 Відео",
    "podcast":     "🎙️ Подкаст NbLM",
    "flashcards":  "🃏 Flashcards",
    "slides":      "📊 Slide Deck",
    "infographic": "📈 Infographic",
    "tts":         "🔊 Подкаст TTS",
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
            "Return ONLY JSON array: id (start 100), title, estimate, why, read, do.\n\n"
            "CRITICAL for the read field:\n"
            "- Must be a SPECIFIC article, blog post, paper, or single documentation page\n"
            "- NOT a landing page, hub, or index (e.g. NOT https://privacy.anthropic.com/, NOT https://docs.anthropic.com/)\n"
            "- NOT a homepage or category page with many sub-links\n"
            "- Prefer: Anthropic research posts, specific docs sections like /docs/build-with-claude/tool-use, arxiv papers, engineering blog posts\n"
            "- Rule of thumb: if URL ends with / or /home or /center, it is probably a hub and wrong choice\n"
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

    @staticmethod
    def _md_escape(text: str) -> str:
        """Екранує символи що ламають Markdown v1."""
        for ch in ["_", "*", "`", "["]:
            text = text.replace(ch, "\\" + ch)
        return text

    def _item_text(self, item: dict, state: dict) -> str:
        icon = self._status_icon(item["id"], state)
        from shared.notebooklm_module import load_nb_state, FORMAT_NAMES as NB_NAMES
        nb_state = load_nb_state(self.data_dir)
        entry = nb_state.get(str(item["id"]))
        if entry and isinstance(entry, dict) and entry.get("generated"):
            nb_line = "\n\n*NbLM:* " + "  ".join(NB_NAMES.get(f, f) for f in entry["generated"])
        else:
            nb_line = ""
        e = self._md_escape
        return (
            f"{icon} *{item['id']}. {e(item['title'])}*\n"
            f"⏱ {e(item['estimate'])}\n\n"
            f"*Навіщо:* {e(item['why'])}\n\n"
            f"*Почитати:* [посилання]({item['read']})\n\n"
            f"*Зробити руками:*\n{e(item['do'])}"
            f"{nb_line}"
        )

    def _item_keyboard(self, item_id: int) -> InlineKeyboardMarkup:
        rows = [
            [
                InlineKeyboardButton("🔄 Почав", callback_data=f"cur_start|{item_id}"),
                InlineKeyboardButton("✅ Готово", callback_data=f"cur_done|{item_id}"),
            ],
            [InlineKeyboardButton("← Назад", callback_data="cur_back")],
        ]
        return InlineKeyboardMarkup(rows)

    def _format_keyboard(self, item_id: int, selected: list) -> InlineKeyboardMarkup:
        from shared.notebooklm_module import load_nb_state
        nb_state = load_nb_state(self.data_dir)
        entry = nb_state.get(str(item_id))
        already_done = entry.get("generated", []) if isinstance(entry, dict) else []
        buttons = [
            InlineKeyboardButton(
                f"{'🔒' if fmt in already_done else ('✅' if fmt in selected else '⬜')} {label}",
                callback_data=f"cur_nbtoggle|{item_id}|{fmt}" if fmt not in already_done else f"cur_nb_done_noop|{item_id}"
            )
            for label, fmt in NOTEBOOKLM_FORMATS
        ]
        rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
        active = [f for f in selected if f not in already_done]
        if active:
            rows.append([InlineKeyboardButton(f"▶️ Генерувати ({len(active)})", callback_data=f"cur_nbrun|{item_id}")])
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

    PAGE_SIZE = 8

    def _curriculum_message(self, all_topics, state, page=0):
        total, done = len(all_topics), len(state["completed"])
        filled = round(done / total * 10) if total else 0
        bar = f"[{'█' * filled}{'░' * (10 - filled)}] {done}/{total}"
        lines = [f"📚 Curriculum\n{bar}\n"]
        for item in all_topics:
            icon = self._status_icon(item["id"], state)
            tag = " ✨" if item["id"] >= 100 else ""
            lines.append(f"{icon} {item['id']}. {item['title']} — {item['estimate']}{tag}")
        lines.append("\nОбери тему:")

        start = page * self.PAGE_SIZE
        page_topics = all_topics[start:start + self.PAGE_SIZE]
        btn_list = [
            InlineKeyboardButton(
                f"{self._status_icon(item['id'], state)} {item['id']}",
                callback_data=f"cur_item|{item['id']}"
            ) for item in page_topics
        ]
        rows = [btn_list[i:i+4] for i in range(0, len(btn_list), 4)]

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("← Назад", callback_data=f"cur_page|{page-1}"))
        total_pages = (len(all_topics) + self.PAGE_SIZE - 1) // self.PAGE_SIZE
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(f"Далі → ({page+1+1}/{total_pages})", callback_data=f"cur_page|{page+1}"))
        if nav:
            rows.append(nav)

        return "\n".join(lines), InlineKeyboardMarkup(rows)

    async def cmd_curriculum(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        profile = self.load_profile()
        state = self.load_state()
        all_topics = self.get_full_curriculum(state, profile)
        text, keyboard = self._curriculum_message(all_topics, state, page=0)
        await update.message.reply_text(text, reply_markup=keyboard)


    # ── Podcast state helpers ─────────────────────────────────────────────────
    def _podcast_state_path(self):
        return self.data_dir / "podcasts_state.json"

    def _load_podcast_state(self) -> dict:
        import json
        p = self._podcast_state_path()
        return json.loads(p.read_text()) if p.exists() else {}

    def _save_podcast_state(self, state: dict):
        import json
        p = self._podcast_state_path()
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2))
        tmp.rename(p)

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
        # ID: продовжуємо після останнього ID з усіх тем (static + dynamic)
        all_ids = [t.get("id", 0) for t in self.CURRICULUM] + [t.get("id", 0) for t in dynamic]
        next_id = max(all_ids + [0]) + 1
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

    async def _generate_podcast_for_item(self, query, item: dict, fmt: str | None = None):
        """Генерує подкаст прямо з /cur без /podcast команди."""
        try:
            from shared.podcast_module import PodcastModule
            if fmt is None:
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


    async def _run_formats_with_backoff(self, bot, chat_id, item, selected, data_dir):
        """Генерує формати з exponential backoff. В чат тільки фінальний підсумок."""
        import asyncio
        import logging
        log = logging.getLogger("shared.curriculum_engine")
        from shared.notebooklm_module import generate_fmt, get_or_create_notebook as _get_nb, _run as nb_run2, FORMAT_NAMES as FN, load_nb_state, save_nb_state

        # Маркуємо генерацію як in_progress
        _nb_st = load_nb_state(data_dir)
        _nb_key = str(item["id"])
        if _nb_key not in _nb_st:
            _nb_st[_nb_key] = {"notebook_id": None, "generated": [], "pending": []}
        _nb_st[_nb_key]["pending"] = selected
        _nb_st[_nb_key]["status"] = "in_progress"
        save_nb_state(_nb_st, data_dir)
        log.info(f"[NbLM] topic {item['id']} marked in_progress, pending={selected}")

        try:
            notebook_id = await _get_nb(item["id"], item["title"], data_dir, category=item.get("category", "AGENT"))
        except Exception as e:
            await bot.send_message(chat_id, f"\u274c Не вдалось створити notebook: {e}")
            return
        if not notebook_id:
            log.warning(f"[NbLM] topic {item['id']} has no notebook_id, skipping")
            return
        nb_url = f"https://notebooklm.google.com/notebook/{notebook_id}"
        if item.get("read"):
            rc, _, stderr = await nb_run2(["source", "add", "-n", notebook_id, item["read"]])
            if rc != 0:
                log.warning(f"Add source warning (ignored): {stderr}")
        page_text = await self._fetch_page(item["read"]) if item.get("read") else ""
        BACKOFF = [0, 15 * 60, 30 * 60, 60 * 60, 120 * 60]
        FMT_PAUSE = 45
        results = {}
        for fmt_idx, fmt in enumerate(selected):
            if fmt_idx > 0:
                log.info(f"Pause {FMT_PAUSE}s before {fmt}")
                await asyncio.sleep(FMT_PAUSE)
            instructions = ""
            if page_text:
                loop = asyncio.get_event_loop()
                instructions = await loop.run_in_executor(None, self._generate_nb_prompt, item, fmt, page_text)
                if "\U0001f4cc" in instructions and "1:" in instructions:
                    instructions = instructions.split("1:")[-1].split("2:")[0].strip()
                instructions = instructions[:500]
            ok, err = False, "error"
            for attempt, delay in enumerate(BACKOFF):
                if delay:
                    log.info(f"[NbLM] {fmt} rate_limit attempt {attempt}, waiting {delay//60}min")
                    await asyncio.sleep(delay)
                try:
                    ok, err = await generate_fmt(notebook_id, fmt, instructions, item["id"], data_dir)
                except Exception as e:
                    log.warning(f"generate_fmt {fmt} exception: {e}")
                    err, ok = "error", False
                if ok or err != "rate_limit":
                    break
            results[fmt] = "ok" if ok else err
        # Знімаємо in_progress маркер
        _nb_st2 = load_nb_state(data_dir)
        if str(item["id"]) in _nb_st2:
            _nb_st2[str(item["id"])]["status"] = "done"
            _nb_st2[str(item["id"])]["pending"] = []
            save_nb_state(_nb_st2, data_dir)
        log.info(f"[NbLM] topic {item['id']} marked done")

        log.info(f"[NbLM] topic {item['id']} results: {results}")

    async def _run_all_formats_task(self, bot, chat_id, item, selected, data_dir):
        """Публічний wrapper — делегує в _run_formats_with_backoff."""
        await self._run_formats_with_backoff(bot, chat_id, item, selected, data_dir)

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
            from shared.hub_renderer import hub_page
            try:
                text, keyboard = hub_page(all_topics, page=0, data_dir=self.data_dir)
                await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)
            except Exception:
                text, keyboard = self._curriculum_message(all_topics, state, page=0)
                await query.edit_message_text(text, reply_markup=keyboard)


        elif action == "cur_page":
            page = int(parts[1]) if len(parts) > 1 else 0
            from shared.hub_renderer import hub_page
            try:
                text, keyboard = hub_page(all_topics, page=page, data_dir=self.data_dir)
                await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)
            except Exception:
                text, keyboard = self._curriculum_message(all_topics, state, page=page)
                await query.edit_message_text(text, reply_markup=keyboard)

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
            ps = self._load_podcast_state()
            entry = ps.get(str(item_id), {})
            for fmt in ("short", "deep"):
                if entry.get(fmt, {}).get("file_id"):
                    await query.answer()
                    label = "~8-12 хв" if fmt == "short" else "~15-20 хв"
                    caption = f"*{item['title']}*\n_{label} • Curriculum #{item['id']}_\n\n{item['why']}"
                    await query.message.reply_audio(audio=entry[fmt]["file_id"], caption=caption, parse_mode="Markdown")
                    return
            await query.edit_message_text(f"🎙️ *{item['title']}*\n\nГенерую подкаст... займе ~1-2 хв", parse_mode="Markdown")
            import asyncio
            asyncio.create_task(self._generate_podcast_for_item(query, item))

        elif action == "cur_podcast_play":
            item_id = int(parts[1])
            fmt = parts[2] if len(parts) > 2 else "short"
            item = next((i for i in all_topics if i["id"] == item_id), None)
            if not item: return
            ps = self._load_podcast_state()
            file_id = ps.get(str(item_id), {}).get(fmt, {}).get("file_id")
            if not file_id:
                await query.answer("Подкаст не знайдено", show_alert=True)
                return
            await query.answer()
            label = "~8-12 хв" if fmt == "short" else "~15-20 хв"
            caption = f"*{item['title']}*\n_{label} • Curriculum #{item['id']}_\n\n{item['why']}"
            await query.message.reply_audio(audio=file_id, caption=caption, parse_mode="Markdown")

        elif action in ("cur_podcast_short", "cur_podcast_deep"):
            item_id = int(parts[1])
            fmt = "short" if action == "cur_podcast_short" else "deep"
            item = next((i for i in all_topics if i["id"] == item_id), None)
            if not item: return
            await query.edit_message_text(f"🎙️ *{item['title']}*\n\nГенерую {fmt} подкаст... займе ~1-2 хв", parse_mode="Markdown")
            import asyncio
            asyncio.create_task(self._generate_podcast_for_item(query, item, fmt=fmt))

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
            import asyncio

            asyncio.create_task(self._run_all_formats_task(
                bot=query.get_bot(),
                chat_id=query.message.chat_id,
                item=item,
                selected=selected,
                data_dir=self.data_dir,
            ))
