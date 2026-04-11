"""
Модуль podcast — генерує аудіо-епізоди по curriculum темах.
Команди:
  /podcast        — стандартний епізод (~10-15 хв) по поточній темі
  /podcast deep   — глибокий епізод (~20-25 хв)
  /podcast 3      — по конкретній темі (номер)
  /podcast 3 deep — конкретна тема + глибокий
"""
import logging
import os
import tempfile
from pathlib import Path

from openai import OpenAI
from telegram import Update
from telegram.ext import ContextTypes

from .base import DATA_DIR, client, MODEL_SMART, SAM_PERSONA
from .curriculum import CURRICULUM, load_state

log = logging.getLogger("sam.podcast")

openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

WORD_COUNT = {"short": 1400, "deep": 2800}
FORMAT_LABEL = {"short": "10-15 хв", "deep": "20-25 хв"}

SCRIPT_SYSTEM = (
    "Ти — сценарист освітніх подкастів. Пишеш скрипт для аудіо — без заголовків, без markdown, "
    "без списків з тире/цифрами. Тільки суцільний текст, який приємно слухати. "
    "Природні паузи позначай трьома крапками (...). "
    "Мова — англійська, стиль — розумний але розмовний, як хороший технічний подкаст. "
    "Слухач — досвідчений Python-розробник що будує AI-агентів, вже знає основи."
)


def _current_topic():
    state = load_state()
    for item in CURRICULUM:
        if item["id"] not in state["completed"]:
            return item
    return None


def _generate_script(item: dict, fmt: str) -> str:
    words = WORD_COUNT[fmt]
    if fmt == "short":
        depth = (
            "Cover the core idea clearly, give 2-3 concrete examples, and end with a practical takeaway. "
            "Keep it focused — one main insight the listener will remember."
        )
    else:
        depth = (
            "Go deep. Explain the concept thoroughly, cover edge cases and tradeoffs, "
            "use analogies, discuss architectural decisions, and give multiple real-world examples. "
            "The listener has 20+ minutes and wants to really understand this."
        )

    prompt = (
        f"Write a podcast episode script about: {item['title']}\n\n"
        f"Context about this topic: {item['why']}\n\n"
        f"Target length: approximately {words} words.\n\n"
        f"{depth}\n\n"
        "The listener is building Telegram bots and AI agents with Python + Anthropic API. "
        "Reference practical scenarios they would recognize — things like tool use in bots, "
        "managing agent state, prompt design, etc.\n\n"
        "Start directly with the content — no intro music cues, no Welcome to the podcast. "
        "Just dive in naturally, like picking up a conversation."
    )

    response = client.messages.create(
        model=MODEL_SMART,
        max_tokens=4096,
        system=[{"type": "text", "text": SCRIPT_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
    )
    return "\n".join(b.text for b in response.content if b.type == "text")


def _tts(script: str) -> Path:
    chunk_size = 4000
    chunks = [script[i:i + chunk_size] for i in range(0, len(script), chunk_size)]

    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False, dir="/tmp")
    tmp.close()
    out_path = Path(tmp.name)

    if len(chunks) == 1:
        response = openai_client.audio.speech.create(
            model="tts-1",
            voice="onyx",
            input=chunks[0],
        )
        response.stream_to_file(out_path)
        return out_path

    audio_bytes = b""
    for chunk in chunks:
        resp = openai_client.audio.speech.create(
            model="tts-1",
            voice="onyx",
            input=chunk,
        )
        audio_bytes += resp.read()

    out_path.write_bytes(audio_bytes)
    return out_path


async def cmd_podcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    topic_id = None
    fmt = "short"

    for arg in args:
        if arg.isdigit():
            topic_id = int(arg)
        elif arg.lower() == "deep":
            fmt = "deep"

    if topic_id:
        item = next((i for i in CURRICULUM if i["id"] == topic_id), None)
        if not item:
            await update.message.reply_text(f"Тема {topic_id} не існує. Доступні: 1-{len(CURRICULUM)}")
            return
    else:
        item = _current_topic()
        if not item:
            await update.message.reply_text("Весь curriculum пройдено! Вкажи номер теми: /podcast 1")
            return

    label = FORMAT_LABEL[fmt]
    await update.message.reply_text(
        f"Генерую епізод...\n\nТема: *{item['title']}*\nФормат: {label}\n\nЗайме ~1-2 хв",
        parse_mode="Markdown",
    )

    try:
        log.info(f"Generating podcast: topic={item['id']} fmt={fmt}")
        script = _generate_script(item, fmt)
        log.info(f"Script generated: {len(script)} chars")

        mp3_path = _tts(script)
        log.info(f"TTS done: {mp3_path}")

        caption = (
            f"*{item['title']}*\n"
            f"_{label} • AI Curriculum #{item['id']}_\n\n"
            f"{item['why']}"
        )

        with open(mp3_path, "rb") as f:
            await update.message.reply_audio(
                audio=f,
                title=item["title"],
                performer="Sam Podcast",
                caption=caption,
                parse_mode="Markdown",
            )

        mp3_path.unlink(missing_ok=True)

    except Exception as e:
        log.error(f"Podcast generation failed: {e}", exc_info=True)
        await update.message.reply_text(f"Помилка генерації: {e}")
