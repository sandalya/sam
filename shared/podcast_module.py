"""
shared/podcast_module.py — генерація аудіо-подкастів по curriculum темах.
Агент задає: podcast_audience, podcast_style, curriculum, load_state.
"""
import logging
import os
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from .agent_base import AgentBase, client, MODEL_SMART

log = logging.getLogger("shared.podcast")


def _openai_client():
    from openai import OpenAI
    return OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

WORD_COUNT = {"short": 1400, "deep": 2800}
FORMAT_LABEL = {"short": "10-15 хв", "deep": "20-25 хв"}

SCRIPT_SYSTEM = (
    "Ти — сценарист освітніх подкастів. Пишеш скрипт для аудіо — без заголовків, без markdown, "
    "без списків з тире/цифрами. Тільки суцільний текст, який приємно слухати. "
    "Природні паузи позначай трьома крапками (...). "
    "Мова — англійська, стиль — розумний але розмовний, як хороший технічний подкаст."
)


class PodcastModule(AgentBase):
    """
    Підклас задає:
      podcast_audience: str   — хто слухач (для промпту)
      podcast_style: str      — стиль/контекст подкасту
      CURRICULUM: list[dict]  — список тем
      load_state: callable    — функція що повертає {"completed": [...], ...}
    """
    podcast_audience: str = ""
    podcast_style: str = ""
    CURRICULUM: list[dict] = []

    def _load_state(self) -> dict:
        p = self.data_dir / "curriculum.json"
        import json
        return json.loads(p.read_text()) if p.exists() else {"completed": [], "started": [], "notes": {}}

    def _current_topic(self) -> dict | None:
        state = self._load_state()
        for item in self.CURRICULUM:
            if item["id"] not in state["completed"]:
                return item
        return None

    def _generate_script(self, item: dict, fmt: str) -> str:
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
            f"Write a podcast episode script about: {item['title']}\n\n"
            f"Context: {item['why']}\n\n"
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

    async def cmd_podcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        args = context.args or []
        topic_id, fmt = None, "short"
        for arg in args:
            if arg.isdigit(): topic_id = int(arg)
            elif arg.lower() == "deep": fmt = "deep"

        if topic_id:
            item = next((i for i in self.CURRICULUM if i["id"] == topic_id), None)
            if not item:
                await update.message.reply_text(f"Тема {topic_id} не існує. Доступні: 1-{len(self.CURRICULUM)}")
                return
        else:
            item = self._current_topic()
            if not item:
                await update.message.reply_text("Весь curriculum пройдено! Вкажи номер: /podcast 1")
                return

        label = FORMAT_LABEL[fmt]
        await update.message.reply_text(
            f"Генерую епізод...\n\nТема: *{item['title']}*\nФормат: {label}\n\nЗайме ~1-2 хв",
            parse_mode="Markdown",
        )
        try:
            script = self._generate_script(item, fmt)
            mp3_path = self._tts(script)
            caption = (
                f"*{item['title']}*\n"
                f"_{label} • Curriculum #{item['id']}_\n\n"
                f"{item['why']}"
            )
            with open(mp3_path, "rb") as f:
                await update.message.reply_audio(
                    audio=f,
                    title=item["title"],
                    performer="Podcast",
                    caption=caption,
                    parse_mode="Markdown",
                )
            mp3_path.unlink(missing_ok=True)
        except Exception as e:
            log.error(f"Podcast failed: {e}", exc_info=True)
            await update.message.reply_text(f"Помилка генерації: {e}")
