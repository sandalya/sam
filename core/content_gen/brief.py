import asyncio
import json
import logging
import re

from curriculum.models import ContentBrief

log = logging.getLogger("core.content_gen.brief")


class BriefParseError(ValueError):
    def __init__(self, message, *, raw_text: str, cleaned_text: str, json_error: json.JSONDecodeError):
        super().__init__(message)
        self.raw_text = raw_text
        self.cleaned_text = cleaned_text
        self.json_error = json_error

_BRIEF_SYSTEM = (
    "You are a content analyst. Analyze the learning material and return a structured "
    "JSON brief. Output JSON only — no markdown, no preamble, no code fences."
)

_BRIEF_PROMPT = """Analyze this learning material and produce a content brief for NotebookLM generation.

Title: {title}
Source: {source_url}
{extra_block}Angle (preset): {angle}

Return JSON with these fields:
{{
  "key_concepts": ["concept1", "concept2"],
  "focus_questions": ["question1?", "question2?"],
  "suggested_angle": "one sentence on how to approach this material",
  "suggested_instructions": "2-4 sentences of instructions for NotebookLM in English, starts with an imperative verb (Explore, Analyze, Examine, etc.), tailored for an experienced AI/backend developer",
  "source_summary": "1-2 sentences factually describing what this source covers"
}}

Requirements:
- key_concepts: 3-6 items, non-empty
- focus_questions: 2-4 items, non-empty, end with ?
- suggested_instructions: non-empty, starts with an imperative verb (Explore, Analyze, Examine, Focus, etc.)
- source_summary: factual, specific to this material"""


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
    except BriefParseError as e:
        log.error(
            "BRIEF JSON PARSE FAIL\nraw_len=%d\nerror=%s\n--- RAW START ---\n%s\n--- RAW END ---",
            len(e.raw_text), e.json_error, e.raw_text,
        )
        return ContentBrief(
            suggested_instructions=entity.title,
            generated_by="fallback",
        )
    except Exception as e:
        log.warning(f"generate_brief failed for {entity.id!r}: {e} — using fallback")
        return ContentBrief(
            suggested_instructions=entity.title,
            generated_by="fallback",
        )


def _parse_json(raw: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    text = re.sub(r"\s*```\s*$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise BriefParseError(
            f"JSON parse failed: {e.msg} at line {e.lineno} col {e.colno} (pos {e.pos}); "
            f"cleaned[:200]={text[:200]!r}; raw_len={len(raw)}",
            raw_text=raw,
            cleaned_text=text,
            json_error=e,
        ) from e


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
