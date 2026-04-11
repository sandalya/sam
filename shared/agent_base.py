"""
shared/agent_base.py — базовий клас для Sam і Garcia (і майбутніх навчальних агентів).
Містить: Claude client, profile I/O, call_claude, parse_json_response.
"""
import json
import os
from pathlib import Path

import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MODEL_SMART = "claude-sonnet-4-20250514"
MODEL_FAST  = "claude-haiku-4-5-20251001"


class AgentBase:
    """
    Базовий клас. Агент успадковує і задає:
      - self.owner_chat_id
      - self.persona  (str — системний промпт)
      - self.data_dir (Path — куди зберігати дані)
      - self.profile_path (Path — profile.json)
    """

    def __init__(self, owner_chat_id: int, persona: str, data_dir: Path, profile_path: Path):
        self.owner_chat_id = owner_chat_id
        self.persona = persona
        self.data_dir = data_dir
        self.profile_path = profile_path
        self.data_dir.mkdir(exist_ok=True)

    # ── Profile ────────────────────────────────────────────────────────────────

    def load_profile(self) -> dict:
        if self.profile_path.exists():
            data = json.loads(self.profile_path.read_text())
            data.setdefault("interests", [])
            data.setdefault("curriculum_hints", [])
            return data
        return {"scores": {}, "notes": [], "interests": [], "curriculum_hints": []}

    def save_profile(self, profile: dict):
        self.profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2))

    def update_score(self, topic_key: str, delta: int):
        profile = self.load_profile()
        profile["scores"][topic_key] = profile["scores"].get(topic_key, 0) + delta
        self.save_profile(profile)

    def update_interests(self, new_interests: list[str]):
        if not new_interests:
            return
        profile = self.load_profile()
        existing = set(i.lower() for i in profile["interests"])
        for item in new_interests:
            if item.lower() not in existing:
                profile["interests"].append(item)
                existing.add(item.lower())
        self.save_profile(profile)

    def add_note(self, note: str):
        profile = self.load_profile()
        profile["notes"].append(note)
        self.save_profile(profile)

    def profile_to_context(self) -> str:
        profile = self.load_profile()
        if not profile.get("scores") and not profile.get("notes"):
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
        if profile.get("notes"):
            lines.append(f"Побажання: {'; '.join(profile['notes'][-5:])}")
        return "\n".join(lines)

    # ── Claude API ─────────────────────────────────────────────────────────────

    def call_claude_with_search(self, prompt: str, max_tokens: int = 2000) -> str:
        response = client.messages.create(
            model=MODEL_SMART,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": self.persona, "cache_control": {"type": "ephemeral"}}],
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )
        return "\n".join(b.text for b in response.content if b.type == "text")

    def call_claude(self, prompt: str, max_tokens: int = 1024, smart: bool = False) -> str:
        model = MODEL_SMART if smart else MODEL_FAST
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": self.persona, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
        )
        return "\n".join(b.text for b in response.content if b.type == "text")

    def parse_json_response(self, raw: str) -> list:
        import re, json as _json
        clean = raw.strip()
        if clean.startswith("```"):
            parts = clean.split("```")
            clean = parts[1] if len(parts) > 1 else clean
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip()
        try:
            result = _json.loads(clean)
            return result if isinstance(result, list) else []
        except _json.JSONDecodeError:
            match = re.search(r'\[.*\]', clean, re.DOTALL)
            if match:
                try:
                    return _json.loads(match.group())
                except Exception:
                    pass
        return []
