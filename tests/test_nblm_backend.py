"""
Unit tests for nblm backend — Interventions 2, 3, bonus B1/B2.

Run: python -m unittest tests.test_nblm_backend -v
     (or: pip install pytest && python -m pytest tests/test_nblm_backend.py -v)
"""
import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.content_gen.backends.nblm import (
    RETRY_DELAYS,
    _start_generation,
    _wait_for_artifact,
    generate_and_notify,
    get_or_create_notebook,
)


def _mock_state(fmt_status=None, task_id=None):
    """Minimal CurriculumState mock. fmt_status=None → topic has no format entry."""
    mock_fmt = None
    if fmt_status is not None:
        mock_fmt = MagicMock()
        mock_fmt.status = fmt_status
        mock_fmt.task_id = task_id

    mock_entity = MagicMock()
    mock_entity.nblm_notebook_id = "nb-id"
    mock_entity.formats = {"slides": mock_fmt} if mock_fmt is not None else {}

    state = MagicMock()
    state.get_topic.return_value = mock_entity
    state.get_article.return_value = None
    return state, mock_entity


# ── 3a: RETRY_DELAYS cap ──────────────────────────────────────────────────────

class TestRetryDelaysCap(unittest.TestCase):
    def test_length_is_five(self):
        """5 total attempts: immediate + 4 hourly retries (~4h cap)."""
        self.assertEqual(len(RETRY_DELAYS), 5)
        self.assertEqual(RETRY_DELAYS[0], 0)
        self.assertTrue(all(d == 3600 for d in RETRY_DELAYS[1:]))


# ── 3b: null-RPC error propagation ───────────────────────────────────────────

class TestStartGenerationErrorPropagation(unittest.IsolatedAsyncioTestCase):

    async def test_nblm_error_code_propagated(self):
        """Structured JSON error with code → nblm_<code.lower()>."""
        nblm_json = json.dumps({
            "error": True,
            "code": "ERROR",
            "message": "RPC rLM1Ne returned null result data",
        })
        with patch("core.content_gen.backends.nblm._run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (1, nblm_json, "")
            task_id, err = await _start_generation("nb-id", "slides", "instructions")
        self.assertEqual(task_id, "")
        self.assertEqual(err, "nblm_error")

    async def test_non_json_error_falls_back_to_generic(self):
        """Non-JSON error output → generic 'error' string (no crash)."""
        with patch("core.content_gen.backends.nblm._run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (1, "Internal server error", "")
            task_id, err = await _start_generation("nb-id", "slides", "instructions")
        self.assertEqual(task_id, "")
        self.assertEqual(err, "error")

    async def test_rate_limit_substring_still_detected(self):
        """'rate limited' in stdout → rate_limit (early-return path unchanged)."""
        with patch("core.content_gen.backends.nblm._run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "error: rate limited by Google", "")
            task_id, err = await _start_generation("nb-id", "slides", "instructions")
        self.assertEqual(err, "rate_limit")


# ── Bonus B2: _wait_for_artifact external stop ────────────────────────────────

class TestWaitForArtifactExternalStop(unittest.IsolatedAsyncioTestCase):

    async def test_exits_when_status_not_generating(self):
        """Returns (False, 'external_stop') immediately when curriculum status != generating."""
        state, _ = _mock_state(fmt_status="failed")
        with patch("core.content_gen.backends.nblm.load", return_value=state):
            ok, err = await _wait_for_artifact(
                "task-id", "nb-id",
                topic_id="topic-1", kind="topic",
                cur_path=Path("/fake/curriculum.json"), fmt="slides",
            )
        self.assertFalse(ok)
        self.assertEqual(err, "external_stop")

    async def test_continues_while_status_is_generating(self):
        """Proceeds to artifact wait when status=generating."""
        state, _ = _mock_state(fmt_status="generating")
        completed_json = json.dumps({"status": "completed"})
        with patch("core.content_gen.backends.nblm.load", return_value=state), \
             patch("core.content_gen.backends.nblm._run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, completed_json, "")
            ok, err = await _wait_for_artifact(
                "task-id", "nb-id",
                topic_id="topic-1", kind="topic",
                cur_path=Path("/fake/curriculum.json"), fmt="slides",
            )
        self.assertTrue(ok)
        self.assertEqual(err, "")

    async def test_no_check_when_cur_path_none(self):
        """No external stop check when cur_path not provided (backward compat)."""
        completed_json = json.dumps({"status": "completed"})
        with patch("core.content_gen.backends.nblm._run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, completed_json, "")
            ok, err = await _wait_for_artifact("task-id", "nb-id")
        self.assertTrue(ok)


# ── Intervention 2: idempotent source add ─────────────────────────────────────

class TestIdempotentSourceAdd(unittest.IsolatedAsyncioTestCase):

    async def test_source_add_skipped_when_already_present(self):
        """source add NOT called when URL already in notebook source list."""
        source_url = "https://example.com/article"
        source_list_json = json.dumps({"sources": [{"url": source_url}]})
        # _run calls: [source list → present, then _start_generation → error]
        run_side_effects = [
            (0, source_list_json, ""),
            (1, '{"error": true, "code": "ERROR"}', ""),
        ]
        state, _ = _mock_state(fmt_status=None)
        with patch("core.content_gen.backends.nblm._run",
                   new_callable=AsyncMock,
                   side_effect=run_side_effects) as mock_run, \
             patch("core.content_gen.backends.nblm.load", return_value=state), \
             patch("core.content_gen.backends.nblm.save"), \
             patch("core.content_gen.backends.nblm.set_format_status"), \
             patch("core.content_gen.backends.nblm.set_article_format_status"), \
             patch("core.content_gen.backends.nblm.get_or_create_notebook",
                   new_callable=AsyncMock, return_value="nb-id"):
            await generate_and_notify(
                bot=AsyncMock(), chat_id=123,
                topic_id="topic-1", topic_title="Test",
                source_url=source_url, fmt="slides", instructions="test",
                data_dir=Path("/fake"),
            )
        add_calls = [
            c for c in mock_run.call_args_list
            if list(c.args[0])[:2] == ["source", "add"]
        ]
        self.assertEqual(len(add_calls), 0, "source add should be skipped")

    async def test_source_add_called_when_not_present(self):
        """source add IS called when URL not in notebook source list."""
        source_url = "https://example.com/article"
        source_list_json = json.dumps({"sources": [{"url": "https://other.com"}]})
        run_side_effects = [
            (0, source_list_json, ""),              # source list → different URL
            (0, "", ""),                             # source add → success
            (1, '{"error": true, "code": "ERROR"}', ""),  # start gen → error
        ]
        state, _ = _mock_state(fmt_status=None)
        with patch("core.content_gen.backends.nblm._run",
                   new_callable=AsyncMock,
                   side_effect=run_side_effects) as mock_run, \
             patch("core.content_gen.backends.nblm.load", return_value=state), \
             patch("core.content_gen.backends.nblm.save"), \
             patch("core.content_gen.backends.nblm.set_format_status"), \
             patch("core.content_gen.backends.nblm.set_article_format_status"), \
             patch("core.content_gen.backends.nblm.get_or_create_notebook",
                   new_callable=AsyncMock, return_value="nb-id"):
            await generate_and_notify(
                bot=AsyncMock(), chat_id=123,
                topic_id="topic-1", topic_title="Test",
                source_url=source_url, fmt="slides", instructions="test",
                data_dir=Path("/fake"),
            )
        add_calls = [
            c for c in mock_run.call_args_list
            if list(c.args[0])[:2] == ["source", "add"]
        ]
        self.assertEqual(len(add_calls), 1, "source add should be called once")


# ── 3a + B1: rate_limit_exhausted + external stop in retry loop ───────────────

class TestRetryLoopBehavior(unittest.IsolatedAsyncioTestCase):

    async def test_rate_limit_exhausted_after_all_attempts(self):
        """After 5 rate-limited starts, final error is 'rate_limit_exhausted'."""
        rate_limit_out = json.dumps({"info": "rate limited by google"})
        # 5 _start_generation calls (RETRY_DELAYS has 5 elements)
        run_side_effects = [(0, rate_limit_out, "")] * 5

        state, entity = _mock_state(fmt_status=None)
        captured_status = []

        def capture(st, tid, fmt, status, **kw):
            captured_status.append((status, kw))

        with patch("core.content_gen.backends.nblm._run",
                   new_callable=AsyncMock, side_effect=run_side_effects), \
             patch("core.content_gen.backends.nblm.load", return_value=state), \
             patch("core.content_gen.backends.nblm.save"), \
             patch("core.content_gen.backends.nblm.set_format_status",
                   side_effect=capture), \
             patch("core.content_gen.backends.nblm.set_article_format_status"), \
             patch("core.content_gen.backends.nblm.get_or_create_notebook",
                   new_callable=AsyncMock, return_value="nb-id"), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            await generate_and_notify(
                bot=AsyncMock(), chat_id=123,
                topic_id="topic-1", topic_title="Test",
                source_url="", fmt="slides", instructions="test",
                data_dir=Path("/fake"),
            )

        failed = [(s, kw) for s, kw in captured_status if s == "failed"]
        self.assertTrue(len(failed) >= 1)
        self.assertEqual(failed[-1][1].get("error"), "rate_limit_exhausted")

    async def test_external_stop_in_retry_loop(self):
        """Retry loop exits early on external stop; bot not notified."""
        rate_limit_out = json.dumps({"info": "rate limited by google"})

        call_count = [0]

        def load_factory(path):
            call_count[0] += 1
            if call_count[0] == 1:
                # Lazy re-attach check: no existing task
                state, _ = _mock_state(fmt_status=None)
            else:
                # B1 external stop check (after first sleep): status=failed
                state, _ = _mock_state(fmt_status="failed")
            return state

        with patch("core.content_gen.backends.nblm._run",
                   new_callable=AsyncMock,
                   side_effect=[(0, rate_limit_out, "")]) as mock_run, \
             patch("core.content_gen.backends.nblm.load", side_effect=load_factory), \
             patch("core.content_gen.backends.nblm.save"), \
             patch("core.content_gen.backends.nblm.set_format_status"), \
             patch("core.content_gen.backends.nblm.set_article_format_status"), \
             patch("core.content_gen.backends.nblm.get_or_create_notebook",
                   new_callable=AsyncMock, return_value="nb-id"), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            mock_bot = AsyncMock()
            await generate_and_notify(
                bot=mock_bot, chat_id=123,
                topic_id="topic-1", topic_title="Test",
                source_url="", fmt="slides", instructions="test",
                data_dir=Path("/fake"),
            )

        # Only 1 _start_generation call (delay=0 iteration), then external stop on delay=3600
        self.assertEqual(mock_run.call_count, 1)
        mock_bot.send_message.assert_not_called()


# ── Intervention 1: dangling notebook probe ──────────────────────────────────

class TestNotebookProbe(unittest.IsolatedAsyncioTestCase):

    def _state(self, nb_id):
        entity = MagicMock()
        entity.nblm_notebook_id = nb_id
        state = MagicMock()
        state.get_topic.return_value = entity
        state.get_article.return_value = None
        return state, entity

    async def test_probe_success_reuses_uuid(self):
        """probe rc=0 + valid JSON → return existing UUID, no create call."""
        state, _ = self._state("existing-uuid")
        probe_json = json.dumps({"sources": []})
        with patch("core.content_gen.backends.nblm._run",
                   new_callable=AsyncMock,
                   return_value=(0, probe_json, "")) as mock_run, \
             patch("core.content_gen.backends.nblm.load", return_value=state), \
             patch("core.content_gen.backends.nblm.save") as mock_save:
            result = await get_or_create_notebook(
                "topic-1", "Topic One", Path("/fake"), kind="topic"
            )
        self.assertEqual(result, "existing-uuid")
        self.assertEqual(mock_run.call_count, 1)
        mock_save.assert_not_called()

    async def test_probe_rc_nonzero_invalidates_and_creates(self):
        """probe rc!=0 → invalidate (set None), fallthrough to create, return new UUID."""
        state, _ = self._state("dangling-uuid")
        run_side_effects = [
            (1, "", "not found"),
            (0, "Created notebook: fresh-uuid extra", ""),
        ]
        with patch("core.content_gen.backends.nblm._run",
                   new_callable=AsyncMock, side_effect=run_side_effects), \
             patch("core.content_gen.backends.nblm.load", return_value=state), \
             patch("core.content_gen.backends.nblm.save") as mock_save, \
             patch("core.content_gen.backends.nblm.set_nblm_notebook_id") as mock_set, \
             patch("core.content_gen.backends.nblm.set_article_nblm_notebook_id"):
            result = await get_or_create_notebook(
                "topic-1", "Topic One", Path("/fake"), kind="topic"
            )
        self.assertEqual(result, "fresh-uuid")
        self.assertIsNone(mock_set.call_args_list[0].args[2])   # invalidation
        self.assertEqual(mock_set.call_args_list[1].args[2], "fresh-uuid")  # new id
        self.assertEqual(mock_save.call_count, 2)

    async def test_probe_rate_limited_falls_back_to_reuse(self):
        """probe rc!=0 з 'rate limited' у stderr → reuse без інвалідації."""
        state, _ = self._state("existing-uuid")
        with patch("core.content_gen.backends.nblm._run",
                   new_callable=AsyncMock,
                   return_value=(1, "", "Error: rate limited by Google")) as mock_run, \
             patch("core.content_gen.backends.nblm.load", return_value=state), \
             patch("core.content_gen.backends.nblm.save") as mock_save, \
             patch("core.content_gen.backends.nblm.set_nblm_notebook_id") as mock_set:
            result = await get_or_create_notebook(
                "topic-1", "Topic One", Path("/fake"), kind="topic"
            )
        self.assertEqual(result, "existing-uuid")
        self.assertEqual(mock_run.call_count, 1)
        mock_save.assert_not_called()
        mock_set.assert_not_called()

    async def test_probe_json_decode_error_invalidates_and_creates(self):
        """probe rc=0 but JSON malformed → invalidate, fallthrough to create."""
        state, _ = self._state("dangling-uuid")
        run_side_effects = [
            (0, "not-valid-json", ""),
            (0, "Created notebook: fresh-uuid2 extra", ""),
        ]
        with patch("core.content_gen.backends.nblm._run",
                   new_callable=AsyncMock, side_effect=run_side_effects), \
             patch("core.content_gen.backends.nblm.load", return_value=state), \
             patch("core.content_gen.backends.nblm.save"), \
             patch("core.content_gen.backends.nblm.set_nblm_notebook_id") as mock_set, \
             patch("core.content_gen.backends.nblm.set_article_nblm_notebook_id"):
            result = await get_or_create_notebook(
                "topic-1", "Topic One", Path("/fake"), kind="topic"
            )
        self.assertEqual(result, "fresh-uuid2")
        self.assertIsNone(mock_set.call_args_list[0].args[2])


if __name__ == "__main__":
    unittest.main()
