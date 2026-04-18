"""
shared/curriculum/islands.py — логіка островів для міграції.

Відповідає за:
1. REFERENCE_ISLANDS — hardcoded базовий список островів AI-learning
2. cluster_topics_for_migration() — LLM-пропозиція як згрупувати існуючі
   теми в острови з врахуванням learning_vector та референсу
3. determine_content_style() — для кожної теми: audio-first чи visual-first

Використовує shared.agent_base.client (той самий Anthropic-клієнт що Sam).
Всі LLM-виклики логують токени і повертають structured output.

Референс: workspace/sam/docs/DATA_MODEL.md (крок 4 і 6 міграції)
         workspace/sam/docs/BOOTSTRAP_DIALOG.md (Акт 3 і Акт 4)
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from shared.agent_base import client, MODEL_SMART

from .models import ContentStyle

log = logging.getLogger("shared.curriculum.islands")


# ─── REFERENCE_ISLANDS ────────────────────────────────────────────────────────

# Базовий список островів AI-learning. LLM може:
#  - використовувати ці ID/назви
#  - переіменовувати під специфіку користувача
#  - додавати нові острови якщо теми не вписуються
#  - опускати ті що не потрібні
#
# Формат: (slug, title, description)

REFERENCE_ISLANDS: list[tuple[str, str, str]] = [
    ("foundations", "LLM Foundations",
     "Трансформери, attention, training, scaling laws, архітектура LLM"),
    ("prompting", "Prompting & Context Engineering",
     "Промпт-дизайн, few-shot, chain-of-thought, context management"),
    ("tool_use", "Tool Use & Function Calling",
     "Інтеграція LLM з зовнішніми інструментами, structured outputs"),
    ("agents", "AI Agents",
     "Agentic loops, multi-step reasoning, planning, автономні агенти"),
    ("multi_agent", "Multi-Agent Systems",
     "Оркестрація, комунікація між агентами, розподіл задач"),
    ("rag", "RAG & Retrieval",
     "Векторний пошук, embeddings, chunking, hybrid search, knowledge bases"),
    ("evals", "Evaluations & Testing",
     "Бенчмарки, автоеволи, regression testing, оцінка якості AI-систем"),
    ("production", "Production AI Systems",
     "Надійність, моніторинг, cost optimization, error handling, deployment"),
    ("safety", "AI Safety & Alignment",
     "RLHF, red-teaming, безпека, alignment, відповідальний AI"),
    ("interpretability", "Interpretability",
     "Розуміння внутрішніх процесів моделі, mechanistic interpretability"),
    ("fine_tuning", "Fine-tuning & Customization",
     "SFT, LoRA, adapters, constitutional AI, кастомізація моделей"),
    ("privacy", "Privacy & Security",
     "PII, дані користувачів, security в AI-продуктах"),
]


# ─── Результат кластеризації ──────────────────────────────────────────────────

@dataclass
class IslandProposal:
    """Один острів з пропозиції."""
    id: str                # slug
    title: str
    description: str
    topic_legacy_ids: list[int] = field(default_factory=list)  # які теми туди йдуть
    is_gap: bool = False   # True якщо острів запропонований як "прогалина"
                           # (тобто має бути створений, але тем зараз в ньому нема)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "topic_legacy_ids": list(self.topic_legacy_ids),
            "is_gap": self.is_gap,
        }


@dataclass
class ClusteringProposal:
    """Повний результат LLM-кластеризації для міграції."""
    islands: list[IslandProposal]
    reasoning: str = ""  # пояснення LLM чому саме так

    def populated_islands(self) -> list[IslandProposal]:
        return [i for i in self.islands if not i.is_gap]

    def gap_islands(self) -> list[IslandProposal]:
        return [i for i in self.islands if i.is_gap]

    def assignment_map(self) -> dict[int, str]:
        """legacy_id -> island_id"""
        out: dict[int, str] = {}
        for island in self.islands:
            for lid in island.topic_legacy_ids:
                out[lid] = island.id
        return out

    def to_dict(self) -> dict:
        return {
            "islands": [i.to_dict() for i in self.islands],
            "reasoning": self.reasoning,
        }


# ─── LLM-промпт для кластеризації ─────────────────────────────────────────────

_CLUSTERING_SYSTEM_PROMPT = """You are a curriculum architect for an AI learning assistant.
Your task is to organize the user's existing learning topics into meaningful "islands"
(semantic groups) that reflect how AI knowledge naturally clusters.

You will receive:
- The user's learning_vector (their focus direction)
- A list of existing topics they've been studying
- A reference list of common AI-learning islands

You must return a STRICT JSON object with this exact shape:

{
  "reasoning": "1-3 sentences explaining the overall structure you chose",
  "islands": [
    {
      "id": "snake_case_slug",
      "title": "Human Readable Title",
      "description": "1-2 sentences about what belongs here",
      "topic_legacy_ids": [1, 2, 3],
      "is_gap": false
    }
  ]
}

RULES:
- Every topic_legacy_id from the input MUST appear in exactly one island.
- You may rename/merge/split reference islands if the user's topics suggest a better structure.
- You MAY create new islands not in the reference if topics demand it.
- You MAY propose "gap" islands with is_gap=true AND empty topic_legacy_ids[] — these represent
  important AI-learning areas the user has no topics in yet. Propose 1-3 gaps max, and only
  ones genuinely relevant to their learning_vector.
- Aim for 4-8 populated islands. Fewer if topics are narrow, more if broad.
- Don't over-categorize — 1-topic islands are fine if a topic truly doesn't fit elsewhere,
  but prefer grouping when meaningful.
- IDs must be snake_case slugs (ASCII, no spaces, no special chars).
- Titles can have spaces, can be in English regardless of topic language.

Return ONLY the JSON object. No prose before or after. No markdown code fences.
"""


def _format_reference_for_prompt() -> str:
    lines = []
    for slug, title, desc in REFERENCE_ISLANDS:
        lines.append(f"  - {slug}: {title} — {desc}")
    return "\n".join(lines)


def _format_topics_for_prompt(topics: list[dict]) -> str:
    """topics — список dict з полями id (int), title, why, category (опц)."""
    lines = []
    for t in topics:
        parts = [f"id={t['id']}: {t['title']}"]
        if t.get("why"):
            parts.append(f"  why: {t['why']}")
        if t.get("category"):
            parts.append(f"  category: {t['category']}")
        lines.append("\n".join(parts))
    return "\n\n".join(lines)


# ─── Головна функція кластеризації ────────────────────────────────────────────

def cluster_topics_for_migration(
    topics: list[dict],
    learning_vector: str,
    *,
    max_tokens: int = 3000,
) -> ClusteringProposal:
    """
    Викликає LLM для пропозиції структури островів на основі існуючих тем.

    Args:
        topics: список dict з полями {id: int, title: str, why: str, category?: str}
                id — це legacy integer ID з curriculum_dynamic.json / CURRICULUM
        learning_vector: текстовий опис напрямку користувача
        max_tokens: ліміт для LLM-відповіді (3000 вистачає для ~20 тем і 8 островів)

    Returns:
        ClusteringProposal з islands і reasoning.

    Raises:
        ValueError якщо LLM повернув невалідний JSON або структуру.
    """
    if not topics:
        raise ValueError("Cannot cluster empty topics list")

    user_prompt = (
        f"LEARNING_VECTOR:\n{learning_vector or '(not specified)'}\n\n"
        f"EXISTING_TOPICS ({len(topics)}):\n{_format_topics_for_prompt(topics)}\n\n"
        f"REFERENCE_ISLANDS:\n{_format_reference_for_prompt()}\n\n"
        f"Now produce the JSON."
    )

    log.info(
        f"Calling LLM for island clustering: {len(topics)} topics, "
        f"vector={learning_vector!r:.80}"
    )

    response = client.messages.create(
        model=MODEL_SMART,
        max_tokens=max_tokens,
        system=_CLUSTERING_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text = "".join(b.text for b in response.content if b.type == "text").strip()

    # LLM іноді обертає в ```json ... ``` — зчищаємо
    text = _strip_code_fence(text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        log.error(f"LLM returned invalid JSON: {text[:500]}")
        raise ValueError(f"Clustering LLM returned invalid JSON: {e}") from e

    proposal = _parse_clustering_response(data, topics)
    _validate_clustering(proposal, topics)
    return proposal


def _strip_code_fence(text: str) -> str:
    """Прибирає ```json ... ``` обгортку якщо є."""
    text = text.strip()
    if text.startswith("```"):
        # віддаляємо першу лінію з ``` і останню
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _parse_clustering_response(data: dict, topics: list[dict]) -> ClusteringProposal:
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object, got {type(data).__name__}")

    raw_islands = data.get("islands", [])
    if not isinstance(raw_islands, list):
        raise ValueError("'islands' must be a list")

    islands: list[IslandProposal] = []
    for i, raw in enumerate(raw_islands):
        if not isinstance(raw, dict):
            raise ValueError(f"Island {i} must be an object")
        try:
            islands.append(IslandProposal(
                id=str(raw["id"]),
                title=str(raw["title"]),
                description=str(raw.get("description", "")),
                topic_legacy_ids=[int(x) for x in raw.get("topic_legacy_ids", [])],
                is_gap=bool(raw.get("is_gap", False)),
            ))
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"Island {i} malformed: {e}") from e

    return ClusteringProposal(
        islands=islands,
        reasoning=str(data.get("reasoning", "")),
    )


def _validate_clustering(proposal: ClusteringProposal, topics: list[dict]) -> None:
    """Перевіряє що кожна тема потрапила рівно в один non-gap острів."""
    input_ids = {int(t["id"]) for t in topics}
    assigned_ids: list[int] = []
    for island in proposal.islands:
        if island.is_gap and island.topic_legacy_ids:
            raise ValueError(
                f"Gap island {island.id!r} must have empty topic_legacy_ids"
            )
        assigned_ids.extend(island.topic_legacy_ids)

    assigned_set = set(assigned_ids)

    missing = input_ids - assigned_set
    if missing:
        raise ValueError(
            f"LLM didn't assign all topics to islands. Missing: {sorted(missing)}"
        )

    extra = assigned_set - input_ids
    if extra:
        raise ValueError(
            f"LLM assigned unknown topic IDs: {sorted(extra)}"
        )

    duplicates = [i for i in assigned_ids if assigned_ids.count(i) > 1]
    if duplicates:
        raise ValueError(
            f"LLM assigned topics to multiple islands: {sorted(set(duplicates))}"
        )

    # Slugs unique
    slugs = [i.id for i in proposal.islands]
    if len(slugs) != len(set(slugs)):
        dupes = [s for s in slugs if slugs.count(s) > 1]
        raise ValueError(f"Duplicate island ids: {sorted(set(dupes))}")

    # Slugs valid (snake_case, no whitespace/special)
    for slug in slugs:
        if not re.match(r"^[a-z][a-z0-9_]*$", slug):
            raise ValueError(f"Invalid island id {slug!r} — must be snake_case ASCII")


# ─── Визначення content_style ─────────────────────────────────────────────────

_CONTENT_STYLE_SYSTEM_PROMPT = """You classify AI learning topics by their optimal
consumption style:

- "audio" — concept-heavy, narrative, can be understood by listening
  (theory, history, high-level explanations, philosophical/abstract topics)
- "visual" — requires seeing diagrams, architectures, code, matrices,
  spatial relationships (system designs, architectural patterns, graph structures,
  flow diagrams, code-heavy topics)

You will receive a list of topics. Return a STRICT JSON object:

{
  "assignments": [
    {"id": "<topic_id_as_string>", "style": "audio"},
    {"id": "<topic_id_as_string>", "style": "visual"}
  ]
}

RULES:
- Every topic ID from input must appear in output.
- Only "audio" or "visual", no other values.
- Default to "audio" when uncertain — visual-first is a strong statement.
- Return IDs as STRINGS even if input has integers.

Return ONLY the JSON. No prose, no markdown fences.
"""


def determine_content_style(
    topics: list[dict],
    *,
    max_tokens: int = 2000,
) -> dict[str, ContentStyle]:
    """
    Один LLM-виклик для визначення content_style всіх тем.

    Args:
        topics: список dict з полями {id, title, why?}.
                id може бути int або str — повертається як str в output.

    Returns:
        dict {topic_id_as_string: "audio" | "visual"}
    """
    if not topics:
        return {}

    lines = []
    for t in topics:
        tid = t["id"]
        line = f"id={tid}: {t['title']}"
        if t.get("why"):
            line += f" — {t['why']}"
        lines.append(line)
    topics_text = "\n".join(lines)

    log.info(f"Calling LLM for content_style on {len(topics)} topics")

    response = client.messages.create(
        model=MODEL_SMART,
        max_tokens=max_tokens,
        system=_CONTENT_STYLE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"TOPICS:\n{topics_text}"}],
    )

    text = "".join(b.text for b in response.content if b.type == "text").strip()
    text = _strip_code_fence(text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        log.error(f"LLM returned invalid JSON for content_style: {text[:500]}")
        raise ValueError(f"Content style LLM returned invalid JSON: {e}") from e

    assignments = data.get("assignments", [])
    if not isinstance(assignments, list):
        raise ValueError("'assignments' must be a list")

    out: dict[str, ContentStyle] = {}
    for item in assignments:
        if not isinstance(item, dict):
            continue
        tid = str(item.get("id", "")).strip()
        style = item.get("style", "audio")
        if style not in ("audio", "visual"):
            log.warning(f"Topic {tid}: invalid style {style!r}, defaulting to audio")
            style = "audio"
        if tid:
            out[tid] = style  # type: ignore[assignment]

    # Fallback для пропущених тем
    input_ids = {str(t["id"]) for t in topics}
    missing = input_ids - set(out.keys())
    if missing:
        log.warning(f"LLM skipped {len(missing)} topics, defaulting to audio: {missing}")
        for tid in missing:
            out[tid] = "audio"

    return out
