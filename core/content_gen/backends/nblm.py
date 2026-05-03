"""
core/content_gen/backends/nblm.py — NotebookLM backend.

Містить повну імплементацію (перенесено з core/notebooklm_module.py)
+ клас NblmBackend(ContentBackend).

Публічне API (для зворотної сумісності через shim):
- generate_and_notify
- get_or_create_notebook
- cmd_notebooks
- notebook_url
- FORMAT_NAMES, NBLM_FORMATS, _NBLM_CMD_ARGS, NOTEBOOKLM_BIN
- load_nb_state
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
from .base import ContentBackend

log = logging.getLogger("core.content_gen.backends.nblm")

NOTEBOOKLM_BIN = Path("/home/sashok/.openclaw/workspace/sam/venv/bin/notebooklm")
NOTEBOOKLM_BASE_URL = "https://notebooklm.google.com/notebook/"

CURRICULUM_FILENAME = "curriculum.json"
RETRY_DELAYS = [0] + [3600] * 4  # hourly retry, 5 attempts total (~4h cap)

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
    """Legacy shim (Phase 2.3). Повертає порожній dict."""
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
        existing_id = entity.nblm_notebook_id
        probe_rc, probe_out, probe_err = await _run(
            ["source", "list", "-n", existing_id, "--json"], timeout=30
        )
        probe_ok = False
        if probe_rc == 0:
            try:
                probe_data = json.loads(probe_out)
                if probe_data is not None:
                    probe_ok = True
            except json.JSONDecodeError:
                pass
        if probe_ok:
            log.info(f"Reusing notebook {existing_id} for {kind} {topic_id}")
            return existing_id
        if probe_rc != 0:
            probe_text = (probe_out + probe_err).lower()
            if "rate limited" in probe_text or "rate_limit" in probe_text:
                log.warning(
                    f"Probe rate-limited for {existing_id} ({kind} {topic_id}), "
                    f"reusing UUID without invalidation"
                )
                return existing_id
        log.warning(
            f"Notebook {existing_id} dangling for {kind} {topic_id} "
            f"(probe rc={probe_rc}), invalidating"
        )
        if kind == "article":
            set_article_nblm_notebook_id(state, topic_id, None)
        else:
            set_nblm_notebook_id(state, topic_id, None)
        save(state, cur_path)

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

    if kind == "article":
        set_article_nblm_notebook_id(state, topic_id, notebook_id)
    else:
        set_nblm_notebook_id(state, topic_id, notebook_id)
    save(state, cur_path)
    log.info(f"Created notebook {notebook_id} for {kind} {topic_id}")
    return notebook_id


# ── _start_generation ────────────────────────────────────────────────────────

async def _start_generation(
    notebook_id: str,
    fmt: str,
    instructions: str,
    nblm_format: str | None = None,
    length: str | None = None,
) -> tuple[str, str]:
    """Phase 1: запускає генерацію через --no-wait --json. Повертає (task_id, error)."""
    if fmt not in _NBLM_CMD_ARGS:
        log.error(f"Format {fmt!r} is not an NBLM format")
        return "", "unsupported"

    args = list(_NBLM_CMD_ARGS[fmt]) + ["-n", notebook_id, "--no-wait", "--json"]
    if fmt == "podcast_nblm":
        if nblm_format:
            args.extend(["--format", nblm_format])
        if length:
            args.extend(["--length", length])
    if instructions:
        args.append(instructions)

    log.info(f"NBLM args for {fmt}: {args}")
    log.debug(f"NBLM args (full): {args}")
    rc, stdout, stderr = await _run(args, timeout=120)
    if rc == -1:
        return "", "error"
    if "rate limited" in stdout.lower() or "rate limited" in stderr.lower():
        return "", "rate_limit"
    if rc != 0:
        log.error(f"Start {fmt} failed rc={rc}: stdout={stdout[:300]} stderr={stderr[:300]}")
        try:
            data = json.loads(stdout)
            code = data.get("code", "")
            if code:
                msg = data.get("message", "")
                if msg:
                    log.error(f"Start {fmt} NBLM error code={code}: {msg}")
                return "", f"nblm_{code.lower()}"
        except json.JSONDecodeError:
            pass
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


# ── _wait_for_artifact ───────────────────────────────────────────────────────

async def _wait_for_artifact(
    task_id: str,
    notebook_id: str,
    timeout: int = 1800,
    topic_id: str | None = None,
    kind: str = "topic",
    cur_path: Path | None = None,
    fmt: str | None = None,
) -> tuple[bool, str]:
    """Phase 2: чекає на завершення артефакту. Loop при timeout (нескінченно)."""
    while True:
        if cur_path and topic_id and fmt:
            _w_state = load(cur_path)
            _w_entity = (
                _w_state.get_article(topic_id) if kind == "article"
                else _w_state.get_topic(topic_id)
            )
            if (_w_entity and _w_entity.formats.get(fmt)
                    and _w_entity.formats[fmt].status != "generating"):
                log.info(f"External stop detected in wait loop for {topic_id}/{fmt}")
                return False, "external_stop"
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
    nblm_format: str | None = None,
    length: str | None = None,
) -> None:
    """
    Один формат end-to-end: ensure notebook → add source → generate → notify.
    Сигнатура збережена для зворотної сумісності з main.py (re-attach).
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

    # Step 2: add source idempotent (best effort, warnings ignored)
    if not skip_source and source_url:
        _should_add = True
        _sl_rc, _sl_out, _sl_err = await _run(["source", "list", "-n", notebook_id, "--json"])
        if _sl_rc == 0:
            try:
                _sl_data = json.loads(_sl_out)
                _existing_urls = {s.get("url", "") for s in _sl_data.get("sources", [])}
                if source_url in _existing_urls:
                    log.info(f"Source already present for {topic_id}, skipping add")
                    _should_add = False
            except json.JSONDecodeError:
                log.warning(f"Source list JSON malformed for {topic_id}, fallback to add")
        else:
            log.warning(f"Source list failed rc={_sl_rc} for {topic_id}, fallback to add")
        if _should_add:
            rc, stdout, stderr = await _run(["source", "add", "-n", notebook_id, source_url])
            if rc != 0:
                log.warning(f"Add source warning (ignored) for {topic_id}: {stderr}")

    # Step 4: two-phase generation with re-attach support
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
                _chk_state = load(cur_path)
                _chk_entity = (
                    _chk_state.get_article(topic_id) if kind == "article"
                    else _chk_state.get_topic(topic_id)
                )
                if (_chk_entity and _chk_entity.formats.get(fmt)
                        and _chk_entity.formats[fmt].status != "generating"):
                    log.info(
                        f"External stop detected for {topic_id}/{fmt} "
                        f"(status={_chk_entity.formats[fmt].status}), exiting retry loop"
                    )
                    return
            task_id, start_err = await _start_generation(
                notebook_id, fmt, instructions,
                nblm_format=nblm_format, length=length,
            )
            if task_id or start_err != "rate_limit":
                break
        if not task_id:
            if start_err == "rate_limit":
                start_err = "rate_limit_exhausted"
            ok, err = False, start_err
        else:
            # Save task_id to state before waiting (re-attach point on restart)
            state = load(cur_path)
            if kind == "article":
                set_article_format_status(state, topic_id, fmt, "generating", task_id=task_id)
            else:
                set_format_status(state, topic_id, fmt, "generating", task_id=task_id)
            save(state, cur_path)

    # Phase 2: wait (only if we have a task_id)
    if task_id:
        ok, err = await _wait_for_artifact(
            task_id, notebook_id,
            topic_id=topic_id, kind=kind, cur_path=cur_path, fmt=fmt,
        )

    # Step 5: persist outcome
    state = load(cur_path)
    if err == "external_stop":
        _es_entity = (
            state.get_article(topic_id) if kind == "article"
            else state.get_topic(topic_id)
        )
        _es_fmt = _es_entity.formats.get(fmt) if _es_entity else None
        _es_status = _es_fmt.status if _es_fmt else "unknown"
        if _es_status in ("failed", "cancelled"):
            log.info(f"External stop confirmed for {topic_id}/{fmt}: status={_es_status}")
        else:
            log.warning(
                f"External stop for {topic_id}/{fmt}: unexpected status={_es_status!r}, "
                f"exiting without mutation"
            )
        return
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

    # RSS regen після успішної генерації podcast_nblm (non-fatal)
    if ok and fmt == "podcast_nblm":
        try:
            from core.rss_feed import regenerate_feed_async
            asyncio.create_task(regenerate_feed_async())
        except Exception as _rss_e:
            log.warning(f"RSS regen failed (non-fatal): {_rss_e}")

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
    cur_path = _curriculum_path(data_dir)
    state = load(cur_path)

    topics_with_nb = [t for t in state.topics if t.nblm_notebook_id]
    if not topics_with_nb:
        await update.message.reply_text(
            "Ще немає жодного notebook. Згенеруй через /cur → тема → формат."
        )
        return

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


# ── NblmBackend ──────────────────────────────────────────────────────────────

class NblmBackend(ContentBackend):
    name = "nblm"

    def supports_format(self, fmt: str) -> bool:
        return fmt in _NBLM_CMD_ARGS

    async def generate(
        self, bot, chat_id: int, *,
        entity, kind: str, fmt: str, brief, preset: dict,
        data_dir: Path, skip_source: bool = False, **kwargs,
    ) -> None:
        instructions = brief.suggested_instructions
        if preset.get("format_modifier"):
            instructions = f"{instructions} {preset['format_modifier']}"

        source_url = entity.source_url if kind == "article" else entity.read

        await generate_and_notify(
            bot=bot,
            chat_id=chat_id,
            topic_id=entity.id,
            topic_title=entity.title,
            source_url=source_url or "",
            fmt=fmt,
            instructions=instructions,
            skip_source=skip_source,
            data_dir=data_dir,
            kind=kind,
            nblm_format=preset.get("nblm_format"),
            length=preset.get("length"),
        )
