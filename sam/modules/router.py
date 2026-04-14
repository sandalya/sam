import json
import logging
from anthropic import Anthropic
import os

logger = logging.getLogger("sam")

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

ROUTER_SYSTEM = """Ти — маршрутизатор повідомлень для навчального бота Sam.
Визнач intent і поверни ТІЛЬКИ JSON, без пояснень.

Intents:
- "curriculum" — курикулум, теми, прогрес навчання
- "digest" — дайджест, новини AI
- "notebooks" — NotebookLM, подкаст, briefing, study guide
- "science" — запит на дайджест наукових новин (НЕ пояснення концепцій)
- "chat" — пояснення концепцій, питання типу "що таке X", "як працює Y", вільне спілкування
- "hub" — dashboard, де я, прогрес, хаб
- "catchup" — catchup, що пропустив
- "jobs" — вакансії, ринок праці
- "cost" — витрати, токени, cost
- "chat" — вільне спілкування

Формат: {"intent": "...", "topic": "...", "confidence": 0.0-1.0}
topic — ключові слова запиту або порожній рядок."""

def route_message(text: str) -> dict:
    """Визначає intent через дешевий API виклик."""
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            system=ROUTER_SYSTEM,
            messages=[{"role": "user", "content": text}],
        )
        content = response.content[0].text.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content.strip())
    except Exception as e:
        logger.warning(f"Router error: {e}")
        return {"intent": "chat", "topic": "", "confidence": 0.5}
