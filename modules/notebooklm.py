"""
Модуль notebooklm — інтеграція з NotebookLM для генерації контенту.
"""
import asyncio
import json
import logging
from pathlib import Path

from .base import DATA_DIR

log = logging.getLogger("sam.notebooklm")

NB_STATE_PATH = DATA_DIR / "notebooklm_notebooks.json"
NOTEBOOKLM_BIN = Path("/home/sashok/.openclaw/workspace/sam/venv/bin/notebooklm")
NOTEBOOKLM_BASE_URL = "https://notebooklm.google.com/notebook/"

FORMAT_NAMES = {
    "video": "🎬 Відео",
    "podcast": "🎙️ Подкаст",
    "study": "📋 Study guide",
    "briefing": "📄 Briefing",
}


def load_nb_state() -> dict:
    if NB_STATE_PATH.exists():
        return json.loads(NB_STATE_PATH.read_text())
    return {}


def save_nb_state(state: dict):
    NB_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def notebook_url(notebook_id: str) -> str:
    return f"{NOTEBOOKLM_BASE_URL}{notebook_id}"


async def _run(args: list[str], timeout: int = 900) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        str(NOTEBOOKLM_BIN), *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return -1, "", "timeout"
    return proc.returncode, stdout.decode(), stderr.decode()


async def get_or_create_notebook(topic_id: int, topic_title: str) -> str | None:
    state = load_nb_state()
    key = str(topic_id)

    if key in state:
        log.info(f"Reusing notebook {state[key]} for topic {topic_id}")
        return state[key]

    rc, stdout, stderr = await _run(["create", f"SAM | {topic_title}"])
    if rc != 0:
        log.error(f"Create notebook failed: {stderr}")
        return None

    for line in stdout.splitlines():
        if "Created notebook:" in line:
            notebook_id = line.split(":", 1)[-1].strip().split(" ")[0].strip()
            state[key] = notebook_id
            save_nb_state(state)
            log.info(f"Created notebook {notebook_id}")
            return notebook_id

    log.error(f"Could not parse notebook ID: {stdout}")
    return None


async def generate_and_notify(
    bot,
    chat_id: int,
    topic_id: int,
    topic_title: str,
    source_url: str,
    fmt: str,
    instructions: str,
) -> None:
    format_name = FORMAT_NAMES.get(fmt, fmt)
    try:
        notebook_id = await get_or_create_notebook(topic_id, topic_title)
        if not notebook_id:
            await bot.send_message(chat_id, "❌ Не вдалось створити notebook.")
            return

        nb_url = notebook_url(notebook_id)

        rc, stdout, stderr = await _run(
            ["source", "add", "-n", notebook_id, source_url]
        )
        if rc != 0:
            log.error(f"Add source failed: {stderr}")
            await bot.send_message(chat_id, "❌ Не вдалось додати джерело.")
            return

        format_cmd = {
            "video":    ["generate", "video", "-n", notebook_id, "--wait"],
            "podcast":  ["generate", "audio", "-n", notebook_id, "--wait"],
            "study":    ["generate", "report", "-n", notebook_id, "--format", "study-guide", "--wait"],
            "briefing": ["generate", "report", "-n", notebook_id, "--format", "briefing-doc", "--wait"],
        }

        args = format_cmd.get(fmt, format_cmd["video"])
        if instructions:
            args.append(instructions)

        rc, stdout, stderr = await _run(args, timeout=1800)

        if rc == -1:
            await bot.send_message(
                chat_id,
                f"⏰ {format_name} генерується довше ніж 30 хв.\nПеревір сам:\n{nb_url}",
            )
            return

        if rc != 0 or "rate limited" in stdout.lower():
            log.error(f"Generate failed: rc={rc} stdout={stdout} stderr={stderr}")
            if "rate limited" in stdout.lower():
                await bot.send_message(chat_id, f"⏳ Google rate limit — спробуй через 1-24 год.\n{nb_url}")
            else:
                await bot.send_message(chat_id, f"❌ Помилка генерації.\n{nb_url}")
            return

        await bot.send_message(
            chat_id,
            f"✅ {format_name} готове!\n\nТема: {topic_title}\n{nb_url}",
        )

    except Exception as e:
        log.exception(f"generate_and_notify error: {e}")
        await bot.send_message(chat_id, f"❌ Помилка: {str(e)[:300]}")
