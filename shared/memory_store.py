"""
shared/memory_store.py — довгострокова пам'ять агента.

Зберігає важливі факти про користувача між сесіями:
- цілі і плани
- стилі і уподобання  
- проекти над якими працює
- важливі речі які сказав

Агент сам вирішує що записати після кожної розмови.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("shared.memory")

MAX_MEMORIES = 100  # скільки фактів зберігаємо максимум


class MemoryStore:
    def __init__(self, data_dir: Path):
        self.path = data_dir / "memory.json"
        self._ensure()

    def _ensure(self):
        if not self.path.exists():
            self.path.write_text(json.dumps({"memories": []}, ensure_ascii=False, indent=2))

    def load(self) -> list[dict]:
        try:
            return json.loads(self.path.read_text()).get("memories", [])
        except Exception:
            return []

    def save(self, memories: list[dict]):
        self.path.write_text(
            json.dumps({"memories": memories}, ensure_ascii=False, indent=2)
        )

    def add(self, fact: str, category: str = "general"):
        """Додати новий факт. Дублікати ігноруються."""
        memories = self.load()
        # не додавати якщо майже ідентичне вже є
        existing_facts = [m["fact"].lower() for m in memories]
        if fact.lower() in existing_facts:
            return
        memories.append({
            "fact": fact,
            "category": category,
            "date": datetime.now().strftime("%Y-%m-%d"),
        })
        # обрізаємо якщо забагато — зберігаємо найновіші
        if len(memories) > MAX_MEMORIES:
            memories = memories[-MAX_MEMORIES:]
        self.save(memories)
        logger.info(f"Memory saved [{category}]: {fact}")

    def to_context(self) -> str:
        """Форматує пам'ять для системного промпту."""
        memories = self.load()
        if not memories:
            return ""
        by_category: dict[str, list[str]] = {}
        for m in memories:
            cat = m.get("category", "general")
            by_category.setdefault(cat, []).append(m["fact"])
        lines = ["📋 Що я знаю про користувача (довгострокова пам'ять):"]
        for cat, facts in by_category.items():
            lines.append(f"\n[{cat}]")
            for f in facts[-10:]:  # максимум 10 на категорію
                lines.append(f"  • {f}")
        return "\n".join(lines)
