"""
shared/agent_base.py — базовий клас для Sam і Garcia (і майбутніх навчальних агентів).
Містить: Claude client, profile I/O, call_claude, parse_json_response.
"""
import json
from datetime import datetime
import os
from pathlib import Path

import anthropic

from .memory_store import MemoryStore
from .conversation_store import ConversationStore

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MODEL_SMART = "claude-sonnet-4-20250514"
MODEL_FAST  = "claude-haiku-4-5-20251001"

ANTI_HALLUCINATION_RULE = """
⚠️ КРИТИЧНЕ ПРАВИЛО — ЧЕСНІСТЬ:
- Ніколи не вигадуй імена людей, назви компаній, URL, статистику, рейтинги, відгуки.
- Якщо не знаєш точної відповіді — скажи прямо: «Не маю перевіреної інформації про це».
- Краще визнати незнання ніж дати неправдиву відповідь.
- Якщо є web search — використовуй його для перевірки фактів.
- Посилання: давай ТІЛЬКИ прямі URL конкретного профілю/сторінки. Загальні каталоги (типу /hire/...) — не давай.
- Якщо просять список профайлів/людей/компаній з посиланнями — включай ТІЛЬКИ тих для кого знайшла пряме посилання. Немає посилання = людина не потрапляє в список. Краще 2 реальних ніж 5 з порожніми.
"""


class AgentBase:
    """
    Базовий клас. Агент успадковує і задає:
      - self.owner_chat_id
      - self.persona  (str — системний промпт)
      - self.data_dir (Path — куди зберігати дані)
      - self.profile_path (Path — profile.json)
    """

    def __init__(self, owner_chat_id: int, persona: str, data_dir: Path, profile_path: Path):
        self.owner_chat_id = owner_chat_id
        self.persona = persona
        self.data_dir = data_dir
        self.profile_path = profile_path
        self.data_dir.mkdir(exist_ok=True)
        self.memory = MemoryStore(data_dir)
        self.conversation = ConversationStore(data_dir)

    # ── Profile ────────────────────────────────────────────────────────────────

    def load_profile(self) -> dict:
        if self.profile_path.exists():
            data = json.loads(self.profile_path.read_text())
            data.setdefault("interests", [])
            data.setdefault("curriculum_hints", [])
            return data
        return {"scores": {}, "notes": [], "interests": [], "curriculum_hints": []}

    def save_profile(self, profile: dict):
        self.profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2))

    def update_score(self, topic_key: str, delta: int):
        profile = self.load_profile()
        profile["scores"][topic_key] = profile["scores"].get(topic_key, 0) + delta
        self.save_profile(profile)

    def update_interests(self, new_interests: list[str]):
        if not new_interests:
            return
        profile = self.load_profile()
        existing = set(i.lower() for i in profile["interests"])
        for item in new_interests:
            if item.lower() not in existing:
                profile["interests"].append(item)
                existing.add(item.lower())
        self.save_profile(profile)

    def add_note(self, note: str):
        profile = self.load_profile()
        profile["notes"].append(note)
        self.save_profile(profile)

    def profile_to_context(self) -> str:
        profile = self.load_profile()
        if not profile.get("scores") and not profile.get("notes"):
            return ""
        lines = ["Профіль інтересів користувача (враховуй при підборі новин):"]
        if profile["scores"]:
            sorted_t = sorted(profile["scores"].items(), key=lambda x: x[1], reverse=True)
            top = [t for t, s in sorted_t if s > 0]
            low = [t for t, s in sorted_t if s < 0]
            if top:
                lines.append(f"Подобається: {', '.join(top[:5])}")
            if low:
                lines.append(f"Не цікаво: {', '.join(low[:5])}")
        if profile.get("notes"):
            lines.append(f"Побажання: {'; '.join(profile['notes'][-5:])}")
        return "\n".join(lines)

    def _build_context_snapshot(self) -> str:
        """Живий стан користувача для системного промпту."""
        lines = []

        # Поточна дата і час
        now = datetime.now()
        lines.append(f"📅 Зараз: {now.strftime('%A, %d %B %Y, %H:%M')}")

        # Стан curriculum якщо є
        curriculum_path = self.data_dir / "curriculum.json"
        curriculum_list = getattr(self, "CURRICULUM", [])
        if curriculum_path.exists():
            try:
                import json as _j
                cur = _j.loads(curriculum_path.read_text())
                started = cur.get("started", [])
                completed = cur.get("completed", [])

                def topic_name(tid):
                    if curriculum_list:
                        t = next((t for t in curriculum_list if t["id"] == tid), None)
                        return f"{tid}. {t['title']}" if t else str(tid)
                    return str(tid)

                if started:
                    names = [topic_name(i) for i in started]
                    lines.append(f"📚 Зараз вивчає: {', '.join(names)}")
                if completed:
                    names = [topic_name(i) for i in completed]
                    lines.append(f"✅ Завершено: {', '.join(names)}")
                if not started and not completed:
                    lines.append("📚 Curriculum: ще не починав")
            except Exception:
                pass

        # Остання розмова
        conv = self.conversation.load()
        if conv:
            last = conv[-1]
            lines.append(f"💬 Остання активність: {last.get('time','?')} ({last['role']})")
        else:
            lines.append("💬 Це перша розмова")

        # Читаємо SESSION.md від Кота якщо є
        session_path = Path.home() / ".openclaw/workspace/sam/SESSION.md"
        if not session_path.exists():
            session_path = self.data_dir.parent / "SESSION.md"
        if session_path.exists():
            try:
                session = session_path.read_text(encoding="utf-8").strip()
                if session:
                    lines.append(f"\n📋 Остання сесія розробки (від Кота):\n{session[:500]}")
            except Exception:
                pass

        return "\n".join(lines)

    # ── Claude API ─────────────────────────────────────────────────────────────

    def _build_system(self, include_memory: bool = True, include_conversation: bool = False) -> str:
        """Збирає повний системний промпт: persona + anti-hallucination + пам'ять + стан."""
        parts = [self.persona, ANTI_HALLUCINATION_RULE]
        if include_memory:
            mem_ctx = self.memory.to_context()
            if mem_ctx:
                parts.append(mem_ctx)
        if include_conversation:
            conv_ctx = self.conversation.to_context_string()
            if conv_ctx:
                parts.append(conv_ctx)
        # Завжди додаємо живий стан
        snapshot = self._build_context_snapshot()
        if snapshot:
            parts.append(snapshot)
        return "\n\n".join(parts)

    def call_claude_with_search(self, prompt: str, max_tokens: int = 2000) -> str:
        response = client.messages.create(
            model=MODEL_SMART,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": self._build_system(), "cache_control": {"type": "ephemeral"}}],
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )
        return "\n".join(b.text for b in response.content if b.type == "text")

    def call_claude(self, prompt: str, max_tokens: int = 1024, smart: bool = False) -> str:
        model = MODEL_SMART if smart else MODEL_FAST
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": self._build_system(), "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
        )
        return "\n".join(b.text for b in response.content if b.type == "text")

    def _is_personal_question(self, text: str) -> bool:
        """Чи питання стосується особистого стану — curriculum, прогрес, профіль тощо."""
        personal_keywords = [
            "curriculum", "курікулум", "план навчання", "де я", "мій прогрес",
            "що я вивчаю", "що вивчаю", "моя тема", "мій профіль", "profile",
            "що далі", "наступна тема", "скільки я", "мої нотатки", "що знаю",
        ]
        low = text.lower()
        return any(kw in low for kw in personal_keywords)

    def call_claude_chat(self, user_message: str, max_tokens: int = 1024) -> str:
        """Чат з пам'яттю розмови. Пошук тільки для зовнішніх питань."""
        self.conversation.add("user", user_message)

        system = self._build_system(include_memory=True, include_conversation=False)
        history = self.conversation.to_messages()[:-1]
        messages = history + [{"role": "user", "content": user_message}]

        use_search = not self._is_personal_question(user_message)

        try:
            kwargs = dict(
                model=MODEL_SMART,
                max_tokens=max_tokens,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=messages,
            )
            if use_search:
                kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search"}]
            response = client.messages.create(**kwargs)
            texts = [b.text for b in response.content if b.type == "text"]
            answer = texts[-1] if texts else ""
        except Exception:
            response = client.messages.create(
                model=MODEL_SMART,
                max_tokens=max_tokens,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=messages,
            )
            answer = "\n".join(b.text for b in response.content if b.type == "text")

        if answer:
            # Проактивна підказка (раз на день)
            answer = self._maybe_proactive_hint(user_message, answer)
            # Зберігаємо відповідь агента
            self.conversation.add("assistant", answer)
            # Асинхронно витягуємо важливі факти в довгострокову пам'ять
            import threading
            threading.Thread(
                target=self._extract_and_save_memory,
                args=(user_message, answer),
                daemon=True,
            ).start()
        return answer

    def call_claude_profiles(self, query: str, platform: str = "Upwork", max_tokens: int = 2000) -> str:
        """Пошук профайлів з реальними URL. Фільтрація на рівні коду."""
        import re as _re, json as _json

        search_prompt = (
            f"Знайди реальних фрілансерів/артистів на {platform} за запитом: {query}\n\n"
            f"Поверни результат ТІЛЬКИ у форматі JSON масиву. \n"
            "Критично важливо: включай профіль ТІЛЬКИ якщо знайшов пряме посилання на профіль (\"profile_url\"). Не вигадуй URL.\n"
            '[{"name": "...", "profile_url": "https://...", "specialty": "...", "rate": "...", "rating": "...", "portfolio_url": "..."}]\n'
            "Якщо не знайшов прямого profile_url — залиш profile_url порожнім (\"\"). Не давай каталоги."
        )

        raw = self.call_claude_with_search(search_prompt, max_tokens=max_tokens)

        # Фільтруємо на рівні коду
        try:
            match = _re.search(r'\[.*\]', raw, _re.DOTALL)
            if match:
                profiles = _json.loads(match.group())
                # залишаємо тільки тих для кого є прямий URL профілю (не каталог)
                def is_direct_profile(url: str) -> bool:
                    if not url or not url.startswith("http"):
                        return False
                    skip = ["/hire/", "/search/", "/o/", "/catalog/", "?q="]
                    return not any(s in url for s in skip)

                valid = [p for p in profiles if is_direct_profile(p.get("profile_url", ""))]

                if not valid:
                    return "🔍 Пошук не дав результатів з прямими посиланнями. Спробуй запитати інакше: наприклад \"botanical packaging designer site:upwork.com\"."

                # Форматуємо остаточну відповідь
                format_prompt = (
                    f"Оформи цей список профайлів як пораду для Ксюші. Збережи всі URL. Одне повідомлення, без markdown-заголовків другого рівня.\n\n"
                    f"Знайшло {len(valid)} профайлів з прямими посиланнями:\n"
                    + _json.dumps(valid, ensure_ascii=False, indent=2)
                )
                return self.call_claude(format_prompt, max_tokens=1500, smart=True)
        except Exception:
            pass

        return "🔍 Не вдалось знайти профайли з перевіреними посиланнями. Upwork погано індексується — спробуй пошукати вручну: https://www.upwork.com/search/profiles/?q=botanical+packaging"


    def _maybe_proactive_hint(self, user_message: str, answer: str) -> str:
        """Додає проактивну підказку раз на день якщо є тригер."""
        import random
        from datetime import date

        # Перевіряємо чи вже була підказка сьогодні
        hint_path = self.data_dir / "last_hint.txt"
        today = str(date.today())
        if hint_path.exists() and hint_path.read_text().strip() == today:
            return answer

        # Тригери
        curriculum_path = self.data_dir / "curriculum.json"
        if not curriculum_path.exists():
            return answer

        import json as _j
        cur = _j.loads(curriculum_path.read_text())
        started = cur.get("started", [])
        if not started:
            return answer

        curriculum_list = getattr(self, "CURRICULUM", [])
        current_topic = next((t for t in curriculum_list if t["id"] == started[0]), None)

        # Перевіряємо тригери
        topic_related = False
        if current_topic:
            keywords = current_topic.get("title", "").lower().split()
            msg_low = user_message.lower()
            topic_related = any(kw in msg_low for kw in keywords if len(kw) > 3)

        random_trigger = random.random() < 0.20

        if not topic_related and not random_trigger:
            return answer

        # Генеруємо підказку
        topic_info = ""
        if current_topic:
            topic_info = (
                f"Поточна тема: {current_topic['title']}\n"
                f"Завдання: {current_topic.get('do', '')}\n"
                f"Чому важливо: {current_topic.get('why', '')}"
            )

        hint_prompt = (
            f"Користувач написав: {user_message[:200]}\n"
            f"Твоя відповідь: {answer[:300]}\n\n"
            f"{topic_info}\n\n"
            "Додай ОДНЕ коротке речення-підказку в кінці відповіді (через \n\n) "
            "що природно пов'язує розмову з поточною темою навчання або нагадує про практичне завдання. "
            "Стиль Сема — коротко, без пафосу. "
            "Якщо зв'язок натягнутий — краще нічого не додавай, поверни порожній рядок."
        )

        try:
            hint = self.call_claude(hint_prompt, max_tokens=150, smart=False).strip()
            if hint:
                hint_path.write_text(today)
                return answer + "\n\n" + hint
        except Exception:
            pass

        return answer

    def _extract_and_save_memory(self, user_message: str, assistant_answer: str):
        """Витягує важливі факти з розмови і зберігає в довгострокову пам'ять."""
        try:
            prompt = (
                f"Користувач написав: {user_message}\n"
                f"Асистент відповів: {assistant_answer}\n\n"
                "Витягни ТІЛЬКИ нові конкретні факти про користувача які варто запам'ятати надовго.\n"
                "Зберігай ТІЛЬКИ:\n"
                "- конкретні проекти (назва, деталі, технології)\n"
                "- реальні цілі і плани (конкретні, не загальні)\n"
                "- стійкі уподобання (не те що очевидно з контексту)\n"
                "- важливі факти про роботу/навички\n"
                "НЕ зберігай:\n"
                "- що користувач навчається AI (це очевидно)\n"
                "- що використовує curriculum (це очевидно)\n"
                "- загальні спостереження типу 'цікавиться деталями'\n"
                "- дублікати того що вже могло бути збережено\n"
                "- факти про поведінку бота або команди\n"
                "Якщо нічого конкретного і нового — повертай порожній масив.\n"
                "Відповідь ТІЛЬКИ JSON:\n"
                '[{"fact": "...", "category": "goals|style|projects|preferences|skills"}]'
            )
            raw = self.call_claude(prompt, max_tokens=512, smart=True)
            import re, json as _json
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if not match:
                return
            facts = _json.loads(match.group())
            for item in facts:
                if isinstance(item, dict) and item.get("fact"):
                    self.memory.add(item["fact"], item.get("category", "general"))
        except Exception as e:
            import logging
            logging.getLogger("shared.agent_base").warning(f"Memory extraction failed: {e}")

    def parse_json_response(self, raw: str):
        """Parse JSON from Claude response. Returns list or dict depending on content."""
        import re, json as _json
        clean = raw.strip()
        if clean.startswith("```"):
            parts = clean.split("```")
            clean = parts[1] if len(parts) > 1 else clean
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip()
        try:
            result = _json.loads(clean)
            return result  # повертаємо як є — list або dict
        except _json.JSONDecodeError:
            # спробуємо знайти dict
            match = re.search(r'\{.*\}', clean, re.DOTALL)
            if match:
                try:
                    return _json.loads(match.group())
                except Exception:
                    pass
            # спробуємо знайти list
            match = re.search(r'\[.*\]', clean, re.DOTALL)
            if match:
                try:
                    return _json.loads(match.group())
                except Exception:
                    pass
        return []
