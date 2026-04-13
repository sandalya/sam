"""
shared/conversation_store.py — пам'ять поточної розмови.

Зберігає останні N повідомлень між Ксю/Сашком і агентом.
Агент читає їх при кожному новому повідомленні → пам'ятає контекст.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("shared.conversation")

MAX_MESSAGES = 20  # скільки повідомлень тримаємо


class ConversationStore:
    def __init__(self, data_dir: Path):
        self.path = data_dir / "conversation.json"
        self._ensure()

    def _ensure(self):
        if not self.path.exists():
            self.path.write_text(json.dumps({"messages": []}, ensure_ascii=False, indent=2))

    def load(self) -> list[dict]:
        try:
            return json.loads(self.path.read_text()).get("messages", [])
        except Exception:
            return []

    def save(self, messages: list[dict]):
        self.path.write_text(
            json.dumps({"messages": messages}, ensure_ascii=False, indent=2)
        )

    def add(self, role: str, text: str):
        """role: 'user' або 'assistant'"""
        messages = self.load()
        messages.append({
            "role": role,
            "text": text,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        # тримаємо тільки останні N
        if len(messages) > MAX_MESSAGES:
            messages = messages[-MAX_MESSAGES:]
        self.save(messages)

    def to_messages(self) -> list[dict]:
        """Формат для Claude API (role + content)."""
        history = self.load()
        return [{"role": m["role"], "content": m["text"]} for m in history]

    def to_context_string(self) -> str:
        """Текстовий формат для вставки в промпт."""
        history = self.load()
        if not history:
            return ""
        lines = ["💬 Попередні повідомлення цієї розмови:"]
        for m in history:
            prefix = "Користувач" if m["role"] == "user" else "Ти"
            lines.append(f"[{m.get('time','')}] {prefix}: {m['text']}")
        return "\n".join(lines)
