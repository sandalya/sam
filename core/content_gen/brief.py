import asyncio
import json
import logging
import re

from curriculum.models import ContentBrief

log = logging.getLogger("core.content_gen.brief")

_BRIEF_SYSTEM = (
    "Ти — контент-аналітик. Проаналізуй навчальний матеріал і поверни структурований JSON-brief. "
    "Виводь лише JSON — без markdown, без преамбули, без code fences."
)

_BRIEF_PROMPT = """Проаналізуй цей навчальний матеріал і сформуй content brief для генерації в NotebookLM.

Title: {title}
Source: {source_url}
{extra_block}Кут подачі (preset): {angle}

Поверни JSON з такими полями:
{{
  "key_concepts": ["концепція1", "концепція2"],
  "focus_questions": ["питання1?", "питання2?"],
  "suggested_angle": "одне речення про те, як підходити до цього матеріалу",
  "suggested_instructions": "2-4 речення інструкцій для NotebookLM українською, починається з дієслова-директиви, адаптовано для досвідченого AI/backend-розробника",
  "source_summary": "1-2 речення фактичного опису того, що охоплює це джерело"
}}

Вимоги:
- key_concepts: 3-6 елементів, не порожньо
- focus_questions: 2-4 елементи, не порожньо, закінчуються на ?
- suggested_instructions: не порожньо, починається з дієслова-директиви (Зосередься, Дослідь, Охопи тощо)
- source_summary: фактично, конкретно до цього матеріалу"""


async def generate_brief(entity, kind: str, preset_angle: str = "") -> ContentBrief:
    """Haiku pre-analysis. Returns ContentBrief. Falls back to safe defaults on any error."""
    from shared.agent_base import client, MODEL_FAST

    source_url = entity.source_url if kind == "article" else entity.read
    extra_block = ""
    if kind == "article" and getattr(entity, "summary", ""):
        extra_block = f"Summary: {entity.summary}\n"

    prompt = _BRIEF_PROMPT.format(
        title=entity.title,
        source_url=source_url or "(no URL)",
        extra_block=extra_block,
        angle=preset_angle or "збалансований огляд",
    )

    try:
        resp = await asyncio.to_thread(
            client.messages.create,
            model=MODEL_FAST,
            max_tokens=600,
            system=_BRIEF_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        data = _parse_json(raw)
        return _validate_and_build(data, entity.title, MODEL_FAST)
    except Exception as e:
        log.warning(f"generate_brief failed for {entity.id!r}: {e} — using fallback")
        return ContentBrief(
            suggested_instructions=entity.title,
            generated_by="fallback",
        )


def _parse_json(raw: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    text = re.sub(r"\s*```\s*$", "", text)
    return json.loads(text)


def _validate_and_build(data: dict, title: str, model: str) -> ContentBrief:
    key_concepts = [str(c) for c in data.get("key_concepts", []) if c]
    focus_questions = [str(q) for q in data.get("focus_questions", []) if q]
    suggested_instructions = str(data.get("suggested_instructions", "")).strip()

    if not key_concepts:
        key_concepts = [title]
    if not focus_questions:
        focus_questions = [f"Які ключові висновки з {title}?"]
    if not suggested_instructions:
        suggested_instructions = title

    return ContentBrief(
        key_concepts=key_concepts,
        focus_questions=focus_questions,
        suggested_angle=str(data.get("suggested_angle", "")),
        suggested_instructions=suggested_instructions,
        source_summary=str(data.get("source_summary", "")),
        generated_by=model,
    )
