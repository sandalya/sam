"""Sam curriculum — Phase 2.2: /cur_add і /done на v2 через shared.curriculum.

Інші команди (/cur, /cur_item, /start_topic, handle_curriculum_callback) лишаються
як shim-делегація до SamCurriculum (legacy CurriculumEngine), щоб main.py і
notebooklm.py / podcast.py продовжували працювати до Phase 2.3+.

CURRICULUM — legacy-константа, ще потрібна для shared.notebooklm_module і
shared.podcast_module (Phase 2.3 / 2.4 приберуть їх залежність).
"""
import json
import logging
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.agent_base import client, MODEL_SMART
from shared.curriculum import (
    load, save,
    add_topic, add_island, set_topic_state,
    CurriculumState,
)
from shared.curriculum_engine import CurriculumEngine
from shared.curriculum_engine import FORMAT_NAMES, NOTEBOOKLM_FORMATS  # noqa: F401 — re-export для main.py

from .base import SAM_PERSONA, DATA_DIR, PROFILE_PATH

log = logging.getLogger("sam.curriculum")

CURRICULUM_V2_PATH = DATA_DIR / "curriculum.json"

# ── Legacy CURRICULUM (ще юзається notebooklm.py та podcast.py) ──────────────
CURRICULUM = [
    {"id": 1, "title": "Tool Use / Function Calling", "category": "CLAUDE", "estimate": "1-2 дні",
     "why": "Ти вже робиш це вручну через JSON. Нативний tool use — інший рівень контролю.",
     "read": "https://docs.anthropic.com/en/docs/build-with-claude/tool-use",
     "do": "Переписати один action з Meggy (add_to_shopping) на нативний tool use."},
    {"id": 2, "title": "Agentic Loops", "category": "AGENT", "estimate": "2-3 дні",
     "why": "Агент що сам вирішує скільки кроків зробити — це якісний стрибок від бота.",
     "read": "https://www.anthropic.com/research/building-effective-agents",
     "do": "Додати в Sam модуль що сам вирішує — одного пошуку достатньо чи треба ще."},
    {"id": 3, "title": "Evals", "category": "AGENT", "estimate": "1-2 дні",
     "why": "Без evals не знаєш чи агент став кращим або гіршим після змін.",
     "read": "https://platform.claude.com/docs/en/test-and-evaluate/develop-tests",
     "do": "Написати 10 тест-кейсів для InSilver з очікуваною відповіддю і score функцією."},
    {"id": 4, "title": "RAG — Retrieval Augmented Generation", "category": "AGENT", "estimate": "3-4 дні",
     "why": "Векторний пошук замість grep — агент знаходить релевантне навіть при неточному запиті.",
     "read": "https://docs.anthropic.com/en/docs/build-with-claude/embeddings",
     "do": "Додати chromadb в InSilver knowledge.py. Локально, безкоштовно."},
    {"id": 5, "title": "Multi-agent координація", "category": "AGENT", "estimate": "3-5 днів",
     "why": "Оркестратор + субагенти — архітектура складних продуктів.",
     "read": "https://www.anthropic.com/engineering/multi-agent-research-system",
     "do": "Sam делегує дизайн-питання Abby і повертає відповідь."},
]


# ── SamCurriculum (legacy shim для /cur_item, /start_topic, callback) ─────────
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

    async def _after_state_change(self, chat_id: int, bot) -> None:
        from .pinned import refresh_pinned, load_state as load_pin_state
        pin_state = load_pin_state(self.data_dir)
        if not pin_state.get("message_id"):
            return
        await refresh_pinned(bot, chat_id, self.data_dir)


_instance_cache: dict[int, SamCurriculum] = {}

def _get(owner_chat_id: int = 0) -> SamCurriculum:
    if owner_chat_id not in _instance_cache:
        _instance_cache[owner_chat_id] = SamCurriculum(owner_chat_id)
    return _instance_cache[owner_chat_id]


def load_state():
    """Legacy state-loader для notebooklm/podcast модулів що ще на legacy engine."""
    return _get().load_state()


# ── Allowed content styles ───────────────────────────────────────────────────
_CONTENT_STYLES = {"audio", "visual"}


# ── LLM: визначення острова і метаданих для нової теми ──────────────────────

_CUR_ADD_SYSTEM_PROMPT = """You are a curriculum architect. A learner is adding a new topic to their AI learning curriculum.

Given:
- The learner's learning_vector (their focus)
- The list of EXISTING islands (semantic groups) with descriptions
- The new topic title they want to add

Your job:
1. Decide which existing island this topic fits best. Use the island's id (slug).
2. If NO existing island fits (topic is in a new area) — propose a new island with id/title/description.
3. Fill in reasonable defaults for the topic: why, read (URL to authoritative docs/article), do (practical task), estimate, content_style.

Return STRICT JSON with this exact shape:

{
  "island_id": "existing_island_slug_or_null",
  "suggested_new_island": null | {"id": "snake_case_slug", "title": "Human Title", "description": "1-2 sentences"},
  "why": "1-2 sentences why this is worth learning given the learner's focus",
  "read": "https://... (concrete article URL, not a landing page)",
  "do": "one concrete practical task — short, actionable",
  "estimate": "1-2 дні" | "2-3 дні" | "3-5 днів" | "тиждень",
  "content_style": "audio" | "visual"
}

RULES:
- Exactly ONE of island_id or suggested_new_island must be non-null.
- If suggested_new_island — its id must be snake_case ASCII, unique (not match existing).
- Default to content_style="audio" unless the topic is heavily visual (diagrams, architectures, code walkthroughs).
- Keep why/do in the same language as the topic title.
- read must be a real, specific URL (Anthropic docs, arXiv, reputable blogs). Not "https://example.com".

Return ONLY the JSON. No prose, no markdown fences.
"""


def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _enrich_topic_via_llm(state: CurriculumState, title: str) -> dict:
    """Викликає LLM для визначення острова + метаданих нової теми."""
    islands_desc = "\n".join(
        f"  - {i.id}: {i.title} — {i.description}"
        for i in sorted(state.islands, key=lambda x: x.order)
    )
    existing_slugs = {i.id for i in state.islands}

    user_prompt = (
        f"LEARNING_VECTOR:\n{state.learning_vector or '(not set)'}\n\n"
        f"EXISTING_ISLANDS:\n{islands_desc}\n\n"
        f"NEW_TOPIC_TITLE: {title}\n\n"
        f"Produce the JSON."
    )

    log.info(f"LLM enrich for new topic: {title!r}")
    response = client.messages.create(
        model=MODEL_SMART,
        max_tokens=1000,
        system=_CUR_ADD_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    text = _strip_fence(text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        log.error(f"LLM returned invalid JSON: {text[:400]}")
        raise ValueError(f"LLM returned invalid JSON: {e}") from e

    # Нормалізація / валідація
    island_id = data.get("island_id")
    new_island = data.get("suggested_new_island")

    if island_id and new_island:
        # Обираємо existing, ігноруємо new
        new_island = None
    if not island_id and not new_island:
        # Fallback: перший острів по order
        island_id = sorted(state.islands, key=lambda x: x.order)[0].id
        log.warning(f"LLM returned neither island_id nor new island, fallback to {island_id}")

    if island_id and island_id not in existing_slugs:
        # LLM вигадав неіснуючий slug — переганяємо в suggested_new_island
        log.warning(f"LLM returned unknown island_id={island_id!r}, treating as new")
        new_island = {
            "id": island_id,
            "title": island_id.replace("_", " ").title(),
            "description": f"Auto-created for topic: {title}",
        }
        island_id = None

    style = data.get("content_style", "audio")
    if style not in _CONTENT_STYLES:
        style = "audio"

    return {
        "island_id": island_id,
        "suggested_new_island": new_island,
        "why": str(data.get("why", "")).strip(),
        "read": str(data.get("read", "")).strip(),
        "do": str(data.get("do", "")).strip(),
        "estimate": str(data.get("estimate", "1-2 дні")).strip(),
        "content_style": style,
    }


# ── cmd_cur_add (v2) ─────────────────────────────────────────────────────────

async def cmd_cur_add(update, context):
    """Додає нову тему в curriculum_v2.json. LLM визначає острів і метадані."""
    args = context.args
    if not args:
        await update.message.reply_text(
            "Використання: /cur_add Назва теми\n"
            "Приклад: /cur_add Context Management & Memory Patterns"
        )
        return

    title = " ".join(args).strip()
    state = load(CURRICULUM_V2_PATH)

    try:
        enriched = _enrich_topic_via_llm(state, title)
    except Exception as e:
        log.error(f"cur_add LLM enrich failed: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Не вдалось визначити острів для теми через LLM: {e}\n"
            f"Спробуй ще раз або додай руками."
        )
        return

    # Створюємо новий острів якщо треба
    island_id = enriched["island_id"]
    if not island_id and enriched["suggested_new_island"]:
        new_is = enriched["suggested_new_island"]
        try:
            add_island(
                state,
                island_id=new_is["id"],
                title=new_is["title"],
                description=new_is["description"],
            )
            island_id = new_is["id"]
            log.info(f"Created new island: {island_id}")
        except ValueError as e:
            await update.message.reply_text(f"❌ Не вдалось створити острів: {e}")
            return

    # Додаємо тему (state=active одразу — користувач додав явно)
    try:
        topic = add_topic(
            state,
            island_id=island_id,
            title=title,
            why=enriched["why"],
            read=enriched["read"],
            do=enriched["do"],
            estimate=enriched["estimate"],
            content_style=enriched["content_style"],
            initial_state="active",
        )
    except ValueError as e:
        await update.message.reply_text(f"❌ Не вдалось додати тему: {e}")
        return

    save(state, CURRICULUM_V2_PATH)
    log.info(f"Topic added: {topic.id} in island {island_id}")

    # Знаходимо title острова для повідомлення
    island = state.get_island(island_id)
    island_title = island.title if island else island_id

    msg = (
        f"✅ Додано тему\n\n"
        f"📘 <b>{topic.title}</b>\n"
        f"🏝 Острів: {island_title}\n"
        f"🎯 {topic.content_style} · {topic.estimate}\n"
        f"🆔 <code>{topic.id}</code>\n\n"
    )
    if topic.why:
        msg += f"💡 {topic.why}\n"
    if topic.read:
        msg += f"📖 {topic.read}\n"
    if topic.do:
        msg += f"🛠 {topic.do}\n"
    msg += "\nВикористай /cur щоб побачити оновлений план."

    await update.message.reply_text(msg, parse_mode="HTML", disable_web_page_preview=True)

    # Refresh pinned (silent — не ламає flow)
    try:
        from .pinned import refresh_pinned, load_state as load_pin_state
        pin_state = load_pin_state(DATA_DIR)
        if pin_state.get("message_id"):
            await refresh_pinned(update.get_bot(), update.effective_chat.id, DATA_DIR)
    except Exception as e:
        log.warning(f"pinned refresh after cur_add failed: {e}")


# ── cmd_done (v2) ────────────────────────────────────────────────────────────

def _resolve_topic_id(state: CurriculumState, arg: str) -> Optional[str]:
    """
    Приймає:
      - новий str id: "agent_architecture-3"
      - числовий legacy_id: "2" → шукаємо topic з legacy_id=2
    Повертає v2 topic.id або None.
    """
    # Спочатку пряме співпадіння
    if state.get_topic(arg):
        return arg
    # Legacy int
    if arg.isdigit():
        lid = int(arg)
        t = next((t for t in state.topics if t.legacy_id == lid), None)
        if t:
            return t.id
    return None


async def cmd_done(update, context):
    """Позначити тему як mastered. /done <topic_id> або /done <legacy_int_id>."""
    args = context.args
    if not args:
        await update.message.reply_text(
            "Використання: /done <topic_id>\n"
            "Приклад: /done agent_architecture-3  або  /done 2"
        )
        return

    state = load(CURRICULUM_V2_PATH)
    tid = _resolve_topic_id(state, args[0])
    if not tid:
        await update.message.reply_text(f"Тема {args[0]!r} не існує в curriculum_v2.json.")
        return

    topic = state.get_topic(tid)
    prev_state = topic.state
    set_topic_state(state, tid, "mastered")
    save(state, CURRICULUM_V2_PATH)
    log.info(f"Topic mastered: {tid} ({prev_state} → mastered)")

    counts = state.counts()
    island = state.get_island(topic.island_id)
    island_title = island.title if island else topic.island_id

    msg = (
        f"✅ <b>{topic.title}</b> — засвоєно!\n"
        f"🏝 {island_title}\n\n"
        f"📊 Прогрес: {counts['mastered']}/{counts['total']} "
        f"(active: {counts['active']}, pending: {counts['pending']})"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

    # Refresh pinned
    try:
        from .pinned import refresh_pinned, load_state as load_pin_state
        pin_state = load_pin_state(DATA_DIR)
        if pin_state.get("message_id"):
            await refresh_pinned(update.get_bot(), update.effective_chat.id, DATA_DIR)
    except Exception as e:
        log.warning(f"pinned refresh after done failed: {e}")


# ── Legacy shims (делегують в SamCurriculum) ─────────────────────────────────

async def cmd_curriculum(update, context):
    """Не зареєстрований у main.py, залишаємо shim на всяк."""
    inst = _get(update.effective_user.id)
    await inst.cmd_curriculum(update, context)

async def cmd_curriculum_item(update, context):
    inst = _get(update.effective_user.id)
    await inst.cmd_curriculum(update, context)

async def cmd_start_topic(update, context):
    pass  # legacy, не використовується

async def handle_curriculum_callback(update, context):
    """Legacy callback (cur_|...). У main.py не зареєстрований, залишаємо shim."""
    inst = _get(update.effective_user.id)
    await inst.handle_curriculum_callback(update, context)
