"""Sam catchup — ретроспектива AI-новин."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.catchup_module import CatchupModule as _CatchupModule
from .base import SAM_PERSONA, DATA_DIR, PROFILE_PATH


class CatchupModule(_CatchupModule):
    catchup_topics = """- AI agents frameworks architectures
- MCP Model Context Protocol
- LLM new models releases Anthropic OpenAI Google
- AI developer tooling
- AI real world products use cases"""
    catchup_domain = "AI-новин"

    def __init__(self, owner_chat_id: int):
        super().__init__(
            owner_chat_id=owner_chat_id,
            persona=SAM_PERSONA,
            data_dir=DATA_DIR,
            profile_path=PROFILE_PATH,
        )
