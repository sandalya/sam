from pathlib import Path
from .base import ContentBackend


class InteractiveBackend(ContentBackend):
    name = "interactive"

    def supports_format(self, fmt: str) -> bool:
        return False

    async def generate(
        self, bot, chat_id: int, *,
        entity, kind: str, fmt: str, brief, preset: dict,
        data_dir: Path, skip_source: bool = False, **kwargs,
    ) -> None:
        raise NotImplementedError("TODO: Interactive backend not implemented")
