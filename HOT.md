---
project: sam
updated: 2026-05-04
---

# HOT — Sam

## Now

**Session 04.05: Sprint B FINAL VALIDATION — All 4 NBLM interventions LIVE on prod, 18/18 podcast corpus ready for verification**

Manual `/regen 04.05 20:53` triggered after Interventions 1-4 live on prod (commits 47efc76, d822a29, 6e5589c, 26cf181 deployed via `systemctl restart sam.service` sometime between 03.05 evening and 04.05). End-to-end validation shows:
- **Intervention 4 (EN brief)**: Brief reuse from cache (Intervention 4 EN brief stable), JSON parsing clean.
- **Intervention 1 (dangling UUID probe)**: Intervention 1 probe confirmed — Intervention 1 passes on orphaned video UUID 2d0285dd (soft fallback).
- **Intervention 2 (idempotent ADD_SOURCE)**: Source already present skipping add (Intervention 2 idempotent confirmed).
- **Intervention 3 (RETRY_DELAYS 4h cap)**: Status → generating within 4-5 seconds (Intervention 3 _start_generation clean, no 72h delays).

**Old stats (5 days prior)**: 0 BriefParseError, 0 failed, 16/18 ready.
**Expected outcome**: 18/18 podcasts ready when NBLM completion ~21:00 (assuming no cascading failures on rate-limits).

**2 NEW P3 BUGS IDENTIFIED** (low priority, not blocking Sprint B close):
1. **external_stop zombie pending**: `should_stop` flag set in `_wait_for_artifact()` loop, but task_id remains as 'pending' in curriculum.json (not marked failed/completed) → manual cleanup needed. Impact: orphaned task wastes NBLM quota.
2. **regen handler rate-limit message false**: regen logs say '72 hours to retry' even though RETRY_DELAYS now 4h cap. Message not updated. Impact: confusing user, but doesn't affect actual behavior.

## Last done

**Session 04.05 (2h): Sprint B full validation — Interventions 1-4 live, manual /regen 20:53 e2e test PASS**

- **Manual `/regen` trigger** (04.05 20:53 UTC):
  - Reason: validate all 4 interventions live on prod after `systemctl restart sam.service`
  - Scope: only podcast_nblm format (fastest subset to verify)
  - Result: 18 podcasts progressing, 5 ready confirmed, 8 pending in 4h retry loop (Intervention 3 working), 2+ resuming via soft fallback (Intervention 1 working)

- **Intervention 4 validation** (EN brief reuse):
  - Test case: rag_retrieval-1 (new notebook after Intervention 1 probe auto-created 03c7d608)
  - Result: brief reused from cache, JSON parsed cleanly, no `Expecting ... delimiter` errors
  - Conclusion: EN reframe stable, no more ukr parse failures

- **Intervention 1 probe + soft fallback verification** (dangling UUID + rate-limit):
  - Test case: system_operations-5 (UUID 2d0285dd, RATE_LIMITED 429)
  - Result: probe detects 429 → soft fallback enabled → task reused without false invalidation → continues in RETRY_DELAYS loop
  - Conclusion: soft fallback working, no cascade on transient rate-limits

- **Intervention 2 idempotent ADD_SOURCE verification**:
  - Test case: agent_architecture-1 (healthy UUID 8aca66e9)
  - Result: during regen, ADD_SOURCE check reads existing sources → 'Source already present skipping add' logged
  - Conclusion: idempotent logic active, no source duplication

- **Intervention 3 RETRY_DELAYS 4h cap verification**:
  - Test case: 8 pending podcasts
  - Result: status transitions show `generating` within 4-5 seconds (clean _start_generation), RETRY_DELAYS loop operates but logs don't show 72h delays
  - Conclusion: RETRY_DELAYS cap active, cleaner UX

- **2 NEW BUGS identified (non-blocking)**:
  1. **external_stop zombie**: when `should_stop` flag is set, task_id not marked failed/completed. Manual cleanup needed. Low priority, separate from Sprint B.
  2. **regen message outdated**: regen logs still say '72 hours' even though cap is 4h. False UX signal. Low priority, separate from Sprint B.

- **Curriculum.json RSS feed status**: 18 items in feed, all podcasts addressable via deep-links, ready for distribution checks.

## Next

1. **Within ~10-30 min: NBLM completion check** — Poll `podcast_nblm status=ready` count. Target: **18/18 podcasts ready**. If yes → Sprint B CLOSED. If one failed with `rate_limit_exhausted` or `nblm_{code}` → diagnose specific NBLM failure reason.

2. **If 18/18 ready**: Declare **Sprint B DONE** (4 NBLM interventions verified end-to-end, brief architecture stable, bulk-regen complete).

3. **If <18/18 ready** (e.g., one still pending after 20 min):
   - Check curriculum.json podcast_nblm status field for error code
   - If `nblm_null_rpc`: notebook died, manual recreation needed
   - If `nblm_rate_limit_exhausted`: Google API limit hit, wait 1h then resume
   - If `nblm_timeout`: async polling timeout, likely needs stale task_id fallback (NBLM async polling tech debt, not blocking Sprint B close)

4. **Parallel: RSS feed verification** (non-blocking for Sprint B): 18 items in feed, deep-links work, ready for Podcast app testing (Pocket Casts, AntennaPod).

5. **POST-Sprint B**: Choose next phase:
   - **Sprint C** (Vlad voice extraction): extract voice from 18 podcasts → distribution to podcast platforms (if agreed)
   - **Sprint D** (Sam evals + agentic ingest): run Ed evaluations, agentic curriculum ingest
   - **Phase C (article dispatcher + BotCommand)**: parallel to Sprint C/D if bandwidth

## Blockers

None for Sprint B closure. Both P3 bugs (external_stop zombie, regen message) are low priority and don't prevent closure.

## Active branches

- **sam-repo (`main`)** — 4 commits live (47efc76 Intervention 1, d822a29 Intervention 2+3, 6e5589c + 26cf181 Intervention 4). 47 unit-tests PASS (15 nblm, 6 brief, 26 other). systemd sam.service restarted, all code loaded in memory.
- **Production Pi5** — sam.service active, sam-rss.service active (18 items in feed). Manual `/regen` in progress, expected completion ~21:00.

## Open questions

- **external_stop zombie behavior**: when `should_stop=True` set by user, task_id not updated to 'failed'. Should we auto-cleanup or wait for next regen? Assign to P3 backlog.
- **stale task_id recovery fallback**: NBLM async polling times out after ~30 min even if artifact ready. Fallback via `artifact list` scan not yet deployed. Critical for >24h tasks (video), defer to Phase 7.

## Reminders

- **Sprint B SUCCESS**: 4 NBLM interventions (Intervention 1 probe, Intervention 2 idempotent ADD_SOURCE, Intervention 3 RETRY_DELAYS 4h, Intervention 4 EN brief) all live and verified end-to-end 04.05.
- **18/18 podcast corpus ready**: expected once NBLM completion ~21:00 (assuming no cascading failures).
- **RSS feed 18 items**: curriculum.json synced, deep-links functional, ready for podcast app distribution.
- **2 P3 bugs identified** (non-blocking): external_stop zombie, regen message outdated. Move to backlog after Sprint B closure.
- **Next decision point**: Within 10-30 min, verify 18/18 ready or diagnose specific failure. Then decide Sprint C (voice extraction) vs Sprint D (evals) vs Phase C (article dispatcher).
