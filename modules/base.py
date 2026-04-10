import json
import os
from pathlib import Path

import anthropic

BASE_DIR = Path(__file__).parent.parent
PROFILE_PATH = BASE_DIR / "profile.json"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


class BaseModule:
    """
    Базовий клас для модулів Sam.
    Кожен модуль має доступ до профілю і клієнта Anthropic.
    """

    def __init__(self, owner_chat_id: int):
        self.owner_chat_id = owner_chat_id

    # ── Profile ────────────────────────────────────────────────────────────────

    def load_profile(self) -> dict:
        if PROFILE_PATH.exists():
            return json.loads(PROFILE_PATH.read_text())
        return {"scores": {}, "notes": []}

    def save_profile(self, profile: dict):
        PROFILE_PATH.write_text(json.dumps(profile, ensure_ascii=False, indent=2))

    def update_score(self, topic_key: str, delta: int):
        profile = self.load_profile()
        profile["scores"][topic_key] = profile["scores"].get(topic_key, 0) + delta
        self.save_profile(profile)

    def add_note(self, note: str):
        profile = self.load_profile()
        profile["notes"].append(note)
        self.save_profile(profile)

    def profile_to_context(self) -> str:
        profile = self.load_profile()
        if not profile["scores"] and not profile["notes"]:
            return ""

        lines = ["Профіль інтересів користувача (враховуй при підборі новин):"]
        if profile["scores"]:
            sorted_t = sorted(profile["scores"].items(), key=lambda x: x[1], reverse=True)
            top = [t for t, s in sorted_t if s > 0]
            low = [t for t, s in sorted_t if s < 0]
            if top:
                lines.append(f"Подобається: {', '.join(top[:5])}")
            if low:
                lines.append(f"Не цікаво: {', '.join(low[:5])}")
        if profile["notes"]:
            lines.append(f"Побажання: {'; '.join(profile['notes'][-5:])}")

        return "\n".join(lines)

    # ── Claude API ─────────────────────────────────────────────────────────────

    def call_claude_with_search(self, prompt: str, max_tokens: int = 2000) -> str:
        """Викликає Claude з web_search, повертає текстову відповідь."""
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""

    def parse_json_response(self, raw: str) -> list:
        """Чистить і парсить JSON з відповіді Claude."""
        import re
        clean = raw.strip()
        if clean.startswith("```"):
            parts = clean.split("```")
            clean = parts[1] if len(parts) > 1 else clean
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip()
        try:
            result = json.loads(clean)
            return result if isinstance(result, list) else []
        except json.JSONDecodeError:
            match = re.search(r'\[.*\]', clean, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except Exception:
                    pass
        return []
