"""
core/content_gen — backend-agnostic content generation package.

Public API:
    prepare_and_generate(bot, chat_id, *, entity_id, kind, fmt, data_dir,
                         backend, preset, skip_source) -> None
"""
import logging
from pathlib import Path

from .presets import NBLM_PRESETS
from .brief import generate_brief
from .backends.nblm import NblmBackend
from .backends.tts import TtsBackend
from .backends.interactive import InteractiveBackend

log = logging.getLogger("core.content_gen")

BACKENDS = {
    "nblm": NblmBackend(),
    "tts": TtsBackend(),
    "interactive": InteractiveBackend(),
}


async def prepare_and_generate(
    bot,
    chat_id: int,
    *,
    entity_id: str,
    kind: str,
    fmt: str,
    data_dir: Path,
    backend: str = "nblm",
    preset: str = "standard",
    skip_source: bool = False,
) -> None:
    """
    1. Load entity from curriculum
    2. Generate ContentBrief if not cached (Haiku), save back
    3. Call backend.generate(...)
    """
    from curriculum.storage import load, save

    cur_path = data_dir / "curriculum.json"
    state = load(cur_path)
    entity = state.get_article(entity_id) if kind == "article" else state.get_topic(entity_id)

    if entity is None:
        log.error(f"prepare_and_generate: {kind} {entity_id!r} not found")
        await bot.send_message(chat_id, f"❌ {kind.capitalize()} {entity_id!r} не знайдено.")
        return

    preset_cfg = NBLM_PRESETS.get(preset, NBLM_PRESETS["standard"])

    if entity.brief is None:
        log.info(f"Generating brief for {kind} {entity_id!r} (preset={preset})")
        entity.brief = await generate_brief(entity, kind, preset_cfg["angle"])
        save(state, cur_path)
        log.info(f"Brief cached for {entity_id!r}")
    else:
        log.info(f"Reusing cached brief for {kind} {entity_id!r}")

    backend_obj = BACKENDS.get(backend)
    if backend_obj is None:
        log.error(f"Unknown backend: {backend!r}")
        await bot.send_message(chat_id, f"❌ Невідомий backend: {backend!r}")
        return

    await backend_obj.generate(
        bot, chat_id,
        entity=entity,
        kind=kind,
        fmt=fmt,
        brief=entity.brief,
        preset=preset_cfg,
        data_dir=data_dir,
        skip_source=skip_source,
    )
