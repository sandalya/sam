"""
shared/podcast_module.py — TTS-подкасти по curriculum темах (Phase 2.4 v2-nativ).

Зміни порівняно з Phase 1:
- топіки читаються з curriculum_v2.json через curriculum
- file_id успішно згенерованого епізоду зберігається в Topic.formats.podcast_tts.url
- окремого podcasts_state.json більше не існує
- CURRICULUM клас-атрибут прибрано — не потрібен, все через v2

Публічне API (сумісне з попереднім):
- class PodcastModule(AgentBase)
- cmd_podcast(update, context)
- підкласи задають: podcast_audience, podcast_style
"""
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from shared.agent_base import AgentBase, client, MODEL_SMART
from curriculum import load, save, set_format_status
from curriculum.models import Topic

log = logging.getLogger("core.podcast_module")


def _openai_client():
    from openai import OpenAI
    return OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

WORD_COUNT = {"short": 1400, "deep": 2800}
FORMAT_LABEL = {"short": "~8-12 хв", "deep": "~15-20 хв"}

CURRICULUM_FILENAME = "curriculum.json"

SCRIPT_SYSTEM = (
    "Ти — сценарист освітніх подкастів. Пишеш скрипт для аудіо — без заголовків, без markdown, "
    "без списків з тире/цифрами. Тільки суцільний текст, який приємно слухати. "
    "Природні паузи позначай трьома крапками (...). "
    "Мова — англійська, стиль — розумний але розмовний, як хороший технічний подкаст."
)


def _adaptive_format(topic: Topic) -> str:
    """Визначає формат на основі розміру контенту теми."""
    size = len(topic.why or "") + len(topic.do or "") + len(topic.title or "")
    return "deep" if size > 300 else "short"


class PodcastModule(AgentBase):
    """
    Підкласи задають:
      podcast_audience: str   — хто слухач (для промпту)
      podcast_style: str      — стиль/контекст
    """
    podcast_audience: str = ""
    podcast_style: str = ""

    # ── v2 curriculum accessors ──────────────────────────────────────────────

    def _curriculum_path(self) -> Path:
        return self.data_dir / CURRICULUM_FILENAME

    def _current_topic(self) -> Optional[Topic]:
        """Перша тема з state="active"."""
        state = load(self._curriculum_path())
        for t in state.topics:
            if t.state == "active":
                return t
        return None

    def _resolve_topic(self, arg: str) -> Optional[Topic]:
        """
        Приймає str id (agent_architecture-3) або legacy int ("2").
        Повертає Topic з v2 curriculum.
        """
        state = load(self._curriculum_path())
        # пряме співпадіння за v2 id
        t = state.get_topic(arg)
        if t:
            return t
        # legacy int
        if arg.isdigit():
            lid = int(arg)
            return next((t for t in state.topics if t.legacy_id == lid), None)
        return None

    # ── Generation (script + TTS) ────────────────────────────────────────────

    def _generate_script(self, topic: Topic, fmt: str) -> str:
        words = WORD_COUNT[fmt]
        if fmt == "short":
            depth = (
                "Cover the core idea clearly, give 2-3 concrete examples, and end with a practical takeaway. "
                "Keep it focused — one main insight the listener will remember."
            )
        else:
            depth = (
                "Go deep. Explain thoroughly, cover edge cases and tradeoffs, use analogies, "
                "discuss architectural decisions, give multiple real-world examples."
            )
        prompt = (
            f"Write a podcast episode script about: {topic.title}\n\n"
            f"Context: {topic.why}\n\n"
            f"Target length: ~{words} words.\n\n"
            f"{depth}\n\n"
            f"Audience: {self.podcast_audience}\n"
            f"Style context: {self.podcast_style}\n\n"
            "Start directly with content — no intro music cues, no 'Welcome to the podcast'. "
            "Just dive in naturally."
        )
        response = client.messages.create(
            model=MODEL_SMART,
            max_tokens=4096,
            system=[{"type": "text", "text": SCRIPT_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
        )
        return "\n".join(b.text for b in response.content if b.type == "text")

    def _tts(self, script: str) -> Path:
        oc = _openai_client()
        chunk_size = 4000
        chunks = [script[i:i + chunk_size] for i in range(0, len(script), chunk_size)]
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False, dir="/tmp")
        tmp.close()
        out_path = Path(tmp.name)
        if len(chunks) == 1:
            response = oc.audio.speech.create(model="tts-1", voice="onyx", input=chunks[0])
            response.stream_to_file(out_path)
            return out_path
        audio_bytes = b""
        for chunk in chunks:
            resp = oc.audio.speech.create(model="tts-1", voice="onyx", input=chunk)
            audio_bytes += resp.read()
        out_path.write_bytes(audio_bytes)
        return out_path

    def _persist_file_id(self, topic_id: str, file_id: str) -> None:
        """Зберігає Telegram file_id в Topic.formats.podcast_tts."""
        cur_path = self._curriculum_path()
        state = load(cur_path)
        set_format_status(state, topic_id, "podcast_tts", "ready", url=file_id)
        save(state, cur_path)
        log.info(f"Persisted podcast_tts file_id for {topic_id}")

    # ── /podcast handler ─────────────────────────────────────────────────────

    async def cmd_podcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        args = context.args or []
        topic_arg: Optional[str] = None
        fmt = "short"
        for arg in args:
            if arg.lower() == "deep":
                fmt = "deep"
            elif arg.lower() == "short":
                fmt = "short"
            elif topic_arg is None:
                topic_arg = arg

        # 1. resolve топік
        if topic_arg:
            topic = self._resolve_topic(topic_arg)
            if not topic:
                await update.message.reply_text(
                    f"Тема {topic_arg!r} не існує. "
                    f"Використай /cur щоб побачити список."
                )
                return
        else:
            topic = self._current_topic()
            if not topic:
                await update.message.reply_text(
                    "Немає активної теми. Вкажи: /podcast <topic_id>\n"
                    "Наприклад: /podcast agent_architecture-1  або  /podcast 1"
                )
                return

        # 2. якщо вже є готовий TTS — send_audio по file_id
        existing = topic.formats.get("podcast_tts")
        if existing and existing.status == "ready" and existing.url:
            caption = (
                f"*{topic.title}*\n"
                f"_Збережений раніше епізод_\n\n"
                f"{topic.why}"
            )
            try:
                await update.message.reply_audio(
                    audio=existing.url,
                    title=topic.title,
                    performer="Podcast",
                    caption=caption,
                    parse_mode="Markdown",
                )
                return
            except Exception as e:
                log.warning(f"Failed to resend by file_id for {topic.id}: {e}; will regenerate")

        # 3. інакше — згенерувати новий
        label = FORMAT_LABEL[fmt]
        await update.message.reply_text(
            f"Генерую епізод...\n\nТема: *{topic.title}*\nФормат: {label}\n\nЗайме ~1-2 хв",
            parse_mode="Markdown",
        )
        # mark as generating
        cur_path = self._curriculum_path()
        state = load(cur_path)
        set_format_status(state, topic.id, "podcast_tts", "generating")
        save(state, cur_path)

        mp3_path: Optional[Path] = None
        try:
            script = self._generate_script(topic, fmt)
            mp3_path = self._tts(script)
            caption = (
                f"*{topic.title}*\n"
                f"_{label} • {topic.id}_\n\n"
                f"{topic.why}"
            )
            with open(mp3_path, "rb") as f:
                msg = await update.message.reply_audio(
                    audio=f,
                    title=topic.title,
                    performer="Podcast",
                    caption=caption,
                    parse_mode="Markdown",
                )
            # зберегти file_id
            file_id = msg.audio.file_id if msg.audio else None
            if file_id:
                self._persist_file_id(topic.id, file_id)
            else:
                log.warning(f"reply_audio returned no audio.file_id for {topic.id}")
                state = load(cur_path)
                set_format_status(state, topic.id, "podcast_tts", "ready")
                save(state, cur_path)
        except Exception as e:
            log.error(f"Podcast failed for {topic.id}: {e}", exc_info=True)
            state = load(cur_path)
            set_format_status(state, topic.id, "podcast_tts", "failed", error=str(e)[:200])
            save(state, cur_path)
            await update.message.reply_text(f"Помилка генерації: {e}")
        finally:
            if mp3_path:
                mp3_path.unlink(missing_ok=True)
