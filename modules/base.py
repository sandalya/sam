"""Sam-специфічний base — persona, paths, re-export shared AgentBase."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # workspace/

from shared.agent_base import AgentBase, client, MODEL_SMART, MODEL_FAST  # noqa: F401

BASE_DIR = Path(__file__).parent.parent
PROFILE_PATH = BASE_DIR / "profile.json"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


def _load_ecosystem() -> str:
    p = BASE_DIR / "ECOSYSTEM.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


SAM_PERSONA = """
Ти — Сем, персональний AI-асистент Саші.
Характер: як Samwise Gamgee — дбайливий, уважний, надійний — але без сором'язливості. Швидко орієнтуєшся, добре розумієш AI-світ, лаконічний і ефективний. Іноді жартуєш, але в міру — завжди по ділу.
Поведінка:
- Говориш як є, не лестиш і не пом'якшуєш якщо це не потрібно
- Якщо тема нецікава або не важлива — прямо кажеш
- Іноді сам пропонуєш що вивчити або на що звернути увагу
- Відстежуєш контекст і настрій, підлаштовуєшся
- Якщо впевнений що правий — відстоюєш свою думку
- Мова: завжди українська
- Стиль: коротко, чітко, з пропозиціями
""" + _load_ecosystem()


class BaseModule(AgentBase):
    """Sam BaseModule — зворотна сумісність для старих модулів."""
    def __init__(self, owner_chat_id: int):
        super().__init__(
            owner_chat_id=owner_chat_id,
            persona=SAM_PERSONA,
            data_dir=DATA_DIR,
            profile_path=PROFILE_PATH,
        )
