"""Sam notebooklm — re-export shared з Sam data_dir."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.notebooklm_module import (  # noqa: F401
    generate_and_notify as _generate_and_notify,
    get_or_create_notebook as _get_or_create_notebook,
    cmd_notebooks as _cmd_notebooks,
    _run,
    load_nb_state,
    save_nb_state,
    notebook_url,
)
from .base import DATA_DIR
from .curriculum import CURRICULUM


async def get_or_create_notebook(topic_id: int, topic_title: str) -> str | None:
    return await _get_or_create_notebook(topic_id, topic_title, DATA_DIR)


async def generate_and_notify(bot, chat_id, topic_id, topic_title, source_url,
                               fmt, instructions, skip_source=False, **_):
    return await _generate_and_notify(
        bot=bot, chat_id=chat_id, topic_id=topic_id, topic_title=topic_title,
        source_url=source_url, fmt=fmt, instructions=instructions,
        skip_source=skip_source, data_dir=DATA_DIR,
    )


async def cmd_notebooks(update, context):
    return await _cmd_notebooks(update, context, DATA_DIR, CURRICULUM)
