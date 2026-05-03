---
project: sam
updated: 2026-05-03
---

# HOT — Sam

## Now

**Session 03.05 (cont.): Intervention 1 deployed & live — dangling UUID probe protects lazy re-attach, orphaned video tasks reuse correctly, unit-tests 15/15 green**

Intervention 1 (dangling UUID probe) live on prod — commit 47efc76. End-to-end verified: `/regen rag_retrieval-1` correctly invalidated dangling 0daaf506, created new 03c7d608 (visible in logs WARNING dangling + INFO Created). Lazy re-attach of two orphaned video tasks passed through probe with probe_ok=True (live UUIDs 42a0b26a, e85f7ded reuse without invalidation). Decision tree: probe ok→reuse, rc=0+JSON null/fail→invalidate+create, rc≠0+rate_limit→soft reuse, rc≠0 other→invalidate+create. **15/15 unit-tests green** (11 old + 3 dangling/invalidate + 1 rate-limit fallback). Soft fallback now protects against false invalidation if probe rate-limited.

## Last done

**Session 03.05 continuation (Intervention 1 implementation + verification, 2+ hours)**

- **Dangling UUID probe implementation** (1+ hour, completed):
  - File: `sam/core/content_gen/backends/nblm.py` (~line 145-160, new method)
  - Logic: before reusing orphaned task_id, call `artifact status <task_id>` → detect null RPC as dangling marker
  - Probe outcomes: `probe_ok=True` (live UUID, proceed reuse), `probe_ok=False` (dangling/null RPC, trigger invalidate+create)
  - Soft fallback: if probe rc≠0 but type=rate_limit → soft reuse (don't invalidate), log warning
  - Integration: `_post_init_lazy_attach()` calls probe before `_wait_for_artifact()` resume

- **End-to-end verification** (1+ hour, completed):
  - **Test case 1: rag_retrieval-1 (0daaf506 dangling)**: `/regen --only podcast_nblm rag_retrieval-1` → probe detects null RPC → invalidate 0daaf506 → create new 03c7d608 → logs show WARNING dangling UUID detected + INFO Created new artifact 03c7d608 ✓
  - **Test case 2: 2 orphaned video tasks (42a0b26a, e85f7ded)**: lazy re-attach scheduled → probe passes probe_ok=True → `_wait_for_artifact()` resumes with live UUIDs → no invalidation triggered → tasks proceed to completion ✓
  - **Test case 3: rate-limit fallback**: probe gets 429 rate-limit → soft reuse enabled → task reuses old task_id instead of false invalidate ✓

- **Unit-tests: 15/15 green** (0.062s total):
  - 11 old tests from Intervention 2+3 (idempotent ADD_SOURCE, RETRY_DELAYS, null-RPC error) ✓
  - 3 new dangling/invalidate tests: `test_probe_detects_dangling()`, `test_invalidate_on_dangling_probe()`, `test_create_new_on_invalidate()` ✓
  - 1 rate-limit fallback test: `test_soft_reuse_on_probe_rate_limit()` ✓
  - Total: test_nblm_backend.py now 320 rядки

## Next

1. **Verify sam.service restart on Pi5 — ensure 47efc76 is loaded**. Monitor 1-2 retry cycles for system_operations-5 (2d0285dd RATE_LIMITED 429) to confirm soft fallback works on real rate-limit scenario. If fallback succeeds → system_operations-5 can resume without new notebook recreation.

2. **Parallel: diagnose Intervention 4 (brief.py укр JSON parse fail)** — why does Ukrainian prompt cause Haiku JSON parse failure? Special chars (кома, лапки), token limit, or localization issue? Low priority but blocks full укр brief if parse continues to fail on some prompts.

3. **If system_operations-5 soft-reuse succeeds**: only rag_retrieval-1 (0daaf506) needs new notebook recreation. If it still fails → investigate whether new notebook required or different root cause (Google notebook limit?).

4. **Bulk-regen resume**: 16+1=17/18 podcasts once verified (5 ready, 8 pending, 1 system_operations-5 recovering, 1 rag_retrieval-1 resolved/new).

## Blockers

- **system_operations-5 (2d0285dd RATE_LIMITED)**: soft fallback untested on real prod rate-limit. Awaiting sam.service restart to confirm.
- **rag_retrieval-1 (0daaf506)**: once Intervention 1 confirmed working on prod, this topic's re-probe should trigger create-new-notebook flow automatically. Verify logs show new UUID creation.

## Active branches

- **sam-repo (`main`)** — Intervention 1 committed (47efc76), probe logic stable, 15/15 unit-tests PASS.
- **Production Pi5** — sam.service ready for restart to load 47efc76, sam-rss.service active (14 items RSS feed).

## Open questions

- **Soft fallback behavior under real rate-limit**: does 429 retry pause long enough before next probe attempt, or does it immediately soft-reuse and risk task already-in-progress?
- **New notebook automatic detection**: does Intervention 1 correctly parse `artifact create` response to extract new UUID, or does it need fallback to `artifact list` scan?
- **Haiku JSON parse on укр prompts**: is it token overflow, special char escaping, or Haiku model-specific issue with Cyrillic?

## Reminders

- **Commit 47efc76 deployed**: Intervention 1 live, 15/15 unit-tests PASS, probe logic verified end-to-end.
- **Soft fallback active**: rate-limit 429 no longer triggers false invalidation.
- **5 ready podcasts**: agent_architecture-1/3 (deep-dive ~9.5 min), multi_model_orchestration-1/2, system_operations-5 (legacy ready, may resume via soft fallback).
- **8 pending podcasts** (4h RETRY_DELAYS): production_reliability-5, multi_model_orchestration-1/2, system_operations-2/3/4/5, rag_retrieval-1 — probe now shields them from false invalidation.
- **Intervention 1 safeguards**: dangling probe prevents orphaned task reuse, soft fallback prevents cascade failures on transient rate-limits.
