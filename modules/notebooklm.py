"""Sam notebooklm — re-export shared з Sam data_dir.

Phase 2.3: notebook_id мігровано в Topic.nblm_notebook_id всередині curriculum_v2.json.
Окремого nb_state файлу більше не існує. load_nb_state/save_nb_state прибрані.
"""

from core.notebooklm_module import (  # noqa: F401
    generate_and_notify as _generate_and_notify,
    get_or_create_notebook as _get_or_create_notebook,
    cmd_notebooks as _cmd_notebooks,
    _run,
    notebook_url,
    FORMAT_NAMES,
    NBLM_FORMATS,
)
from .base import DATA_DIR


async def get_or_create_notebook(topic_id: str, topic_title: str) -> str | None:
    return await _get_or_create_notebook(topic_id, topic_title, DATA_DIR)


async def generate_and_notify(bot, chat_id, topic_id, topic_title, source_url,
                               fmt, instructions, skip_source=False, kind="topic", **_):
    return await _generate_and_notify(
        bot=bot, chat_id=chat_id, topic_id=topic_id, topic_title=topic_title,
        source_url=source_url, fmt=fmt, instructions=instructions,
        skip_source=skip_source, data_dir=DATA_DIR, kind=kind,
    )


async def cmd_notebooks(update, context):
    return await _cmd_notebooks(update, context, DATA_DIR)
