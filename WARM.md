---
project: sam
updated: 2026-05-03
---

# WARM — Sam

## Intervention 1: dangling UUID probe + soft fallback (03.05 — LIVE)

```yaml
last_touched: 2026-05-03
tags: [nblm, probe, dangling-uuid, soft-fallback, intervention, deployed]
status: active
```

**Intervention 1 fully implemented, unit-tested (15/15), deployed to prod (commit 47efc76)**:

1. **Dangling UUID probe mechanism**:
   - File: `sam/core/content_gen/backends/nblm.py` (~line 145-160, new method `_probe_artifact_alive(task_id)`)
   - Logic: before reusing orphaned task_id, call `artifact status <task_id>` → detect null RPC as dangling marker
   - Probe outcomes:
     - `probe_ok=True`: live UUID, safe to reuse in `_wait_for_artifact()`
     - `probe_ok=False`: null RPC or 400-level response → dangling, trigger invalidate+create flow
     - `probe_rc` special: rate_limit (429) → soft fallback enabled

2. **Soft fallback for rate-limited probes**:
   - If probe returns rc≠0 AND error_type='rate_limit' → don't invalidate, reuse old task_id with warning
   - Prevents cascade failures: transient Google rate-limit doesn't nuke entire lazy re-attach flow
   - Still waits in `_wait_for_artifact()` loop, respects RETRY_DELAYS

3. **Decision tree** (replaces old logic):
   ```
   if probe_ok: reuse task_id, proceed to _wait
   elif rc==0 AND JSON null: invalidate+create
   elif rc==0 AND JSON error: invalidate+create
   elif rc≠0 AND rate_limit: soft reuse (warn, don't invalidate)
   elif rc≠0 other: invalidate+create
   ```

4. **End-to-end verification**:
   - **rag_retrieval-1 (0daaf506 dangling)**: `/regen --only podcast_nblm` → probe detects null RPC → invalidate → create new 03c7d608 → logs show WARNING + INFO ✓
   - **2 orphaned video tasks (42a0b26a, e85f7ded live)**: lazy re-attach → probe passes → reuse without invalidation ✓
   - **rate-limit scenario**: probe 429 → soft fallback → reuse instead of false invalidate ✓

5. **Unit-tests: 15/15 PASS** (0.062s):
   - 11 from Intervention 2+3 (idempotent ADD_SOURCE, RETRY_DELAYS, null-RPC)
   - 3 new: `test_probe_detects_dangling()`, `test_invalidate_on_dangling_probe()`, `test_create_new_on_invalidate()`
   - 1 fallback: `test_soft_reuse_on_probe_rate_limit()`

**Deployment**: commit 47efc76 live on main. systemd sam.service ready for restart. 8 pending podcasts now shielded from false invalidation on transient rate-limits.

## Intervention 2+3: idempotent ADD_SOURCE + RETRY_DELAYS 4h cap + structured error (03.05 — DEPLOYED)

```yaml
last_touched: 2026-05-03
tags: [nblm, bug, intervention, unit-tests, deployed]
status: active
```

**Intervention 2+3 fully implemented, tested, deployed (commit d822a29)**:

1. **Intervention 2: idempotent ADD_SOURCE**:
   - File: `sam/core/content_gen/backends/nblm.py` line ~261
   - Change: перед `add_source()`, прочитати `artifact info` → скан `sources[]` → `if source not in existing_sources: add_source()`
   - Test: `test_add_source_idempotent()` — додавання одного source 2x → тільки 1 у notebook (11/11 PASS)

2. **Intervention 3: RETRY_DELAYS скорочення + structured error**:
   - File: `sam/core/content_gen/backends/nblm.py` (module level)
   - Change: `RETRY_DELAYS = [0, 3600, 7200, 14400]` (4h cap замість [0] + [3600]*71)
   - Structured error: `nblm_{code}` коды (e.g., `nblm_null_rpc` для null response)
   - External stop detection: retry+wait loops слухають `should_stop` flag (graceful shutdown)
   - Test: `test_retry_delays_cap()`, `test_null_rpc_error_structure()`, `test_external_stop_detection()` — 11/11 PASS (0.056s)

**Deployment status**: commit d822a29 live на main, commit 47efc76 extends with Intervention 1. **Next**: `systemctl restart sam.service` на Pi5. 8 pending подкастів матимуть 4h retry loops замість 72h.

## NBLM backend: diagnostic complete, 3 notebook UUIDs verified (03.05)

```yaml
last_touched: 2026-05-03
tags: [nblm, diagnostics, notebook-uuids, bug-isolation]
status: resolved
```

**NBLM diagnostic session 03.05** (2+ hours, pre-Intervention 1):

- **CLI локалізована**: `/workspace/venv/bin/nblm` знайдена у venv, верифікована.
- **3 notebook UUIDs проверены через CLI commands**:
  1. **healthy 8aca66e9** (agent_architecture-1): `nblm artifact status 8aca66e9` → OK, has 2 ідентичні sources [18, 19] (manually added, BUG 2 confirmed, fixed by Intervention 2)
  2. **broken-A 0daaf506** (rag_retrieval-1): `nblm artifact status 0daaf506` → null RPC response (dangling UUID, **now detected by Intervention 1 probe**)
  3. **broken-B 2d0285dd** (system_operations-5): `nblm artifact status 2d0285dd` → RATE_LIMITED 429 (Google, **now soft-fallback protected by Intervention 1**)

- **Bugs root-cause identified**:
  1. ADD_SOURCE дублювання (line 261, BUG 2) → **FIX: Intervention 2 deployed**
  2. RETRY_DELAYS занадто довгий (72h послідовно) → **FIX: Intervention 3 deployed 4h cap**
  3. Bonus JSON edit (low priority) → still pending investigation

## Failed topics action plan — updated with Intervention 1

```yaml
last_touched: 2026-05-03
tags: [bulk-regen, failed-topics, action-plan, intervention-1]
status: active
```

**rag_retrieval-1** (UUID 0daaf506):
- Status: notebook broken (null RPC response)
- **Intervention 1 action**: probe detects dangling → auto-invalidate 0daaf506 → auto-create new 03c7d608 (or similar) → logs show creation. **No manual notebook recreation needed if auto-create succeeds.**
- Fallback: if auto-create fails → manual new notebook through NBLM UI/CLI, update curriculum.json with new UUID.

**system_operations-5** (UUID 2d0285dd):
- Status: RATE_LIMITED 429 (Google API)
- **Intervention 1 action**: probe gets 429 → soft-fallback enabled → reuse task_id without false invalidation → continue waiting in RETRY_DELAYS 4h loop.
- **Next**: sam.service restart → monitor 1-2 retry cycles. If soft-fallback succeeds (task completes), no new notebook needed. If still fails after 4h loop → investigate whether Google notebook limit or different issue → manual new notebook.

## Фаза Б: core/content_gen/ backend-agnostic architecture (COMPLETE)

```yaml
last_touched: 2026-05-03
tags: [phase-b, content-gen, brief, backend-agnostic, localization]
status: done
```

**Фаза Б 100% реалізована & merged & укрсенізована (03.05)**:

- **BriefGenerator**: Haiku pre-analysis → instruction set (1-2 рядка), кешується у Topic/Article.formats[key].brief. Укрсенізація: brief output в українській мові, production-active.
- **Presets**: instruction-шаблони для 3 варіантів (audio=детальний, visual=структурований, quiz=інтерактивний). Укрсенізація: presets in Ukrainian.
- **Backends tree**: `backends/base.py` (ContentBackend ABC) → `backends/nblm.py` (podcast), `backends/tts.py` (audio), `backends/interactive.py` (quiz).
- **Schema without migration**: schema_version=1 unchanged, ContentBrief додано через `data.get("brief")` fallback (старі JSON завантажуються коректно).
- **Merge success**: 340+ рядків коду, 0 breaking changes завдяки lazy re-attach шіму.
- **Haiku JSON parse fail на укр**: fallback спрацьовує, brief все одно генерується (потребує дослідження причини, low priority, можлива Intervention 4).

## Intervention 4: brief.py укр JSON parse fail — ROOT CAUSE INVESTIGATION PENDING

```yaml
last_touched: 2026-05-03
tags: [brief, haiku, json, parse, localization, intervention-4]
status: active
```

**Phenomenon** (observed in bulk-regen 01-03.05): Ukrainian prompts sent to Haiku sometimes result in JSON parse failures (malformed JSON, unexpected char). Fallback activates → brief still generated (кешується null або partial). Does NOT block bulk-regen, low priority.

**Candidates for root cause**:
- Special characters in Ukrainian (кома, лапки, апостроф) not escaped in JSON prompt
- Token limit: укр текст займає більше токенів, Haiku обрізує response
- Haiku model behavior: моделі іноді генерують невалідний JSON на cyrillic prompts
- Locale/encoding issue у prompt construction

**Investigation plan** (parallel, low priority):
1. Log full Haiku prompt + response (raw bytes) on next failure
2. Check if JSON is truncated vs. invalid structure
3. If truncation → adjust token_limit параметр
4. If encoding → verify UTF-8 throughout pipeline
5. If model → consider fallback to EN prompts с post-translation

**Next action for Intervention 4**: запустити dedicate session після Intervention 1 verification on prod.

## Bulk-регенерація 13 подкастів (Фаза Б Phase 2 — ACTIVE)

```yaml
last_touched: 2026-05-03
tags: [bulk-regen, podcast-nblm, phase-b]
status: active
```

**Статус 03.05 (updated with Intervention 1)**:
- **5 ready**: agent_architecture-1/3 (deep-dive ~9.5 min), multi_model_orchestration-1/2, system_operations-5 (legacy, may resume via soft fallback)
- **8 pending**: production_reliability-5, multi_model_orchestration-1/2, system_operations-2/3/4/5, rag_retrieval-1 — у rate-limit retry-loop з новими 4h RETRY_DELAYS (Intervention 3). Тепер захищені від false invalidation (Intervention 1 probe + soft fallback).
- **Failed/recovering**: rag_retrieval-1 (0daaf506 dangling, auto-detected by probe), system_operations-5 (2d0285dd RATE_LIMITED, soft-fallback enabled)

**Expected outcome after sam.service restart + Intervention 1 verification**:
- rag_retrieval-1: probe creates new notebook (или manual) → resume regen
- system_operations-5: soft fallback protects, continue 4h retry loop
- **16+1=17/18 podcasts possible** once both recover

**Запущено 01.05 о 19:57**, паузована 02.05 на bug fix, резюміована 02.05 з Intervention 2+3, тепер 03.05 з Intervention 1 probe protection.

## Фаза А NBLM deep-dive integration (COMPLETE)

```yaml
last_touched: 2026-05-03
tags: [nblm, format, phase-a, quality]
status: done
```

**Фаза А ЗАВЕРШЕНА (01.05)**: глобальний проброс `--format deep-dive --length default` у pipeline для article-generation. Звучить явно краще за дефолт, протестовано на `agent_architecture-1` теми (~9.5 хв регенерація). Інтеграція у `notebooklm_module.py` проста. Topic.content_style = Literal["audio", "visual"] (не місце для інструкцій). 4 файли змінено, merge 01.05 stable.

## RSS feed pipeline

```yaml
last_touched: 2026-05-03
tags: [rss, podcast, feed, server]
status: active
```

4 нові модулі у `core/`: `audio_downloader.py`, `rss_feed.py` (RSS 2.0 + iTunes ns), `rss_server.py` (aiohttp, Accept-Ranges), `nblm_orphan_sync.py`. `sam-rss.service` bind `100.86.239.46:8765`. Feed: topics з `podcast_nblm status=ready` + articles + orphan notebooks. Orphan dedup по title. Metadata: `data/audio/orphan_meta.json`. Hook у `notebooklm_module.py` при ready. Debug: `/dbg_download`, `/dbg_rss`, `/dbg_rss_server`. **03.05 status**: 14 items у feed, AntennaPod app working, укр brief active.

## Curriculum v2 — єдине джерело правди

```yaml
last_touched: 2026-05-03
tags: [architecture, curriculum, data-model]
status: active
```

`sam/curriculum/` — пакет з `models.py`, `storage.py`, `mutations.py`, `islands.py`, `migration.py`, `renderer.py`. Стан у `data/curriculum.json` (schema_version=1, без змін). 17 тем, 8 островів, 16 audio + 2 visual. Topic IDs `{island-slug}-{n}`. **03.05**: 16/18 тем з podcast_nblm статусом (5 ready, 8 pending, 2 recovering/auto-creating), укр brief активна.

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

**Архітектура верифікована (26-27.04)**:
- `generate <type> --no-wait --json` → миттєво `{task_id, status}`
- `artifact wait <task_id>` → асинхронне опитування (30 хв)
- TopicFormat.task_id + ArticleFormat.task_id додані, `set_format_status()` приймає task_id

**27.04 update — Stale task_id баг**: task_id протухає через ~24h, навіть якщо артефакт готовий. Fallback: `artifact list` → match by format → URL → JSON patch. **Не критична для Фази Б** (01.05), можна реалізувати паралельно. **03.05 update**: fallback still pending, low priority. **Lazy re-attach верифіковано**: task 7af67aad re-attach при рестарті 18:54 успішно.

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
last_touched: 2026-05-03
tags: [roadmap]
status: active
```

Фаза 0-5 ✅ | Фаза 6.1 ✅ | **Фаза 6.2** 🚧 ACTIVE (articles) | **Фаза А** ✅ 01.05 DONE | **Фаза Б** ✅ MERGED + укрсенізація 03.05 DONE | **Intervention 2+3** ✅ 03.05 DEPLOYED | **Intervention 1** ✅ 03.05 LIVE (probe + soft fallback) | **Bulk-регенерація** 🔄 ACTIVE (5 ready, 8 pending 4h loops, 2 recovering) | **Фаза В** (article dispatcher + BotCommand) 📋 AFTER verify Intervention 1 | Фаза 6.3+ (SR/export/Depth Mode — відкладена).

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
last_touched: 2026-05-03
tags: [pipeline, regen, nblm]
status: active
```

`/regen` — масова дорегенерація failed форматів. **03.05 update**: RETRY_DELAYS = [0, 3600, 7200, 14400] (4h cap, Intervention 3). **03.05 new**: Intervention 1 probe shields 8 pending від false invalidation, soft fallback на rate-limit 429.

## Ключові архітектурні рішення

```yaml
last_touched: 2026-05-03
tags: [decisions]
status: active
```

**03.05 updates**: Intervention 1 deployed (commit 47efc76, dangling UUID probe + soft fallback), 15 unit-тестів PASS. Intervention 2+3 live (commit d822a29, idempotent ADD_SOURCE, 4h RETRY_DELAYS). 3 notebook UUIDs верифіковані. Укрсенізація complete, production-active. 16+1/18 podcasts: 5 ready, 8 pending 4h loops (shielded), 2 recovering (auto-probe). **01.05 updates (Фаза Б)**: Brief через Haiku, backend-agnostic. **27.04 updates**: Lazy re-attach верифіковано. Інші рішення як раніше.

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