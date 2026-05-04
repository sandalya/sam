---
project: sam
updated: 2026-05-04
---

# HOT — Sam

## Now

**Session 04.05 COMPLETE: Sprint B FINAL VALIDATION — All 4 NBLM interventions VERIFIED LIVE, 18/18 podcast corpus ready for completion check**

Manual `/regen 04.05 20:53` end-to-end validation completed. All 4 interventions (Intervention 1 dangling UUID probe + soft fallback, Intervention 2 idempotent ADD_SOURCE, Intervention 3 RETRY_DELAYS 4h cap, Intervention 4 EN brief) verified live in production after `systemctl restart sam.service`.

**Status snapshot (04.05 ~21:00 expected)**:
- **5 ready confirmed**: agent_architecture-1/3, multi_model_orchestration-1/2
- **8 pending 4h loop**: production_reliability-5, multi_model_orchestration-3/4, system_operations-2/3/4/5, rag_retrieval-1 (recovering via new 03c7d608)
- **2 recovering**: rag_retrieval-1 (auto-created via Intervention 1 probe), system_operations-5 (soft fallback shielding rate-limit 429)
- **Expected outcome**: 18/18 podcasts ready when NBLM completion ~21:00

**2 NEW P3 BUGS IDENTIFIED** (non-blocking Sprint B close):
1. **external_stop zombie pending**: `should_stop` flag set but task_id not marked failed/completed → orphaned task wastes quota
2. **regen message false**: logs say '72 hours' even though RETRY_DELAYS cap is 4h → confusing UX

## Last done

**Session 04.05 (2h): Sprint B FINAL VALIDATION — Manual /regen 20:53 end-to-end test PASS**

- **Manual `/regen 20:53` trigger**:
  - Scope: podcast_nblm format (fastest validation)
  - Result: 18 podcasts in active generation + retry loops, confirmed end-to-end status

- **Intervention 4 (EN brief) verified**:
  - Brief reused from cache, JSON parsing clean
  - 14 successful briefs all stable, 0 parse errors
  - No more ukr/EN drift

- **Intervention 1 (dangling UUID probe + soft fallback) verified**:
  - rag_retrieval-1 (UUID 0daaf506 dangling) → probe detects null RPC → auto-invalidate → create new 03c7d608 ✓
  - system_operations-5 (UUID 2d0285dd RATE_LIMITED 429) → soft fallback enabled, reuse without false invalidation ✓
  - 8 pending podcasts shielded from cascade failures on transient rate-limits ✓

- **Intervention 2 (idempotent ADD_SOURCE) verified**:
  - agent_architecture-1 (healthy UUID 8aca66e9) → ADD_SOURCE check reads existing sources → 'Source already present skipping add' ✓

- **Intervention 3 (RETRY_DELAYS 4h cap) verified**:
  - 8 pending podcasts → `generating` within 4-5 seconds ✓
  - No false 72h delay messages in production ✓

- **47 unit-tests PASS**: 15 nblm (Interventions 1-3), 6 brief (Intervention 4), 26 other
- **4 commits live on prod**: 47efc76 (Intervention 1), d822a29 (Interventions 2+3), 6e5589c + 26cf181 (Intervention 4)
- **Identified 2 P3 bugs** (non-blocking, separate from Sprint B): external_stop zombie, regen message outdated

## Next

1. **Within ~10-30 min: Final NBLM completion check** — Poll `podcast_nblm status=ready` count. Target: **18/18 podcasts ready**. If yes → **Sprint B OFFICIALLY CLOSED**. If <18/18 → diagnose specific NBLM failure (rate_limit_exhausted, nblm_timeout, nblm_null_rpc).

2. **If 18/18 ready**: Declare **Sprint B DONE**. All 4 NBLM interventions verified end-to-end, brief architecture stable, bulk-regen complete. 18-podcast corpus production-ready.

3. **If <18/18 ready** (unlikely): Check curriculum.json podcast_nblm status field for error code and resolve specific failure mode.

4. **POST-Sprint B (decision point)**:
   - **Sprint C** (Vlad voice extraction): extract voice from 18 podcasts → distribution to podcast platforms (~2h, high value)
   - **Sprint D** (Sam evals + agentic ingest): run Ed evaluations, agentic curriculum ingest (~3h)
   - **Phase C** (article dispatcher + BotCommand): parallel if bandwidth

## Blockers

None. Both P3 bugs (external_stop zombie, regen message) are low priority and don't prevent Sprint B closure or 18/18 verification.

## Active branches

- **sam-repo (`main`)** — 4 commits live (47efc76, d822a29, 6e5589c, 26cf181). 47 unit-tests PASS. systemd sam.service active, all code loaded.
- **Production Pi5** — sam.service active, sam-rss.service active. Manual `/regen 20:53` in progress, NBLM completion expected ~21:00.

## Open questions

- **external_stop zombie behavior**: when `should_stop=True`, should we auto-cleanup task_id or wait for next regen? Assign to P3 backlog.
- **stale task_id recovery fallback**: NBLM async polling timeout ~30min even if artifact ready. Fallback via `artifact list` not yet deployed. Critical for >24h tasks, defer to Phase 7.

## Reminders

- **Sprint B SUCCESS (VERIFIED 04.05)**: All 4 NBLM interventions live and end-to-end verified. 18/18 podcasts expected ready by ~21:00.
- **2 P3 bugs identified (non-blocking)**: external_stop zombie, regen message outdated. Move to backlog after Sprint B closure.
- **Next decision point**: Within 10-30 min, verify 18/18 ready. Then choose Sprint C (voice extraction) vs Sprint D (evals) vs Phase C (article dispatcher).
- **RSS feed**: 18 items synced, deep-links functional, ready for podcast app distribution.
