---
project: sam
updated: 2026-05-05
---

# HOT — Sam

## Now

**Session 05.05 MORNING: DAILY_DIGEST_ENABLED env-flag guard deployed — avoids duplicate digests on service restart**

Daily digest job auto-trigger at 09:00 disabled via `.env` guard. `main.py:303-306` wraps job_daily_digest with `os.getenv('DAILY_DIGEST_ENABLED','true').lower()` check — false/0/no/off values skip execution and log 'Daily digest job skipped'. systemctl restart sam.service completed, svc active. No `.env.example` created yet (optional future task). Verification: tomorrow 09:00 should log skip message instead of running digest.

## Last done

**Session 04.05 FINAL CHECKPOINT (recap from WARM)**: Sprint B COMPLETE — All 4 NBLM interventions (1 dangling UUID probe, 2 idempotent ADD_SOURCE, 3 RETRY_DELAYS 4h cap, 4 EN brief) verified live in production via manual `/regen 20:53` end-to-end test. 18/18 podcasts status: 5 ready, 8 pending 4h loop, 2 recovering via Intervention 1 soft fallback. 47 unit-tests PASS (15 nblm, 6 brief, 26 other). RSS feed 18 items synced, deep-links functional.

**Session 05.05 (1.5h): Daily digest guard deployed**

- **Problem identified**: job_daily_digest runs at 09:00 every morning, but on systemctl restart it auto-triggers because systemd timer fires during boot. Creates duplicate digest if restart happens near 09:00.

- **Solution**: Added env-flag guard `DAILY_DIGEST_ENABLED` in `main.py:303-306`. Check `os.getenv('DAILY_DIGEST_ENABLED','true').lower()` → if value in ['false','0','no','off'], log 'Daily digest job skipped' and return. Preserves `/digest` manual command (no changes). Default true (backward compat).

- **Deployment**: `.env` file updated with `DAILY_DIGEST_ENABLED=false`. systemctl restart sam.service executed, svc status active (loaded new code). `.env.example` NOT created (optional improvement for future).

- **Verification**: Tomorrow 05.05 09:00 expected log message 'Daily digest job skipped' instead of running digest. If needed, restore: `sed -i '/^DAILY_DIGEST_ENABLED=/d' .env && systemctl restart sam.service`.

## Next

1. **Tomorrow 05.05 ~09:00: Check daily digest skip message** — Verify logs show 'Daily digest job skipped' at 09:00. Confirm no duplicate digest generated.

2. **Post-Sprint B final decision** (assuming 18/18 still ready from 04.05):
   - **Sprint C** (voice extraction): High value, ~2h
   - **Sprint D** (evals): Medium complexity, ~3h
   - **Phase C** (article dispatcher): Parallel if bandwidth

3. **Backlog (P3, post-Sprint B)**:
   - external_stop zombie: Auto-mark failed when should_stop=True
   - regen message: Say '4 hours' instead of '72 hours'
   - `.env.example` template: Create for deployment docs
   - Cheat-sheet Linux/bash block 2 (grep friction): Resume separately

## Blockers

None. Daily digest guard is optional (non-critical UX improvement).

## Active branches

- **sam-repo (`main`)**: 4 interventions live (47efc76, d822a29, 6e5589c, 26cf181). 47 unit-tests PASS.
- **Production Pi5**: sam.service + sam-rss.service active. Daily digest guard deployed via `.env`. systemctl restart completed, svc loaded.

## Open questions

- **18/18 podcast count**: Expected ready from 04.05 ~21:00. Should verify this morning (05.05) to confirm Sprint B closure.
- **`.env.example` template**: Future task, create example file with common flags for deployment docs.

## Reminders

- **Sprint B VERIFIED (04.05)**: All 4 NBLM interventions live. 18/18 podcasts expected ready (check this morning).
- **Daily digest guard deployed (05.05)**: Env-flag DAILY_DIGEST_ENABLED=false stops 09:00 auto-trigger. Manual /digest command unaffected.
- **2 P3 bugs for backlog**: external_stop zombie, regen message. Both non-blocking.
- **RSS feed**: 18 items, deep-links ready for distribution.
- **Next decision**: Voice extraction vs Evals vs Article dispatcher — after 18/18 final confirmation.
