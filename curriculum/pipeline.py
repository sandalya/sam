"""
curriculum/pipeline.py — Pipeline orchestrator (Phase 2.3).

Запускає генерацію всіх форматів для теми послідовно
за content_style порядком (audio-first або visual-first).
Exam не генерується пайплайном (Phase 3 — діалоговий тест).

Публічне API:
    run_pipeline(bot, chat_id, topic_id, data_dir) -> bool
"""
import asyncio
import logging
from pathlib import Path

from curriculum.storage import load as load_curriculum, save as save_curriculum
from curriculum.models import Topic

log = logging.getLogger("curriculum.pipeline")

# Порядок генерації за content_style (exam виключено — Phase 3)
AUDIO_FIRST_ORDER = [
    "slides",
    "podcast_nblm",
    "podcast_tts",
    "video",
    "infographic",
    "flashcards",
]

VISUAL_FIRST_ORDER = [
    "slides",
    "infographic",
    "video",
    "podcast_nblm",
    "podcast_tts",
    "flashcards",
]

# Формати які генеруються через NBLM CLI
NBLM_FORMATS = {"slides", "podcast_nblm", "video", "infographic", "flashcards"}

# Статуси які пропускаємо (вже готово, генерується, або свідомо пропущено)
SKIP_STATUSES = {"ready", "generating", "skipped"}


def _get_order(topic: Topic) -> list[str]:
    if topic.content_style == "visual":
        return VISUAL_FIRST_ORDER
    return AUDIO_FIRST_ORDER


def _curriculum_path(data_dir: Path) -> Path:
    return data_dir / "curriculum.json"


async def run_pipeline(
    bot,
    chat_id: int,
    topic_id: str,
    data_dir: Path,
) -> bool:
    """
    Запускає генерацію всіх форматів для теми.

    Послідовно проходить формати в порядку content_style.
    Пропускає формати зі статусом ready/generating/skipped.
    Після кожного формату — refresh pinned.
    Повертає True якщо хоча б один формат було запущено.

    Працює як asyncio.create_task — не блокує deep-link handler.
    """
    from modules.pinned import refresh_pinned

    cur_path = _curriculum_path(data_dir)
    state = load_curriculum(cur_path)
    topic = state.get_topic(topic_id)

    if not topic:
        log.error(f"Pipeline: topic {topic_id!r} not found")
        await bot.send_message(chat_id, f"❌ Тема {topic_id} не знайдена.")
        return False

    order = _get_order(topic)

    # Визначаємо які формати потрібно згенерувати
    to_generate = []
    for fmt_key in order:
        existing = topic.formats.get(fmt_key)
        if existing and existing.status in SKIP_STATUSES:
            log.info(f"Pipeline {topic_id}: skip {fmt_key} (status={existing.status})")
            continue
        to_generate.append(fmt_key)

    if not to_generate:
        await bot.send_message(
            chat_id,
            f"✅ Всі формати для <b>{topic.title}</b> вже згенеровані або в процесі.",
            parse_mode="HTML",
        )
        return False

    fmt_list = ", ".join(to_generate)
    await bot.send_message(
        chat_id,
        f"🚀 Pipeline для <b>{topic.title}</b>\n"
        f"Формати: {fmt_list}\n"
        f"Стиль: {topic.content_style}-first",
        parse_mode="HTML",
    )

    generated_count = 0

    for fmt_key in to_generate:
        # Перечитуємо стан перед кожним форматом (попередній міг змінити)
        state = load_curriculum(cur_path)
        topic = state.get_topic(topic_id)
        if not topic:
            log.error(f"Pipeline: topic {topic_id} disappeared mid-pipeline")
            break

        # Повторна перевірка — стан міг змінитись
        existing = topic.formats.get(fmt_key)
        if existing and existing.status in SKIP_STATUSES:
            continue

        try:
            if fmt_key in NBLM_FORMATS:
                await _generate_nblm(bot, chat_id, topic_id, topic.title, topic.read, fmt_key, data_dir)
            elif fmt_key == "podcast_tts":
                await _generate_tts(bot, chat_id, topic_id, data_dir)
            else:
                log.warning(f"Pipeline: unknown format {fmt_key}, skipping")
                continue
            generated_count += 1
        except Exception as e:
            log.error(f"Pipeline {topic_id}/{fmt_key} failed: {e}", exc_info=True)
            await bot.send_message(
                chat_id,
                f"⚠️ Помилка {fmt_key}: {str(e)[:200]}",
            )

        # Refresh pinned після кожного формату
        try:
            await refresh_pinned(bot, chat_id, data_dir)
        except Exception as e:
            log.warning(f"Pipeline: refresh_pinned failed after {fmt_key}: {e}")

    # Фінальне повідомлення
    state = load_curriculum(cur_path)
    topic = state.get_topic(topic_id)
    if topic:
        ready = sum(1 for f in topic.formats.values() if f.status == "ready")
        total = len(AUDIO_FIRST_ORDER)  # 6 (без exam)
        await bot.send_message(
            chat_id,
            f"🏁 Pipeline завершено: <b>{topic.title}</b>\n"
            f"Готово: {ready}/{total} форматів",
            parse_mode="HTML",
        )

    # Фінальний refresh
    try:
        await refresh_pinned(bot, chat_id, data_dir)
    except Exception:
        pass

    return generated_count > 0


async def _generate_nblm(
    bot,
    chat_id: int,
    topic_id: str,
    topic_title: str,
    source_url: str,
    fmt_key: str,
    data_dir: Path,
) -> None:
    """Делегує генерацію NBLM-формату до notebooklm_module."""
    from core.notebooklm_module import generate_and_notify

    await generate_and_notify(
        bot=bot,
        chat_id=chat_id,
        topic_id=topic_id,
        topic_title=topic_title,
        source_url=source_url or "",
        fmt=fmt_key,
        instructions="",
        data_dir=data_dir,
    )


async def _generate_tts(
    bot,
    chat_id: int,
    topic_id: str,
    data_dir: Path,
) -> None:
    """Делегує генерацію TTS podcast до podcast_module."""
    from core.podcast_module import generate_tts_for_pipeline

    await generate_tts_for_pipeline(
        bot=bot,
        chat_id=chat_id,
        topic_id=topic_id,
        data_dir=data_dir,
    )
