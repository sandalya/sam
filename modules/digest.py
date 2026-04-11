"""Sam digest — AI-новини."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.digest_module import DigestModule as _DigestModule
from .base import SAM_PERSONA, DATA_DIR, PROFILE_PATH


class DigestModule(_DigestModule):
    topics = [
        "AI agents frameworks architectures 2025",
        "MCP Model Context Protocol new servers integrations",
        "LLM new models releases Anthropic OpenAI Google",
        "AI agents real world use cases products",
        "LLM developer tooling prompting evals",
    ]
    digest_label = "AI"
    overview_style = "як Сем: коротко, чітко, з характером"

    def __init__(self, owner_chat_id: int):
        super().__init__(
            owner_chat_id=owner_chat_id,
            persona=SAM_PERSONA,
            data_dir=DATA_DIR,
            profile_path=PROFILE_PATH,
        )
