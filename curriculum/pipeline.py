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
    "flashcards",   # LLM-generated (Sonnet), see LLM_FORMATS
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
NBLM_FORMATS = {"slides", "podcast_nblm", "video", "infographic"}

# LLM-generated formats (Anthropic Sonnet, not NBLM CLI)
LLM_FORMATS = {"flashcards"}

# Default deck size; per-topic override via Topic.formats.flashcards.deck_size
CARDS_PER_TOPIC = 10

# Retry генерації при invalid JSON або валідації, що не пройшла
FLASHCARDS_MAX_RETRIES = 1

# Sonnet prompt для генерації flashcards (Phase 6.1)
_FLASHCARDS_PROMPT_TEMPLATE = (
    "Ти створюєш флеш-картки для закріплення матеріалу.\n"
    "\n"
    "Тема: {title}\n"
    "Опис (що треба знати): {read}\n"
    "Острів: {island_title}\n"
    "\n"
    "Створи РІВНО {deck_size} карток у форматі JSON. Кожна картка має:\n"
    "- \"q\": питання (1-2 речення, українською, конкретне)\n"
    "- \"a\": правильна відповідь (1-2 речення, повна але стисла)\n"
    "- \"distractors\": масив з РІВНО 3 неправильних варіантів, які:\n"
    "  * звучать правдоподібно для людини, що плутається в темі\n"
    "  * мають схожу довжину з правильною відповіддю\n"
    "  * НЕ є очевидно абсурдними\n"
    "  * НЕ повторюють правильну відповідь перефразовано\n"
    "\n"
    "Уникай:\n"
    "- питань на чисте визначення (натомість перевіряй використання, відмінності, наслідки)\n"
    "- питань з відповіддю так/ні\n"
    "- distractors що є частковою правдою\n"
    "\n"
    "Поверни ТІЛЬКИ JSON-масив карток, без преамбули, без markdown-блоків:\n"
    "[\n"
    "  {{\"q\": \"...\", \"a\": \"...\", \"distractors\": [\"...\", \"...\", \"...\"]}}\n"
    "]\n"
)

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
    only_formats: set[str] | None = None,
    silent: bool = False,
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
    if only_formats:
        order = [f for f in order if f in only_formats]
        log.info(f"Pipeline {topic_id}: filtered to {order} (only={only_formats})")

    # Визначаємо які формати потрібно згенерувати
    to_generate = []
    for fmt_key in order:
        existing = topic.formats.get(fmt_key)
        if existing and existing.status in SKIP_STATUSES:
            log.info(f"Pipeline {topic_id}: skip {fmt_key} (status={existing.status})")
            continue
        to_generate.append(fmt_key)

    if not to_generate:
        if not silent:
            await bot.send_message(
                chat_id,
                f"✅ Всі формати для <b>{topic.title}</b> вже згенеровані або в процесі.",
                parse_mode="HTML",
            )
        return False

    fmt_list = ", ".join(to_generate)
    if not silent:
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
            elif fmt_key in LLM_FORMATS:
                if fmt_key == "flashcards":
                    await _generate_flashcards_llm(bot, chat_id, topic_id, data_dir, silent=silent)
                else:
                    log.warning(f"Pipeline: LLM_FORMATS has {fmt_key} but no handler")
                    continue
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
        if not silent:
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
    only_formats: set[str] | None = None,
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
    only_formats: set[str] | None = None,
) -> None:
    """Делегує генерацію TTS podcast до podcast_module."""
    from core.podcast_module import generate_tts_for_pipeline

    await generate_tts_for_pipeline(
        bot=bot,
        chat_id=chat_id,
        topic_id=topic_id,
        data_dir=data_dir,
    )


async def _generate_flashcards_llm(
    bot,
    chat_id: int,
    topic_id: str,
    data_dir: Path,
    only_formats: set[str] | None = None,
    silent: bool = False,
) -> None:
    """Генерує flashcards deck через Sonnet (Phase 6.1)."""
    import asyncio as _asyncio
    import json as _json
    import re as _re
    from shared.agent_base import client as _client, MODEL_SMART as _MODEL
    from curriculum.storage import load as _load, save as _save
    from curriculum.mutations import set_format_status

    cur_path = _curriculum_path(data_dir)
    state = _load(cur_path)
    topic = state.get_topic(topic_id)
    if not topic:
        log.error(f"flashcards: topic {topic_id} not found")
        return

    fmt = topic.formats.get("flashcards")
    deck_size = (fmt.deck_size if fmt else None) or CARDS_PER_TOPIC
    island = state.get_island(topic.island_id)
    island_title = island.title if island else topic.island_id

    set_format_status(state, topic_id, "flashcards", "generating")
    _save(state, cur_path)
    log.info(f"flashcards: generating for {topic_id} deck_size={deck_size}")

    prompt = _FLASHCARDS_PROMPT_TEMPLATE.format(
        title=topic.title,
        read=topic.read or "(опис не заданий)",
        island_title=island_title,
        deck_size=deck_size,
    )

    cards = None
    last_error = None
    for attempt in range(FLASHCARDS_MAX_RETRIES + 1):
        temperature = 0.3 if attempt == 0 else 0.5
        try:
            resp = await _asyncio.to_thread(
                _client.messages.create,
                model=_MODEL,
                max_tokens=4000,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text.strip()
            cards = _parse_and_validate_cards(raw, deck_size)
            log.info(f"flashcards: attempt {attempt+1} ok, got {len(cards)} cards")
            break
        except Exception as e:
            last_error = str(e)[:200]
            log.warning(f"flashcards: attempt {attempt+1} failed for {topic_id}: {last_error}")

    # Перечитуємо стан (міг змінитись за час LLM-виклику)
    state = _load(cur_path)
    topic = state.get_topic(topic_id)
    if not topic:
        log.error(f"flashcards: topic {topic_id} disappeared")
        return

    if cards is None:
        set_format_status(state, topic_id, "flashcards", "failed", error=last_error or "unknown generation error")
        _save(state, cur_path)
        await bot.send_message(
            chat_id,
            f"Flashcards для <b>{topic.title}</b> — помилка генерації: {last_error}",
            parse_mode="HTML",
        )
        return

    # Успіх — зберігаємо cards у форматі
    for i, card in enumerate(cards, start=1):
        card["id"] = f"card_{i:02d}"
    fmt = topic.format("flashcards")
    fmt.cards = cards
    fmt.deck_size = deck_size
    set_format_status(state, topic_id, "flashcards", "ready")
    _save(state, cur_path)
    log.info(f"flashcards: ready for {topic_id} with {len(cards)} cards")
    if not silent:
        await bot.send_message(
            chat_id,
            f"Flashcards для <b>{topic.title}</b> готові: {len(cards)} карток.",
            parse_mode="HTML",
        )


def _parse_and_validate_cards(raw: str, deck_size: int) -> list[dict]:
    """Парсить JSON-масив карток, валідує структуру. Кидає ValueError якщо щось не так."""
    import json as _json
    import re as _re
    # Sonnet іноді обгортає у markdown попри prompt — витягуємо масив
    text = raw.strip()
    if not text.startswith("["):
        m = _re.search(r"\[.*\]", text, _re.DOTALL)
        if not m:
            raise ValueError(f"no JSON array found in response: {text[:100]!r}")
        text = m.group(0)
    try:
        cards = _json.loads(text)
    except Exception as e:
        raise ValueError(f"JSON parse failed: {e}")
    if not isinstance(cards, list):
        raise ValueError(f"expected list, got {type(cards).__name__}")
    if len(cards) != deck_size:
        raise ValueError(f"expected {deck_size} cards, got {len(cards)}")
    for i, c in enumerate(cards):
        if not isinstance(c, dict):
            raise ValueError(f"card[{i}] is not a dict")
        for field in ("q", "a", "distractors"):
            if field not in c:
                raise ValueError(f"card[{i}] missing field {field!r}")
        if not isinstance(c["q"], str) or not c["q"].strip():
            raise ValueError(f"card[{i}].q is empty or not str")
        if not isinstance(c["a"], str) or not c["a"].strip():
            raise ValueError(f"card[{i}].a is empty or not str")
        d = c["distractors"]
        if not isinstance(d, list) or len(d) != 3:
            raise ValueError(f"card[{i}].distractors must be list of 3")
        for j, x in enumerate(d):
            if not isinstance(x, str) or not x.strip():
                raise ValueError(f"card[{i}].distractors[{j}] empty or not str")
    return cards
