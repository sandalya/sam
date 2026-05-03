"""
Unit tests for core/content_gen/brief.py — BriefParseError + generate_brief fallback.

Run: python -m pytest tests/test_brief_parse.py -v
"""
import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))            # sam/
sys.path.insert(0, str(Path(__file__).parent.parent.parent))     # workspace/

from core.content_gen.brief import BriefParseError, _parse_json

_VALID_JSON = (
    '{"key_concepts":["A","B"],"focus_questions":["Q?"],'
    '"suggested_angle":"x","suggested_instructions":"Зосередься на X",'
    '"source_summary":"Y"}'
)
_TRUNCATED = (
    '{"key_concepts":["A","B"],"focus_questions":["Q?"],'
    '"suggested_angle":"long text that goes on and on and on'
)


class TestParseJson(unittest.TestCase):

    def test_parse_valid_json(self):
        result = _parse_json(_VALID_JSON)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["key_concepts"], ["A", "B"])

    def test_parse_strips_markdown_fences(self):
        wrapped = f"```json\n{_VALID_JSON}\n```"
        result = _parse_json(wrapped)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["suggested_angle"], "x")

    def test_parse_raises_brief_parse_error_on_truncation(self):
        with self.assertRaises(BriefParseError):
            _parse_json(_TRUNCATED)

    def test_brief_parse_error_includes_raw(self):
        try:
            _parse_json(_TRUNCATED)
            self.fail("Expected BriefParseError")
        except BriefParseError as e:
            self.assertEqual(e.raw_text, _TRUNCATED)
            self.assertIsInstance(e.json_error, json.JSONDecodeError)
            self.assertIsInstance(e.cleaned_text, str)


class TestGenerateBrief(unittest.TestCase):

    def test_generate_brief_falls_back_on_parse_error(self):
        from curriculum.models import ContentBrief

        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text=_TRUNCATED)]

        mock_agent_base = MagicMock()
        mock_agent_base.client = MagicMock()
        mock_agent_base.MODEL_FAST = "claude-haiku-test"

        entity = MagicMock()
        entity.id = "test-entity-1"
        entity.title = "Test Title"
        entity.source_url = "https://example.com"
        entity.summary = ""

        with patch.dict("sys.modules", {
            "shared": MagicMock(),
            "shared.agent_base": mock_agent_base,
        }):
            with patch("asyncio.to_thread", new_callable=AsyncMock, return_value=mock_resp):
                with patch("core.content_gen.brief.log") as mock_log:
                    from core.content_gen import brief
                    result = asyncio.run(brief.generate_brief(entity, "article"))

        self.assertIsInstance(result, ContentBrief)
        self.assertEqual(result.generated_by, "fallback")
        self.assertEqual(result.suggested_instructions, "Test Title")
        mock_log.error.assert_called_once()
        call_args = mock_log.error.call_args[0]
        self.assertIn("BRIEF JSON PARSE FAIL", call_args[0])


if __name__ == "__main__":
    unittest.main()
