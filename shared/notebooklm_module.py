"""
shared/notebooklm_module.py — інтеграція з NotebookLM (спільна для Sam і Garcia).
"""
import asyncio
import json
import logging
from pathlib import Path

log = logging.getLogger("shared.notebooklm")

NOTEBOOKLM_BIN = Path("/home/sashok/.openclaw/workspace/sam/venv/bin/notebooklm")
NOTEBOOKLM_BASE_URL = "https://notebooklm.google.com/notebook/"

FORMAT_NAMES = {
    "video": "🎬 Відео",
    "podcast": "🎙️ Подкаст",
    "audio": "🎤 Монолог",
    "study": "📋 Study guide",
    "briefing": "📄 Briefing",
}


def _nb_state_path(data_dir: Path) -> Path:
    return data_dir / "notebooklm_notebooks.json"


def load_nb_state(data_dir: Path) -> dict:
    p = _nb_state_path(data_dir)
    return json.loads(p.read_text()) if p.exists() else {}


def save_nb_state(state: dict, data_dir: Path):
    _nb_state_path(data_dir).write_text(json.dumps(state, ensure_ascii=False, indent=2))


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


async def get_or_create_notebook(topic_id: int, topic_title: str, data_dir: Path) -> str | None:
    state = load_nb_state(data_dir)
    key = str(topic_id)
    if key in state:
        log.info(f"Reusing notebook {state[key]} for topic {topic_id}")
        return state[key]
    rc, stdout, stderr = await _run(["create", f"AGENT | {topic_title}"])
    if rc != 0:
        log.error(f"Create notebook failed: {stderr}")
        return None
    for line in stdout.splitlines():
        if "Created notebook:" in line:
            notebook_id = line.split(":", 1)[-1].strip().split(" ")[0].strip()
            state[key] = notebook_id
            save_nb_state(state, data_dir)
            log.info(f"Created notebook {notebook_id}")
            return notebook_id
    log.error(f"Could not parse notebook ID: {stdout}")
    return None


async def cmd_notebooks(update, context, data_dir: Path, curriculum: list):
    state = load_nb_state(data_dir)
    if not state:
        await update.message.reply_text("Ще немає жодного notebook. Створи через /cur → тема → NotebookLM.")
        return
    topic_map = {str(i["id"]): i["title"] for i in curriculum}
    lines = ["📓 *Твої NotebookLM notebooks:*\n"]
    for topic_id, notebook_id in state.items():
        title = topic_map.get(topic_id, f"Тема {topic_id}")
        lines.append(f"• [{title}]({notebook_url(notebook_id)})")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)


async def generate_and_notify(
    bot, chat_id: int, topic_id: int, topic_title: str,
    source_url: str, fmt: str, instructions: str,
    skip_source: bool = False, data_dir: Path = None,
) -> None:
    format_name = FORMAT_NAMES.get(fmt, fmt)
    try:
        notebook_id = await get_or_create_notebook(topic_id, topic_title, data_dir)
        if not notebook_id:
            await bot.send_message(chat_id, "❌ Не вдалось створити notebook.")
            return
        nb_url = notebook_url(notebook_id)
        if not skip_source:
            rc, stdout, stderr = await _run(["source", "add", "-n", notebook_id, source_url])
            if rc != 0:
                log.error(f"Add source failed: {stderr}")
                await bot.send_message(chat_id, "❌ Не вдалось додати джерело.")
                return
        format_cmd = {
            "video":       ["generate", "video", "-n", notebook_id, "--wait"],
            "podcast":     ["generate", "audio", "-n", notebook_id, "--wait"],
            "audio":       ["generate", "audio", "-n", notebook_id, "--wait"],
            "study":       ["generate", "report", "-n", notebook_id, "--format", "study-guide", "--wait"],
            "briefing":    ["generate", "report", "-n", notebook_id, "--format", "briefing-doc", "--wait"],
            "flashcards":  ["generate", "flashcards", "-n", notebook_id, "--wait"],
            "mindmap":     ["generate", "mind-map", "-n", notebook_id, "--wait"],
            "slides":      ["generate", "slide-deck", "-n", notebook_id, "--wait"],
            "infographic": ["generate", "infographic", "-n", notebook_id, "--wait"],
        }
        args = format_cmd.get(fmt, format_cmd["video"])
        if instructions:
            args.append(instructions)
        rc, stdout, stderr = await _run(args, timeout=1800)
        if rc == -1:
            await bot.send_message(chat_id, f"⏰ {format_name} генерується довше ніж 30 хв.\n{nb_url}")
            return
        if rc != 0 or "rate limited" in stdout.lower():
            if "rate limited" in stdout.lower():
                await bot.send_message(chat_id, f"⏳ Google rate limit — спробуй через 1-24 год.\n{nb_url}")
            else:
                await bot.send_message(chat_id, f"❌ Помилка генерації.\n{nb_url}")
            return
        await bot.send_message(chat_id, f"✅ {format_name} готове!\n\nТема: {topic_title}\n{nb_url}")
    except Exception as e:
        log.exception(f"generate_and_notify error: {e}")
        await bot.send_message(chat_id, f"❌ Помилка: {str(e)[:300]}")
