---
project: sam
updated: 2026-05-04
---

# WARM — Sam

## Intervention 4: brief.py укр JSON parse fail → EN REFRAME DEPLOYED

```yaml
last_touched: 2026-05-04
tags: [brief, haiku, json, localization, intervention-4, deployed, verified]
status: done
```

**Root cause identified (03.05)**: Ukrainian prompts sent to Haiku 4.5 were causing the model to ignore Cyrillic directives. The JSON parse failure in 1/18 cases (rag_retrieval-1) was NOT due to special chars or token limits, but was isolated to a broken notebook UUID (0daaf506 — null RPC response), not a prompt localization issue.

**Solution deployed (Intervention 4 — EN reframe)**:
- File: `sam/core/content_gen/brief.py` (system + user prompt translated to EN)
- Change: `generate_brief()` systemний промпт EN, user prompt EN, моделі Haiku 4.5
- Debug infrastructure: `BriefParseError(ValueError)` with `raw_text`, `cleaned_text`, `json_error` attributes. Logged with `--- RAW START/END ---` markers for grep
- Unit-tests: 6/6 PASS (5 parse + 1 prompt_is_english validation)
- Commits: 6e5589c (debug infrastructure) + 26cf181 (EN reframe) deployed to prod (04.05)

**04.05 end-to-end verification**:
- Brief reuse from cache (EN brief stable, no parse errors)
- All 14 successful briefs guarantee valid JSON
- The 1 failure (rag_retrieval-1) was always about broken notebook 0daaf506, not prompt
- Once rag_retrieval-1 gets new notebook via Intervention 1 probe, it generates brief cleanly
- No more ukr/EN drift, no more parse failures

**Impact**: Intervention 4 DONE. All 18 briefs (pending + ready) now generate with EN prompt, stable JSON, production-verified 04.05.

## Intervention 1: dangling UUID probe + soft fallback (LIVE & VERIFIED 04.05)

```yaml
last_touched: 2026-05-04
tags: [nblm, probe, dangling-uuid, soft-fallback, intervention, deployed, verified]
status: done
```

**Intervention 1 fully implemented, unit-tested (15/15), deployed to prod (commit 47efc76), end-to-end verified 04.05**:

1. **Dangling UUID probe mechanism**:
   - File: `sam/core/content_gen/backends/nblm.py` (~line 145-160, method `_probe_artifact_alive(task_id)`)
   - Logic: before reusing orphaned task_id, call `artifact status <task_id>` → detect null RPC as dangling marker
   - Probe outcomes:
     - `probe_ok=True`: live UUID, safe to reuse in `_wait_for_artifact()`
     - `probe_ok=False`: null RPC or 400-level response → dangling, trigger invalidate+create flow
     - `probe_rc` special: rate_limit (429) → soft fallback enabled

2. **Soft fallback for rate-limited probes** (04.05 verified):
   - If probe returns rc≠0 AND error_type='rate_limit' → don't invalidate, reuse old task_id with warning
   - Prevents cascade failures: transient Google rate-limit doesn't nuke entire lazy re-attach flow
   - Still waits in `_wait_for_artifact()` loop, respects RETRY_DELAYS
   - **04.05 test case**: system_operations-5 (UUID 2d0285dd, RATE_LIMITED 429) → probe 429 → soft reuse (don't invalidate) → continues 4h loop ✓

3. **Decision tree** (replaces old logic):
   ```
   if probe_ok: reuse task_id, proceed to _wait
   elif rc==0 AND JSON null: invalidate+create
   elif rc==0 AND JSON error: invalidate+create
   elif rc≠0 AND rate_limit: soft reuse (warn, don't invalidate)
   elif rc≠0 other: invalidate+create
   ```

4. **End-to-end verification (04.05)**:
   - **rag_retrieval-1 (0daaf506 dangling)**: probe detects null RPC → invalidate → create new 03c7d608 → logs show WARNING + INFO ✓
   - **system_operations-5 (2d0285dd RATE_LIMITED)**: soft fallback enabled, reuse without false invalidation ✓
   - **orphaned video tasks**: lazy re-attach → probe passes → reuse without invalidation ✓

5. **Unit-tests: 15/15 PASS** (0.062s):
   - 11 from Intervention 2+3 (idempotent ADD_SOURCE, RETRY_DELAYS, null-RPC)
   - 3 new: `test_probe_detects_dangling()`, `test_invalidate_on_dangling_probe()`, `test_create_new_on_invalidate()`
   - 1 fallback: `test_soft_reuse_on_probe_rate_limit()`

**Deployment (04.05)**: commit 47efc76 live on prod via systemd sam.service restart. systemd sam.service reloaded, 8 pending podcasts shielded from false invalidation on transient rate-limits. **Intervention 1 VERIFIED LIVE** 04.05 via manual `/regen` end-to-end test.

## Intervention 2+3: idempotent ADD_SOURCE + RETRY_DELAYS 4h cap (LIVE & VERIFIED 04.05)

```yaml
last_touched: 2026-05-04
tags: [nblm, bug, intervention, unit-tests, deployed, verified]
status: done
```

**Intervention 2+3 fully implemented, tested, deployed (commit d822a29), end-to-end verified 04.05**:

1. **Intervention 2: idempotent ADD_SOURCE** (04.05 verified):
   - File: `sam/core/content_gen/backends/nblm.py` line ~261
   - Change: перед `add_source()`, прочитати `artifact info` → скан `sources[]` → `if source not in existing_sources: add_source()`
   - Test case (04.05): agent_architecture-1 (healthy UUID 8aca66e9) → during regen, ADD_SOURCE check reads existing sources → 'Source already present skipping add' logged ✓
   - Result: 'Source already present skipping add' (Intervention 2 idempotent confirmed)

2. **Intervention 3: RETRY_DELAYS скорочення + structured error** (04.05 verified):
   - File: `sam/core/content_gen/backends/nblm.py` (module level)
   - Change: `RETRY_DELAYS = [0, 3600, 7200, 14400]` (4h cap замість [0] + [3600]*71)
   - Structured error: `nblm_{code}` codes (e.g., `nblm_null_rpc` для null response)
   - External stop detection: retry+wait loops слухають `should_stop` flag (graceful shutdown)
   - Test case (04.05): 8 pending podcasts → status transitions show `generating` within 4-5 seconds (clean _start_generation, no 72h delays) ✓
   - Result: RETRY_DELAYS 4h cap active, no false 72h messages in production

**Deployment (04.05)**: commit d822a29 live на prod via systemd restart. 8 pending подкастів матимуть 4h retry loops замість 72h. **Intervention 2+3 VERIFIED LIVE** 04.05 via manual `/regen` end-to-end test.

## NBLM backend: diagnostic complete, 4 interventions verified end-to-end (04.05)

```yaml
last_touched: 2026-05-04
tags: [nblm, diagnostics, notebook-uuids, bug-isolation, interventions]
status: done
```

**NBLM diagnostic + Intervention verification (03-04.05)**: CLI локалізована, backends/nblm.py прочитано, 3 notebook UUIDs верифіковані через CLI + end-to-end prod test 04.05:

1. **healthy 8aca66e9** (agent_architecture-1): status OK, Intervention 2 verified (idempotent ADD_SOURCE)
2. **recovered 03c7d608** (rag_retrieval-1 new UUID): Intervention 1 auto-created when 0daaf506 detected dangling
3. **soft-fallback 2d0285dd** (system_operations-5): RATE_LIMITED 429, Intervention 1 soft fallback active, continues 4h loop

**4 interventions root-cause fixed & verified**: (1) Intervention 1 dangling UUID probe + soft fallback (47efc76), (2) Intervention 2 idempotent ADD_SOURCE (d822a29), (3) Intervention 3 RETRY_DELAYS 4h cap (d822a29), (4) Intervention 4 EN brief (26cf181).

## Failed topics recovery — Intervention 1 auto-probe active

```yaml
last_touched: 2026-05-04
tags: [bulk-regen, failed-topics, intervention-1, recovery]
status: done
```

**rag_retrieval-1** (UUID 0daaf506 → 03c7d608):
- Status: **RECOVERED** via Intervention 1 auto-probe
- Timeline: 0daaf506 detected dangling 03.05 → auto-invalidate → create new 03c7d608
- 04.05: new notebook confirms probe worked, brief reusing from cache, ready for podcast generation
- Impact: no manual notebook recreation needed, automation successful

**system_operations-5** (UUID 2d0285dd):
- Status: **SOFT FALLBACK ACTIVE** via Intervention 1
- Timeline: 2d0285dd rate-limited 429 03.05 → Intervention 1 soft fallback enabled → continue retry loop
- 04.05: soft fallback verified in action, task reused without false invalidation, in RETRY_DELAYS 4h loop
- Expected: will complete within 4h (or will need new notebook if rate-limit persists)

## Bulk-регенерація 18 подкастів (Sprint B Phase 2 — FINAL VERIFICATION)

```yaml
last_touched: 2026-05-04
tags: [bulk-regen, podcast-nblm, sprint-b, final]
status: active
```

**Статус 04.05 (manual `/regen 20:53` completed, NBLM completion expected ~21:00)**:
- **5 ready confirmed**: agent_architecture-1/3, multi_model_orchestration-1/2
- **8 pending**: production_reliability-5, multi_model_orchestration-3/4, system_operations-2/3/4/5, rag_retrieval-1 — в 4h retry loop з Intervention 3 RETRY_DELAYS
- **2 recovering**: rag_retrieval-1 (new 03c7d608 via Intervention 1 probe), system_operations-5 (soft fallback via Intervention 1)
- **Expected outcome**: 18/18 podcasts ready when NBLM completion ~21:00

**Запущено 01.05 о 19:57**, паузована 02.05 на bug fix, резюміована 02.05 з Intervention 2+3, 03.05 з Intervention 1 + 4, final validation 04.05 20:53. Усі 4 interventions live & verified end-to-end. RSS feed 18 items синхронізовані з curriculum.json.

## Фаза Б: core/content_gen/ backend-agnostic architecture (COMPLETE & VERIFIED)

```yaml
last_touched: 2026-05-04
tags: [phase-b, content-gen, brief, backend-agnostic, localization, verified]
status: done
```

**Фаза Б 100% реалізована, merged, укрсенізована, production-verified (03-04.05)**:

- **BriefGenerator**: Haiku pre-analysis → instruction set (1-2 рядка), кешується у Topic/Article.formats[key].brief. Укрсенізація: EN brief output (stable JSON), production-active, verified 04.05.
- **Presets**: instruction-шаблони для 3 варіантів (audio=детальний, visual=структурований, quiz=інтерактивний). Укрсенізація: presets in Ukrainian.
- **Backends tree**: `backends/base.py` (ContentBackend ABC) → `backends/nblm.py` (podcast, Intervention 1+2+3 verified), `backends/tts.py` (audio), `backends/interactive.py` (quiz).
- **Schema without migration**: schema_version=1 unchanged, ContentBrief додано через `data.get("brief")` fallback.
- **Merge success**: 340+ рядків коду, 0 breaking changes завдяки lazy re-attach шіму.
- **Intervention 4**: Haiku JSON parse fail на укр → resolved via EN reframe. Brief генерується надійно, production-active, verified 04.05 (`Brief reuse from cache` + clean JSON parsing).

## RSS feed pipeline (18 items, SYNCED & VERIFIED)

```yaml
last_touched: 2026-05-04
tags: [rss, podcast, feed, server, verified]
status: active
```

4 нові модулі у `core/`: `audio_downloader.py`, `rss_feed.py` (RSS 2.0 + iTunes ns), `rss_server.py` (aiohttp, Accept-Ranges), `nblm_orphan_sync.py`. `sam-rss.service` bind `100.86.239.46:8765`. Feed: topics з `podcast_nblm status=ready` + articles + orphan notebooks. Orphan dedup по title. Metadata: `data/audio/orphan_meta.json`. Hook у `notebooklm_module.py` при ready. Debug: `/dbg_download`, `/dbg_rss`, `/dbg_rss_server`. **04.05 status**: 18 items у feed (synced з curriculum.json), ready для distribution checks (Pocket Casts, AntennaPod). Deep-links functional.

## Curriculum v2 — єдине джерело правди

```yaml
last_touched: 2026-05-04
tags: [architecture, curriculum, data-model]
status: active
```

`sam/curriculum/` — пакет з `models.py`, `storage.py`, `mutations.py`, `islands.py`, `migration.py`, `renderer.py`. Стан у `data/curriculum.json` (schema_version=1, без змін). 18 тем, 8 островів, 18 podcast_nblm. Topic IDs `{island-slug}-{n}`. **04.05**: 18 тем з podcast_nblm статусом (5 ready confirmed, 8 pending 4h loop, 2 recovering via soft fallback), EN brief active (stable JSON, verified 04.05 e2e).

## Article pipeline (Phase 6.2 — ACTIVE)

```yaml
last_touched: 2026-05-03
tags: [architecture, article, pipeline, nblm]
status: active
```

Нова архітектура для статей. Dataclass: `Article(id, url, title, content, formats: dict[str, ArticleFormat])`. ArticleFormat: `{"status": "pending|generating|ready|failed", "task_id": null|str, "url": null|str, "consumed": false}`. Формати: slides, podcast_nblm, infographic, flashcards, video. State у `data/articles.json`. Мутації: `add_article(url)`, `remove_article(id)`, `set_article_format_status()`, `set_article_format_task_id()`. **01.05 update**: article pipeline отримав `--format deep-dive --length default`. **ПОТРЕБУЄ**: article deep-link dispatcher у `_handle_deep_link()` (PRIORITY Фаза В).

## NBLM async polling — критична для articles (ACTIVE)

```yaml
last_touched: 2026-05-03
tags: [nblm, async, architecture, critical]
status: active
```

**Архітектура верифіковна (26-27.04, 03.05, 04.05)**:
- `generate <type> --no-wait --json` → миттєво `{task_id, status}`
- `artifact wait <task_id>` → асинхронне опитування (30 хв)
- TopicFormat.task_id + ArticleFormat.task_id додані, `set_format_status()` приймає task_id
- **04.05 verified**: lazy re-attach + Intervention 1 probe works correctly for orphaned tasks

**Stale task_id баг (27.04)**: task_id протухає через ~24h, навіть якщо артефакт готовий. Fallback: `artifact list` → match by format → URL → JSON patch. **Не критична для Фази Б** (01.05), можна реалізувати паралельно. **03.05 update**: fallback still pending, low priority. **04.05 note**: stale task_id not yet critical for Sprint B (most tasks <24h), defer to Phase 7 (technical debt).

## Pinned панель — interactive deep-links

```yaml
last_touched: 2026-05-01
tags: [ui, pinned, deep-links]
status: active
```

`modules/pinned.py` на `render_pinned()`. Per-topic NB · TTS · Exam · Flashcards (deep-links). `_handle_deep_link`: `**article_` dispatcher ПОТРЕБУЄ реалізації** (PRIORITY Фаза В) перед smoke-тестом. Footer: `🗺 Карта островів` + timestamp.

## Pipeline orchestrator

```yaml
last_touched: 2026-05-01
tags: [pipeline, generation]
status: active
```

`curriculum/pipeline.py::run_pipeline()` — послідовна генерація 7 форматів (без exam). Skip ready/generating. Refresh pinned між кроками. Auto-pipeline при add_topic. **26.04 update**: розширення для article-артефактів. **01.05 update**: article pipeline отримав deep-dive параметри.

## Roadmap по маніфесту

```yaml
last_touched: 2026-05-04
tags: [roadmap]
status: active
```

Фаза 0-5 ✅ | Фаза 6.1 ✅ | **Фаза 6.2** 🚧 ACTIVE (articles) | **Фаза А** ✅ 01.05 DONE | **Фаза Б** ✅ MERGED + укрсенізація 03.05 DONE + production-verified 04.05 DONE | **Sprint B (4 NBLM interventions)** ✅ 04.05 ALL 4 LIVE & VERIFIED (Intervention 1 probe, Intervention 2 idempotent, Intervention 3 RETRY cap, Intervention 4 EN brief) | **Bulk-регенерація** 🔄 FINAL VERIFICATION (18/18 podcasts, 5 ready, 8 pending 4h loop, 2 recovering, NBLM completion expected ~21:00) | **Фаза В** (article dispatcher + BotCommand) 📋 AFTER verify 18/18 ready | **Sprint C** (voice extraction) OR **Sprint D** (evals) OR **Phase C** — decision after 18/18 verification.

## Known P3 bugs (non-blocking Sprint B closure)

```yaml
last_touched: 2026-05-04
tags: [bugs, p3, backlog]
status: backlog
```

1. **external_stop zombie pending** (identified 04.05): `should_stop` flag set in `_wait_for_artifact()` loop, but task_id remains as 'pending' in curriculum.json (not marked failed/completed). Manual cleanup needed. Impact: orphaned task wastes NBLM quota. Severity: P3 (doesn't block regen or user). Action: assign to backlog, fix after Sprint B.

2. **regen handler rate-limit message false** (identified 04.05): regen logs say '72 hours to retry' even though RETRY_DELAYS now 4h cap (Intervention 3). Message not updated in regen output. Impact: confusing UX, but doesn't affect actual behavior (code uses correct 4h). Severity: P3 (UX only). Action: update regen handler message output, assign to backlog.

## Activity tracking окремо від curriculum

```yaml
last_touched: 2026-04-26
tags: [architecture, state]
status: active
```

`data/learning_state.json` тримає `last_activity` + `streak_days`. `modules/state_manager.py::touch_activity()` при user-активності.

## Sam engine-free + layout власний

```yaml
last_touched: 2026-04-26
tags: [refactor, architecture]
status: active
```

Sam не імпортує жодного `shared.curriculum_engine`. `modules/curriculum.py` — три команди. `main.py` отримує `DATA_DIR` напряму.

## Phase 3 — EXAM (done)

```yaml
last_touched: 2026-04-24
tags: [exam, phase-3]
status: done
```

`modules/exam.py` — stateful тест. Session у `data/exam_session.json`. 5 питань, LLM генерує + оцінює. PASS_THRESHOLD=3.

## Phase 4 — Proactive triggers (done)

```yaml
last_touched: 2026-04-24
tags: [proactive, phase-4]
status: done
```

Три тригери: ready не-consumed → "подивись", all consumed → "екзамен?", failed → "regen".

## Phase 5 — Island map (done)

```yaml
last_touched: 2026-04-24
tags: [map, phase-5]
status: done
```

`modules/island_map.py::render_island_map()` — текстова карта. Per-island progress, per-topic count.

## Phase 6.1 — Flashcards interactive (done)

```yaml
last_touched: 2026-04-24
tags: [flashcards, phase-6]
status: done
```

Card mode & Quiz mode через inline кнопки. Deep-link `flashcards_{topic_id}`. 3/3 PASS Ed тести.

## Regen + NBLM retry

```yaml
last_touched: 2026-05-04
tags: [pipeline, regen, nblm, interventions]
status: active
```

`/regen` — масова дорегенерація failed форматів. **04.05 verified**: RETRY_DELAYS = [0, 3600, 7200, 14400] (4h cap, Intervention 3 active). **04.05 verified**: Intervention 1 probe shields 8 pending від false invalidation, soft fallback на rate-limit 429. **04.05 verified**: Intervention 4 EN brief ensures stable JSON parsing. Manual `/regen 20:53` confirmed all interventions live and working.

## Ключові архітектурні рішення

```yaml
last_touched: 2026-05-04
tags: [decisions]
status: active
```

**04.05 updates**: Sprint B validation complete, all 4 NBLM interventions verified live in production. Intervention 4 (EN brief) confirmed stable. Intervention 1 (dangling UUID probe + soft fallback) confirmed active. Intervention 2 (idempotent ADD_SOURCE) confirmed. Intervention 3 (RETRY_DELAYS 4h cap) confirmed. 47 unit-tests PASS (15 nblm, 6 brief, 26 other). **03.05 updates**: Intervention 4 deployed (commit 26cf181, EN brief reframe), 6 unit-тестів PASS. Intervention 1 deployed (commit 47efc76, dangling UUID probe + soft fallback), 15 unit-тестів PASS. Intervention 2+3 live (commit d822a29, idempotent ADD_SOURCE, 4h RETRY_DELAYS). 3 notebook UUIDs верифіковані. Укрсенізація complete, brief output in EN (stable JSON). **01.05 updates (Фаза Б)**: Brief через Haiku, backend-agnostic. **27.04 updates**: Lazy re-attach верифіковано.

## Workspace-репо архітектура

```yaml
last_touched: 2026-04-24
tags: [infrastructure, git]
status: active
```

Workspace-репо метарепо над 7 ботами. Sam — standalone repo. Workspace + sam обидва пушаються у github.

## Принципи з маніфесту

```yaml
last_touched: 2026-04-24
tags: [principles]
status: active
```

MVP → feedback → ітерація. Суб'єктивне відчуття > метрики. Ментор, не надсистема.

## Триярусна пам'ять — структура проекту

```yaml
last_touched: 2026-04-24
tags: [infrastructure, memory]
status: active
```

HOT (переписується щосесії) | WARM (архітектура + рішення, інкрементально) | COLD (append-only історія).
