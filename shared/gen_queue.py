"""
shared/gen_queue.py — глобальна черга генерації контенту.
Фази: 1) TTS паралельно, 2) NbLM podcast, 3) NbLM інші, 4) NbLM video.
Один фінальний звіт в кінці.
"""
import asyncio
import logging
from pathlib import Path

log = logging.getLogger("shared.gen_queue")

# Семафор для NbLM — не більше 2 паралельних запитів
NBLM_SEM = asyncio.Semaphore(2)

PHASE_ORDER = [
    ["tts"],
    ["podcast"],
    ["flashcards", "slides", "infographic"],
    ["video"],
]


async def run_global_gen(
    bot,
    chat_id: int,
    tasks: list[dict],  # [{"item": {...}, "selected": [...], "data_dir": Path, "engine": inst}]
):
    """
    Запускає глобальну чергу генерації для списку тем.
    tasks — список dict з item, selected, data_dir, engine.
    """
    results = {str(t["item"]["id"]): {} for t in tasks}

    for phase_fmts in PHASE_ORDER:
        phase_tasks = []
        for task in tasks:
            fmts = [f for f in task["selected"] if f in phase_fmts]
            if not fmts:
                continue
            if "tts" in phase_fmts:
                if "tts" in task["selected"]:
                    phase_tasks.append(_run_tts(task, results))
            else:
                phase_tasks.append(_run_nblm_formats(task, fmts, results))

        if phase_tasks:
            phase_name = "/".join(phase_fmts)
            log.info(f"[GenQueue] Phase {phase_name}: {len(phase_tasks)} tasks")
            await asyncio.gather(*phase_tasks, return_exceptions=True)

    # Фінальний звіт
    await _send_final_report(bot, chat_id, tasks, results)


async def _run_tts(task: dict, results: dict):
    """TTS генерація для однієї теми."""
    item = task["item"]
    engine = task["engine"]
    tid = str(item["id"])
    try:
        from shared.podcast_module import PodcastModule

        class _TmpPodcast(PodcastModule):
            pass

        pod = _TmpPodcast.__new__(_TmpPodcast)
        pod.podcast_audience = getattr(engine, "podcast_audience", "AI developer")
        pod.podcast_style = getattr(engine, "podcast_style", "")
        pod.CURRICULUM = getattr(engine, "CURRICULUM", [])
        pod.data_dir = engine.data_dir
        pod.profile_path = engine.profile_path

        content_size = len(item.get("why", "")) + len(item.get("do", "")) + len(item.get("title", ""))
        fmt = "deep" if content_size > 300 else "short"

        loop = asyncio.get_event_loop()
        script = await loop.run_in_executor(None, pod._generate_script, item, fmt)
        mp3_path = await loop.run_in_executor(None, pod._tts, script)

        label = "~8-12 хв" if fmt == "short" else "~15-20 хв"
        caption = f"<b>{item['title']}</b>\n<i>{label} • Curriculum #{item['id']}</i>"
        with open(mp3_path, "rb") as f:
            msg = await task["bot_send_audio"](
                audio=f,
                title=item["title"],
                performer="Sam Podcast",
                caption=caption,
                parse_mode="HTML",
            )
        # Зберігаємо file_id
        ps = engine._load_podcast_state()
        if str(item["id"]) not in ps:
            ps[str(item["id"])] = {}
        ps[str(item["id"])][fmt] = {"file_id": msg.audio.file_id}
        engine._save_podcast_state(ps)
        mp3_path.unlink(missing_ok=True)

        results[tid]["tts"] = "ok"
        log.info(f"[GenQueue] TTS ok for topic {item['id']}")
    except Exception as e:
        log.error(f"[GenQueue] TTS failed for topic {item['id']}: {e}", exc_info=True)
        results[tid]["tts"] = "error"


async def _run_nblm_formats(task: dict, fmts: list, results: dict):
    """NbLM генерація форматів для однієї теми з семафором."""
    async with NBLM_SEM:
        item = task["item"]
        engine = task["engine"]
        data_dir = task["data_dir"]
        tid = str(item["id"])
        try:
            from shared.notebooklm_module import generate_fmt, get_or_create_notebook as _get_nb, _run as nb_run, load_nb_state, save_nb_state

            notebook_id = await _get_nb(item["id"], item["title"], data_dir, category=item.get("category", "AGENT"))
            if not notebook_id:
                log.warning(f"[GenQueue] No notebook_id for topic {item['id']}, skipping")
                for fmt in fmts:
                    results[tid][fmt] = "error"
                return

            if item.get("read"):
                rc, _, stderr = await nb_run(["source", "add", "-n", notebook_id, item["read"]])
                if rc != 0:
                    log.warning(f"[GenQueue] Add source warning: {stderr}")

            page_text = await engine._fetch_page(item["read"]) if item.get("read") else ""
            BACKOFF = [0, 15 * 60, 30 * 60, 60 * 60, 120 * 60]
            FMT_PAUSE = 45

            for fmt_idx, fmt in enumerate(fmts):
                if fmt_idx > 0:
                    await asyncio.sleep(FMT_PAUSE)

                instructions = ""
                if page_text:
                    loop = asyncio.get_event_loop()
                    instructions = await loop.run_in_executor(None, engine._generate_nb_prompt, item, fmt, page_text)
                    instructions = instructions[:500]

                ok, err = False, "error"
                for attempt, delay in enumerate(BACKOFF):
                    if delay:
                        log.info(f"[GenQueue] {fmt} topic {item['id']} rate_limit attempt {attempt}, waiting {delay//60}min")
                        await asyncio.sleep(delay)
                    try:
                        ok, err = await generate_fmt(notebook_id, fmt, instructions, item["id"], data_dir)
                    except Exception as e:
                        log.warning(f"[GenQueue] generate_fmt {fmt} exception: {e}")
                        err, ok = "error", False
                    if ok or err != "rate_limit":
                        break

                results[tid][fmt] = "ok" if ok else err
                log.info(f"[GenQueue] topic {item['id']} {fmt} -> {results[tid][fmt]}")

        except Exception as e:
            log.error(f"[GenQueue] NbLM failed for topic {item['id']}: {e}", exc_info=True)
            for fmt in fmts:
                results[tid].setdefault(fmt, "error")


async def _send_final_report(bot, chat_id: int, tasks: list, results: dict):
    """Один фінальний звіт по всіх темах."""
    from shared.curriculum_engine import FORMAT_NAMES
    lines = ["📊 <b>Генерація завершена</b>\n"]
    has_problems = False

    for task in tasks:
        item = task["item"]
        tid = str(item["id"])
        topic_results = results.get(tid, {})
        if not topic_results:
            continue

        ok_fmts = [f for f, s in topic_results.items() if s == "ok"]
        hard_fail_fmts = [f for f, s in topic_results.items() if s == "error"]
        retry_fmts = [f for f, s in topic_results.items() if s in ("rate_limit", "timeout")]

        if not ok_fmts and not hard_fail_fmts and retry_fmts:
            continue  # все в черзі на retry — мовчимо

        status = "✅" if not hard_fail_fmts else ("⚠️" if ok_fmts else "❌")
        line = f"{status} <b>{item['title']}</b>"
        if hard_fail_fmts:
            has_problems = True
            names = ", ".join(FORMAT_NAMES.get(f, f) for f in hard_fail_fmts)
            line += f"\n   ❌ Помилка: {names}"
        if retry_fmts:
            names = ", ".join(FORMAT_NAMES.get(f, f) for f in retry_fmts)
            line += f"\n   🔄 В черзі: {names}"
        lines.append(line)

    if has_problems:
        lines.append("\nДеякі формати не вдались — перевір конфігурацію.")

    if len(lines) <= 1:
        return
    await bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML")
