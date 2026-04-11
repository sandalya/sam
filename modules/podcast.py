"""Sam podcast — AI-тематика."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.podcast_module import PodcastModule as _PodcastModule
from .base import SAM_PERSONA, DATA_DIR, PROFILE_PATH
from .curriculum import CURRICULUM


class SamPodcast(_PodcastModule):
    podcast_audience = (
        "Experienced Python developer building AI agents and Telegram bots. "
        "Knows the basics, wants deeper understanding of theory and architecture."
    )
    podcast_style = (
        "Reference practical scenarios: tool use in bots, managing agent state, "
        "prompt design, Anthropic API patterns."
    )

    def __init__(self, owner_chat_id: int):
        super().__init__(
            owner_chat_id=owner_chat_id,
            persona=SAM_PERSONA,
            data_dir=DATA_DIR,
            profile_path=PROFILE_PATH,
        )
        self.CURRICULUM = CURRICULUM


# Singleton для main.py
_podcast_instance: dict[int, SamPodcast] = {}

def _get(owner_chat_id: int = 0) -> SamPodcast:
    if owner_chat_id not in _podcast_instance:
        _podcast_instance[owner_chat_id] = SamPodcast(owner_chat_id)
    return _podcast_instance[owner_chat_id]

async def cmd_podcast(update, context):
    await _get(update.effective_user.id).cmd_podcast(update, context)
