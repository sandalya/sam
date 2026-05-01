import asyncio
import json
import logging
import re

from curriculum.models import ContentBrief

log = logging.getLogger("core.content_gen.brief")

_BRIEF_SYSTEM = (
    "You are a content analyst. Analyze the given learning resource and return a structured JSON brief. "
    "Output JSON only — no markdown, no preamble, no code fences."
)

_BRIEF_PROMPT = """Analyze this learning resource and produce a content brief for NotebookLM generation.

Title: {title}
Source: {source_url}
{extra_block}Preset angle: {angle}

Return JSON with exactly these fields:
{{
  "key_concepts": ["concept1", "concept2"],
  "focus_questions": ["question1?", "question2?"],
  "suggested_angle": "one sentence on how to approach this content",
  "suggested_instructions": "2-4 sentences of NotebookLM instructions in English, action-verb opening, tailored for an experienced AI/backend developer",
  "source_summary": "1-2 sentence factual description of what this source covers"
}}

Requirements:
- key_concepts: 3-6 items, non-empty
- focus_questions: 2-4 items, non-empty, end with ?
- suggested_instructions: must be non-empty, start with an action verb (Focus, Explore, Cover, etc.)
- source_summary: factual, specific to this content"""


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
        angle=preset_angle or "balanced overview",
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
        focus_questions = [f"What are the key takeaways from {title}?"]
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
