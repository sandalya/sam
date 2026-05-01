from abc import ABC, abstractmethod
from pathlib import Path


class ContentBackend(ABC):
    name: str

    @abstractmethod
    async def generate(
        self, bot, chat_id: int, *,
        entity, kind: str, fmt: str, brief, preset: dict,
        data_dir: Path, skip_source: bool = False, **kwargs,
    ) -> None: ...

    @abstractmethod
    def supports_format(self, fmt: str) -> bool: ...
