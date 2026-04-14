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
    p = _nb_state_path(data_dir)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    tmp.rename(p)


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


async def get_or_create_notebook(topic_id: int, topic_title: str, data_dir: Path, category: str = "AGENT") -> str | None:
    state = load_nb_state(data_dir)
    key = str(topic_id)
    if key in state:
        nb_id = state[key]["notebook_id"] if isinstance(state[key], dict) else state[key]
        log.info(f"Reusing notebook {nb_id} for topic {topic_id}")
        return nb_id
    notebook_name = f"{category} — {topic_title}"
    rc, stdout, stderr = await _run(["create", notebook_name])
    if rc != 0:
        log.error(f"Create notebook failed: {stderr}")
        return None
    for line in stdout.splitlines():
        if "Created notebook:" in line:
            notebook_id = line.split(":", 1)[-1].strip().split(" ")[0].strip()
            state[key] = {"notebook_id": notebook_id, "generated": []}
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
    for topic_id, entry in state.items():
        nb_id = entry["notebook_id"] if isinstance(entry, dict) else entry
        title = topic_map.get(topic_id, f"Тема {topic_id}")
        generated = entry.get("generated", []) if isinstance(entry, dict) else []
        icons = " ".join(FORMAT_NAMES.get(f, f) for f in generated) if generated else "—"
        lines.append(f"• [{title}]({notebook_url(nb_id)}) {icons}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)


async def generate_fmt(
    notebook_id: str, fmt: str, instructions: str,
    topic_id: int, data_dir: Path,
) -> tuple[bool, str]:
    """Генерує один формат. Повертає (ok, error_type).
    error_type: "" | "rate_limit" | "timeout" | "error"
    """
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
    args = list(format_cmd.get(fmt, format_cmd["video"]))
    if instructions:
        args.append(instructions)
    rc, stdout, stderr = await _run(args, timeout=1800)
    if rc == -1:
        return False, "timeout"
    if "rate limited" in stdout.lower():
        return False, "rate_limit"
    if rc == 1 and "Generating" in stdout:
        # Генерація запустилась але впала на стороні Google — варто ретраїти
        log.error(f"Generate {fmt} failed rc={rc}: {stdout[:200]}")
        return False, "rate_limit"
    if rc != 0:
        log.error(f"Generate {fmt} failed rc={rc}: {stdout[:200]}")
        return False, "error"
    state = load_nb_state(data_dir)
    key = str(topic_id)
    if key in state and isinstance(state[key], dict):
        if fmt not in state[key]["generated"]:
            state[key]["generated"].append(fmt)
            save_nb_state(state, data_dir)
    return True, ""


async def generate_and_notify(
    bot, chat_id: int, topic_id: int, topic_title: str,
    source_url: str, fmt: str, instructions: str,
    skip_source: bool = False, data_dir: Path = None,
) -> None:
    """Compat wrapper для виклику з одним форматом."""
    import asyncio as _asyncio
    notebook_id = await get_or_create_notebook(topic_id, topic_title, data_dir)
    if not notebook_id:
        await bot.send_message(chat_id, "❌ Не вдалось створити notebook.")
        return
    nb_url = notebook_url(notebook_id)
    if not skip_source:
        rc, stdout, stderr = await _run(["source", "add", "-n", notebook_id, source_url])
        if rc != 0:
            log.warning(f"Add source warning (ignored): {stderr}")
    RETRY_DELAYS = [0, 15 * 60, 30 * 60]
    ok, err = False, "error"
    for delay in RETRY_DELAYS:
        if delay:
            log.info(f"Retry {fmt} after {delay}s")
            await _asyncio.sleep(delay)
        ok, err = await generate_fmt(notebook_id, fmt, instructions, topic_id, data_dir)
        if ok or err != "rate_limit":
            break
    format_name = FORMAT_NAMES.get(fmt, fmt)
    if ok:
        await bot.send_message(chat_id, f"✅ {format_name} готове!\n\nТема: {topic_title}\n{nb_url}")
    elif err == "rate_limit":
        await bot.send_message(chat_id, f"⏳ Google rate limit — спробуй через кілька годин.\n{nb_url}")
    elif err == "timeout":
        await bot.send_message(chat_id, f"⏰ {format_name} генерується надто довго.\n{nb_url}")
    else:
        await bot.send_message(chat_id, f"❌ Помилка генерації {format_name}.\n{nb_url}")
