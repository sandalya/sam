"""
shared/notebooklm_module.py — інтеграція з NotebookLM на v2 curriculum.

Phase 2.3 redesign:
- notebook_id живе в Topic.nblm_notebook_id (merge з notebooklm_notebooks_v2.json)
- format URLs живуть в Topic.formats[fmt].url
- все через curriculum API (load/save + mutations)
- окремого файлу стану NBLM більше немає

Формати (v2 FormatKey):
- slides        — NBLM slide-deck
- podcast_nblm  — NBLM audio overview (2 ведучі)
- video         — NBLM video overview
- infographic   — NBLM infographic
- flashcards    — NBLM flashcards
- podcast_tts   — НЕ через NBLM, окремий pipeline в podcast_module (Phase 2.4)
- exam          — НЕ через NBLM, Phase 3 (Claude dialog)

Публічне API:
- get_or_create_notebook(topic_id, topic_title, data_dir) -> notebook_id | None
- generate_and_notify(bot, chat_id, topic_id, topic_title, source_url, fmt, instructions, ...)
- cmd_notebooks(update, context, data_dir) — /notebooks хендлер
- notebook_url(notebook_id) -> str
- FORMAT_NAMES — для UI (re-export з curriculum формати)
"""
import asyncio
import logging
import json
from pathlib import Path
from typing import Optional

from curriculum import (
    load, save,
    set_nblm_notebook_id, set_format_status,
    set_article_nblm_notebook_id, set_article_format_status,
    ALLOWED_FORMATS,
)

log = logging.getLogger("core.notebooklm_module")

NOTEBOOKLM_BIN = Path("/home/sashok/.openclaw/workspace/sam/venv/bin/notebooklm")
NOTEBOOKLM_BASE_URL = "https://notebooklm.google.com/notebook/"

CURRICULUM_FILENAME = "curriculum.json"

# ── UI names для форматів ─────────────────────────────────────────────────────

FORMAT_NAMES = {
    "slides":       "📊 Slides",
    "podcast_nblm": "🎙️ NBLM Podcast",
    "podcast_tts":  "🔊 TTS Podcast",
    "video":        "🎬 Video",
    "infographic":  "📈 Інфографіка",
    "flashcards":   "🃏 Флешкартки",
    "exam":         "🧠 Тест",
}

# Набір форматів які генеруються через NBLM CLI
NBLM_FORMATS = {"slides", "podcast_nblm", "video", "infographic", "flashcards"}

# v2 format key → NBLM CLI args
_NBLM_CMD_ARGS = {
    "slides":       ["generate", "slide-deck"],
    "podcast_nblm": ["generate", "audio"],
    "video":        ["generate", "video"],
    "infographic":  ["generate", "infographic"],
    "flashcards":   ["generate", "flashcards"],
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_nb_state(data_dir):
    """Legacy shim (Phase 2.3). notebook state тепер в Topic.nblm_notebook_id + Topic.formats.
    Повертає порожній dict — startup_check не знайде broken tasks, що коректно для v2.
    Cleanup in Phase 2.5."""
    return {}


def _curriculum_path(data_dir: Path) -> Path:
    return data_dir / CURRICULUM_FILENAME


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


# ── get_or_create_notebook ────────────────────────────────────────────────────

async def get_or_create_notebook(
    topic_id: str,
    topic_title: str,
    data_dir: Path,
    category: str = "SAM",
    kind: str = "topic",
) -> Optional[str]:
    """
    Повертає notebook_id для теми. Якщо Topic.nblm_notebook_id порожнє — створює
    новий через NBLM CLI і зберігає в curriculum_v2.json.

    topic_id: str v2-id (напр. "agent_architecture-1")
    """
    cur_path = _curriculum_path(data_dir)
    state = load(cur_path)
    if kind == "article":
        entity = state.get_article(topic_id)
    else:
        entity = state.get_topic(topic_id)
    if not entity:
        log.error(f"{kind.capitalize()} {topic_id!r} not found in curriculum")
        return None

    if entity.nblm_notebook_id:
        log.info(f"Reusing notebook {entity.nblm_notebook_id} for {kind} {topic_id}")
        return entity.nblm_notebook_id

    # Create new notebook
    notebook_name = f"{category} — {topic_title}"
    rc, stdout, stderr = await _run(["create", notebook_name])
    if rc != 0:
        log.error(f"Create notebook failed for {topic_id}: {stderr}")
        return None

    notebook_id = None
    for line in stdout.splitlines():
        if "Created notebook:" in line:
            notebook_id = line.split(":", 1)[-1].strip().split(" ")[0].strip()
            break

    if not notebook_id:
        log.error(f"Could not parse notebook ID from stdout: {stdout}")
        return None

    # Persist в Topic або Article
    if kind == "article":
        set_article_nblm_notebook_id(state, topic_id, notebook_id)
    else:
        set_nblm_notebook_id(state, topic_id, notebook_id)
    save(state, cur_path)
    log.info(f"Created notebook {notebook_id} for {kind} {topic_id}")
    return notebook_id

# ── generate_fmt async (Phase 6.2: --no-wait + artifact wait) ───────────

async def _start_generation(
    notebook_id: str,
    fmt: str,
    instructions: str,
) -> tuple[str, str]:
    """Phase 1: запускає генерацію через --no-wait --json. Повертає (task_id, error).
    error: "" | "rate_limit" | "error" | "unsupported"."""
    if fmt not in _NBLM_CMD_ARGS:
        log.error(f"Format {fmt!r} is not an NBLM format")
        return "", "unsupported"

    args = list(_NBLM_CMD_ARGS[fmt]) + ["-n", notebook_id, "--no-wait", "--json"]
    if instructions:
        args.append(instructions)

    rc, stdout, stderr = await _run(args, timeout=120)
    if rc == -1:
        return "", "error"
    if "rate limited" in stdout.lower() or "rate limited" in stderr.lower():
        return "", "rate_limit"
    if rc != 0:
        log.error(f"Start {fmt} failed rc={rc}: stdout={stdout[:300]} stderr={stderr[:300]}")
        return "", "error"
    try:
        data = json.loads(stdout)
        task_id = data.get("task_id", "")
        if not task_id:
            log.error(f"Start {fmt}: no task_id in response: {stdout[:300]}")
            return "", "error"
        log.info(f"Start {fmt}: task_id={task_id} status={data.get('status')}")
        return task_id, ""
    except json.JSONDecodeError as e:
        log.error(f"Start {fmt}: JSON decode failed: {e}, stdout={stdout[:300]}")
        return "", "error"


async def _wait_for_artifact(
    task_id: str,
    notebook_id: str,
    timeout: int = 1800,
) -> tuple[bool, str]:
    """Phase 2: чекає на завершення артефакту. Loop при timeout (нескінченно).
    Повертає (ok, error). error: "" | "failed" | "error"."""
    while True:
        args = ["artifact", "wait", task_id, "-n", notebook_id,
                "--timeout", str(timeout), "--json"]
        rc, stdout, stderr = await _run(args, timeout=timeout + 60)
        if rc == -1:
            log.warning(f"Wait {task_id}: subprocess timeout, retry loop")
            continue
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            log.error(f"Wait {task_id}: JSON decode failed: {e}, stdout={stdout[:300]}")
            return False, "error"
        status = data.get("status", "")
        if status == "completed":
            log.info(f"Wait {task_id}: completed")
            return True, ""
        if status == "failed":
            err = data.get("error") or "generation failed"
            log.error(f"Wait {task_id}: failed: {err}")
            return False, "failed"
        # Будь-який інший статус (in_progress/pending/timeout) — продовжуємо чекати
        log.info(f"Wait {task_id}: status={status}, continuing")


# ── generate_and_notify ──────────────────────────────────────────────────────

async def generate_and_notify(
    bot,
    chat_id: int,
    topic_id: str,
    topic_title: str,
    source_url: str,
    fmt: str,
    instructions: str,
    skip_source: bool = False,
    data_dir: Path = None,
    kind: str = "topic",
) -> None:
    """
    Один формат end-to-end: ensure notebook → add source → generate → notify.

    При успіху — Topic.formats[fmt] = {status:ready, url:<nb_url>, generated_at:now}.
    При фейлі — status:failed + error.
    """
    if data_dir is None:
        raise ValueError("data_dir is required")
    if fmt not in NBLM_FORMATS:
        await bot.send_message(
            chat_id,
            f"❌ Формат {fmt!r} не генерується через NBLM. "
            f"Доступні: {', '.join(sorted(NBLM_FORMATS))}."
        )
        return

    cur_path = _curriculum_path(data_dir)

    # Step 1: ensure notebook
    notebook_id = await get_or_create_notebook(topic_id, topic_title, data_dir, kind=kind)
    if not notebook_id:
        await bot.send_message(chat_id, "❌ Не вдалось створити notebook.")
        state = load(cur_path)
        if kind == "article" and state.get_article(topic_id):
            set_article_format_status(state, topic_id, fmt, "failed", error="notebook create failed")
            save(state, cur_path)
        elif kind == "topic" and state.get_topic(topic_id):
            set_format_status(state, topic_id, fmt, "failed", error="notebook create failed")
            save(state, cur_path)
        return

    nb_url = notebook_url(notebook_id)

    # Step 2: add source (best effort, warnings ignored)
    if not skip_source and source_url:
        rc, stdout, stderr = await _run(["source", "add", "-n", notebook_id, source_url])
        if rc != 0:
            log.warning(f"Add source warning (ignored) for {topic_id}: {stderr}")

    # Step 3: mark as generating
    state = load(cur_path)
    if kind == "article":
        set_article_format_status(state, topic_id, fmt, "generating")
    else:
        set_format_status(state, topic_id, fmt, "generating")
    save(state, cur_path)

    # Step 4: two-phase generation with re-attach support
    RETRY_DELAYS = [0] + [3600] * 71  # hourly retry up to 72h on rate_limit at start

    # Lazy re-attach: if there is already a task_id in state, skip Phase 1
    state = load(cur_path)
    existing = (state.get_article(topic_id) if kind == "article"
                else state.get_topic(topic_id))
    existing_fmt = existing.formats.get(fmt) if existing else None
    task_id = existing_fmt.task_id if (existing_fmt and existing_fmt.status == "generating") else ""

    ok, err = False, "error"

    if task_id:
        log.info(f"Re-attach {fmt} for {topic_id}: task_id={task_id}")
    else:
        # Phase 1: start with rate-limit backoff
        start_err = "error"
        for delay in RETRY_DELAYS:
            if delay:
                log.info(f"Retry start {fmt} for {topic_id} after {delay}s")
                await asyncio.sleep(delay)
            task_id, start_err = await _start_generation(notebook_id, fmt, instructions)
            if task_id or start_err != "rate_limit":
                break
        if not task_id:
            ok, err = False, start_err
        else:
            # Save task_id to state before waiting (re-attach point on restart)
            state = load(cur_path)
            if kind == "article":
                set_article_format_status(state, topic_id, fmt, "generating", task_id=task_id)
            else:
                set_format_status(state, topic_id, fmt, "generating", task_id=task_id)
            save(state, cur_path)

    # Phase 2: wait (only if we have a task_id from re-attach or from Phase 1)
    if task_id:
        ok, err = await _wait_for_artifact(task_id, notebook_id)

    # Step 5: persist outcome
    state = load(cur_path)
    if kind == "article":
        if ok:
            set_article_format_status(state, topic_id, fmt, "ready", url=nb_url)
        else:
            set_article_format_status(state, topic_id, fmt, "failed", error=err)
    else:
        if ok:
            set_format_status(state, topic_id, fmt, "ready", url=nb_url)
        else:
            set_format_status(state, topic_id, fmt, "failed", error=err)
    save(state, cur_path)

    # Step 6: notify user
    format_name = FORMAT_NAMES.get(fmt, fmt)
    if ok:
        await bot.send_message(
            chat_id,
            f"✅ {format_name} готове!\n\nТема: {topic_title}\n{nb_url}"
        )
    elif err == "rate_limit":
        await bot.send_message(
            chat_id,
            f"⏳ Google rate limit — спробуй через кілька годин.\n{nb_url}"
        )
    elif err == "timeout":
        await bot.send_message(
            chat_id,
            f"⏰ {format_name} генерується надто довго.\n{nb_url}"
        )
    else:
        await bot.send_message(
            chat_id,
            f"❌ Помилка генерації {format_name}.\n{nb_url}"
        )


# ── /notebooks command ───────────────────────────────────────────────────────

async def cmd_notebooks(update, context, data_dir: Path) -> None:
    """
    Показує всі теми які мають notebook, з переліком готових форматів.
    Не приймає curriculum-параметр — читає з curriculum_v2.json.
    """
    cur_path = _curriculum_path(data_dir)
    state = load(cur_path)

    topics_with_nb = [t for t in state.topics if t.nblm_notebook_id]
    if not topics_with_nb:
        await update.message.reply_text(
            "Ще немає жодного notebook. Згенеруй через /cur → тема → формат."
        )
        return

    # Групуємо за островами (краще орієнтування)
    by_island: dict[str, list] = {}
    for t in topics_with_nb:
        by_island.setdefault(t.island_id, []).append(t)

    lines = ["📓 *NotebookLM notebooks:*\n"]
    island_titles = {i.id: i.title for i in state.islands}
    for island_id in sorted(by_island.keys(), key=lambda i: next(
        (isl.order for isl in state.islands if isl.id == i), 999
    )):
        lines.append(f"\n*{island_titles.get(island_id, island_id)}*")
        for t in by_island[island_id]:
            nb_url_str = notebook_url(t.nblm_notebook_id)
            ready_fmts = [
                FORMAT_NAMES.get(fk, fk)
                for fk, fv in t.formats.items()
                if fv.status == "ready" and fk in NBLM_FORMATS
            ]
            icons = " ".join(ready_fmts) if ready_fmts else "—"
            lines.append(f"• [{t.title}]({nb_url_str}) {icons}")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )
