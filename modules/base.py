import json
import os
import sys
from pathlib import Path

import anthropic

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR.parent))
from shared.agent_base import AgentBase, client, MODEL_SMART, MODEL_FAST  # noqa: F401

def _load_ecosystem() -> str:
    p = BASE_DIR / "ECOSYSTEM.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""
PROFILE_PATH = BASE_DIR / "profile.json"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MODEL_SMART = "claude-sonnet-4-20250514"   # пошук, складні відповіді
MODEL_FAST  = "claude-haiku-4-5-20251001"  # прості відповіді, curriculum, onboarding

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

Про свої дані:
- В системному промпті ти отримуєш живий стан Саші: поточна дата, які теми в curriculum активні/завершені, остання активність.
- Це і є твій "доступ" до його прогресу — не треба просити команди або додаткову інформацію.
- Якщо бачиш "📚 Зараз вивчає: X" — відповідай впевнено що Саша зараз на темі X.
- Не кажи "не маю доступу" якщо інформація є в контексті. Просто відповідай.
-Ніколи не пропонуй команду "/curriculum status" — такої команди не існує. Для деталей по темі є /cur.

""" + _load_ecosystem()



class BaseModule(AgentBase):
    """
    Базовий клас для модулів Sam — тепер через AgentBase (спільний з Garcia).
    """

    def __init__(self, owner_chat_id: int):
        super().__init__(
            owner_chat_id=owner_chat_id,
            persona=SAM_PERSONA,
            data_dir=DATA_DIR,
            profile_path=PROFILE_PATH,
        )

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
        """Викликає Claude Sonnet з web_search (складні/актуальні теми)."""
        response = client.messages.create(
            model=MODEL_SMART,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": SAM_PERSONA, "cache_control": {"type": "ephemeral"}}],
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )
        return "\n".join(b.text for b in response.content if b.type == "text")

    def call_claude(self, prompt: str, max_tokens: int = 1024, smart: bool = False) -> str:
        """Викликає Claude. smart=True → Sonnet, інакше Haiku (дешевше)."""
        model = MODEL_SMART if smart else MODEL_FAST
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": SAM_PERSONA, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
        )
        return "\n".join(b.text for b in response.content if b.type == "text")

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

# Імпортуємо curriculum список для snapshot
def _get_curriculum_list():
    try:
        from modules.curriculum import CURRICULUM
        return CURRICULUM
    except Exception:
        return []

# Патчимо BaseModule щоб знав назви тем
_orig_snapshot = BaseModule._build_context_snapshot

def _sam_snapshot(self):
    self.CURRICULUM = _get_curriculum_list()
    return _orig_snapshot(self)

BaseModule._build_context_snapshot = _sam_snapshot
