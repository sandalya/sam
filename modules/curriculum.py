"""Sam curriculum — план навчання AI."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.curriculum_engine import CurriculumEngine
from .base import SAM_PERSONA, DATA_DIR, PROFILE_PATH

# Re-export для main.py
from shared.curriculum_engine import FORMAT_NAMES, NOTEBOOKLM_FORMATS  # noqa: F401

CURRICULUM = [
    {"id": 1, "title": "Tool Use / Function Calling", "estimate": "1-2 дні",
     "why": "Ти вже робиш це вручну через JSON. Нативний tool use — інший рівень контролю.",
     "read": "https://docs.anthropic.com/en/docs/build-with-claude/tool-use",
     "do": "Переписати один action з Meggy (add_to_shopping) на нативний tool use."},
    {"id": 2, "title": "Agentic Loops", "estimate": "2-3 дні",
     "why": "Агент що сам вирішує скільки кроків зробити — це якісний стрибок від бота.",
     "read": "https://www.anthropic.com/research/building-effective-agents",
     "do": "Додати в Sam модуль що сам вирішує — одного пошуку достатньо чи треба ще."},
    {"id": 3, "title": "Evals", "estimate": "1-2 дні",
     "why": "Без evals не знаєш чи агент став кращим або гіршим після змін.",
     "read": "https://docs.anthropic.com/en/docs/build-with-claude/evals",
     "do": "Написати 10 тест-кейсів для InSilver з очікуваною відповіддю і score функцією."},
    {"id": 4, "title": "RAG — Retrieval Augmented Generation", "estimate": "3-4 дні",
     "why": "Векторний пошук замість grep — агент знаходить релевантне навіть при неточному запиті.",
     "read": "https://docs.anthropic.com/en/docs/build-with-claude/embeddings",
     "do": "Додати chromadb в InSilver knowledge.py. Локально, безкоштовно."},
    {"id": 5, "title": "Multi-agent координація", "estimate": "3-5 днів",
     "why": "Оркестратор + субагенти — архітектура складних продуктів.",
     "read": "https://docs.anthropic.com/en/docs/build-with-claude/multiagent-network",
     "do": "Sam делегує дизайн-питання Abby і повертає відповідь."},
]


class SamCurriculum(CurriculumEngine):
    notebooklm_context = (
        "Python developer building AI agents and Telegram bots with Anthropic API. "
        "Already in production, wants deeper theory and architecture."
    )
    dynamic_curriculum_prompt = (
        "You are a personalized AI curriculum designer. "
        "The learner is a Python developer building AI agents and Telegram bots with Anthropic API."
    )

    def __init__(self, owner_chat_id: int):
        super().__init__(
            owner_chat_id=owner_chat_id,
            persona=SAM_PERSONA,
            data_dir=DATA_DIR,
            profile_path=PROFILE_PATH,
        )
        self.CURRICULUM = CURRICULUM


# ── Backward-compat функції для main.py ───────────────────────────────────────

_instance_cache: dict[int, SamCurriculum] = {}

def _get(owner_chat_id: int = 0) -> SamCurriculum:
    if owner_chat_id not in _instance_cache:
        _instance_cache[owner_chat_id] = SamCurriculum(owner_chat_id)
    return _instance_cache[owner_chat_id]


async def cmd_curriculum(update, context):
    inst = _get(update.effective_user.id)
    await inst.cmd_curriculum(update, context)

async def cmd_curriculum_item(update, context):
    inst = _get(update.effective_user.id)
    # cmd_curriculum_item не в engine, просто показуємо /cur
    await inst.cmd_curriculum(update, context)

async def cmd_done(update, context):
    inst = _get(update.effective_user.id)
    await inst.cmd_done(update, context)

async def cmd_start_topic(update, context):
    pass  # не використовується активно

async def handle_curriculum_callback(update, context):
    inst = _get(update.effective_user.id)
    await inst.handle_curriculum_callback(update, context)

def load_state():
    return _get().load_state()
