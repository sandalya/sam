---
project: sam
updated: 2026-05-03
---

# WARM — Sam

## NBLM backend: Intervention 2+3 DEPLOYED & unit-tested (03.05)

```yaml
last_touched: 2026-05-03
tags: [nblm, bug, intervention, unit-tests, deployed]
status: active
```

**Intervention 2+3 fully implemented, tested, deployed (commit d822a29)**:

1. **Intervention 2: idempotent ADD_SOURCE** (Completed)
   - File: `sam/core/content_gen/backends/nblm.py` line ~261
   - Change: перед `add_source()`, прочитати `artifact info` → скан `sources[]` → `if source not in existing_sources: add_source()`
   - Test: `test_add_source_idempotent()` — додавання одного source 2x → тільки 1 у notebook (11/11 PASS)

2. **Intervention 3: RETRY_DELAYS скорочення + structured error** (Completed)
   - File: `sam/core/content_gen/backends/nblm.py` (module level)
   - Change: `RETRY_DELAYS = [0, 3600, 7200, 14400]` (4h cap замість [0] + [3600]*71)
   - Structured error: `nblm_{code}` коди (e.g., `nblm_null_rpc` для null response) → сигнал broken UUID
   - External stop detection: retry+wait loops слухають `should_stop` flag (graceful shutdown)
   - Test: `test_retry_delays_cap()`, `test_null_rpc_error_structure()`, `test_external_stop_detection()` — 11/11 PASS (0.056s)

**Deployment status**: commit d822a29 live на main, systemd sam.service прибирає старий код. **Next action**: `systemctl restart sam.service` на Pi5 для активації. 8 pending подкастів матимуть 4h retry loops замість 72h.

## NBLM diagnostic: 3 notebook UUIDs verified, bugs isolated (03.05)

```yaml
last_touched: 2026-05-03
tags: [nblm, diagnostics, notebook-uuids, bug-isolation]
status: resolved
```

**NBLM diagnostic session 03.05** (2+ hours):

- **CLI локалізована**: `/workspace/venv/bin/nblm` знайдена у venv, верифікована.
- **3 notebook UUIDs проверены через CLI commands**:
  1. **healthy 8aca66e9** (agent_architecture-1): `nblm artifact status 8aca66e9` → OK, has 2 ідентичні sources [18, 19] (manually added, BUG 2 confirmed)
  2. **broken-A 0daaf506** (rag_retrieval-1): `nblm artifact status 0daaf506` → null RPC response (dangling UUID, потребує нового notebook)
  3. **broken-B 2d0285dd** (system_operations-5): `nblm artifact status 2d0285dd` → RATE_LIMITED 429 (Google, потребує нового notebook)

- **Backend code analysis**: backends/nblm.py 428→282 рядків (після оптимізації у Session 2):
  - Line 165: substring detect для format matching
  - Line 184-200: wait-loop з exponential backoff (改 для RETRY_DELAYS cap)
  - Line 261: add_source() (改 для idempotent check)
  - RETRY_DELAYS: виведено на module level, скорочено до 4h cap

- **Bugs root-cause identified**:
  1. ADD_SOURCE дублювання: line 261 `add_source()` не скануює існуючі sources перед додаванням → дублювання (FIX: Intervention 2)
  2. RETRY_DELAYS занадто довгий: [0] + [3600]*71 = ~72 год послідовно → медленне recovery від rate-limit (FIX: Intervention 3, 4h cap)
  3. Bonus JSON edit: in-flight async task ігнорує changes, потребує reload (low priority, не блокує bulk-regen)

## 2 Failed topics isolated & action plan

```yaml
last_touched: 2026-05-03
tags: [bulk-regen, failed-topics, action-plan]
status: active
```

**rag_retrieval-1** (UUID 0daaf506):
- Status: notebook broken (null RPC response)
- Root cause: UUID dangling or corrupted у NBLM API
- Action: видалити старий notebook UUID 0daaf506 з curriculum.json, створити новий через NBLM UI/CLI (`nblm notebook create`), отримати новий UUID, оновити curriculum.json, set status=pending, запустити `/regen --only podcast_nblm rag_retrieval-1`

**system_operations-5** (UUID 2d0285dd):
- Status: RATE_LIMITED 429 (Google API)
- Root cause: Google rate-limit на notebook, cleanup джерел не допомагає
- Action: видалити старий notebook UUID 2d0285dd, створити новий, reset topic, `/regen --only podcast_nblm system_operations-5`

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
- **Haiku JSON parse fail на укр**: fallback спрацьовує, brief все одно генерується (потребує дослідження причини, low priority).

## NBLM podcast_nblm bug: premature 'mark generating' — ROOT CAUSE IDENTIFIED & FIXED

```yaml
last_touched: 2026-05-03
tags: [nblm, bug, root-cause, resolved]
status: resolved
```

**BUG ROOT CAUSE (FIXED 02.05)**: nblm.py:268-273 line `set_format_status('generating')` запускалась ДО rate-limit retry loop → `status='generating' + task_id=None` → stuck forever. **FIX**: видалено Step 3 (4 рядки), Step 5 (failed handling) достатня. **Verified**: tool_use_integration-1 end-to-end confirmed ready. **Session 2 CC (03.05)**: обидва Intervention 2+3 коректно обробляють failed cases без premature mark.

## Bulk-регенерація 13 подкастів (Фаза Б Phase 2 — ACTIVE)

```yaml
last_touched: 2026-05-03
tags: [bulk-regen, podcast-nblm, phase-b]
status: active
```

**Статус 03.05**: 16/18 тем:
- **5 ready**: agent_architecture-1/3 (deep-dive ~9.5 min), multi_model_orchestration-1/2, system_operations-5 (legacy)
- **8 pending**: production_reliability-5, multi_model_orchestration-1/2, system_operations-2/3/4/5, rag_retrieval-1 — у rate-limit retry-loop з новими 4h RETRY_DELAYS (замість 72h, скоротить очікування з 24-72h до ~4h)
- **2 failed**: rag_retrieval-1 (UUID 0daaf506 broken), system_operations-5 (UUID 2d0285dd RATE_LIMITED) — потребують нових clean notebooks

**Запущено 01.05 о 19:57**, паузована 02.05 на bug fix, резюміована 02.05 з fixes. Параметри: brief через Haiku (кешується), NBLM з deep-dive+length. Моніторинг: 4h loops для 8 pending, моніторинг після рестарту sam.service.

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

`sam/curriculum/` — пакет з `models.py`, `storage.py`, `mutations.py`, `islands.py`, `migration.py`, `renderer.py`. Стан у `data/curriculum.json` (schema_version=1, без змін). 17 тем, 8 островів, 16 audio + 2 visual. Topic IDs `{island-slug}-{n}`. **03.05**: 16/18 тем з podcast_nblm статусом (5 ready, 8 pending, 2 failed), укр brief активна.

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

Фаза 0-5 ✅ | Фаза 6.1 ✅ | **Фаза 6.2** 🚧 ACTIVE (articles) | **Фаза А** ✅ 01.05 DONE | **Фаза Б** ✅ MERGED + укрсенізація 03.05 DONE | **Bulk-регенерація 13 подкастів** 🔄 ACTIVE (5 ready, 8 pending, 2 failed) | **Session 2 CC: Intervention 2+3** ✅ 03.05 DEPLOYED | **Фаза В** (article dispatcher + BotCommand) 📋 AFTER рестарту + verify | Фаза 6.3+ (SR/export/Depth Mode — відкладена).

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

`/regen` — масова дорегенерація failed форматів. **03.05 update**: RETRY_DELAYS = [0, 3600, 7200, 14400] (4h cap). 8 pending подкастів матимуть скорочену ретрай-очікував замість 72h.

## Ключові архітектурні рішення

```yaml
last_touched: 2026-05-03
tags: [decisions]
status: active
```

**03.05 updates**: Intervention 2+3 deployed (commit d822a29), 11 unit-тестів PASS. 3 notebook UUIDs верифіковані (healthy OK, 2 broken isolated). Укрсенізація complete, production-active. 16/18 podcasts: 5 ready, 8 pending 4h loops, 2 failed потребують нових notebooks. **01.05 updates (Фаза Б)**: Brief через Haiku, backend-agnostic. **27.04 updates**: Lazy re-attach верифіковано. Інші рішення як раніше.

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