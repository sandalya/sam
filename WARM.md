---
project: sam
updated: 2026-05-03
---

# WARM — Sam

## NBLM podcast_nblm bug: premature 'mark generating' — ROOT CAUSE IDENTIFIED & FIXED & END-TO-END VERIFIED

```yaml
last_touched: 2026-05-03
tags: [nblm, bug, root-cause, generation-pipeline, resolved]
status: resolved
```

**BUG ROOT CAUSE**: nblm.py:268-273 line `set_format_status('generating')` запускалась **ДО** rate-limit retry loop. Flow:
1. Generate → rate-limit response
2. Loop: retry 3 times, all return rate-limit
3. Step 3 (premature mark): `set_format_status('generating', task_id=None)` → status set, save()
4. Loop exit (all retries failed)
5. Step 5 (failed handling): `set_format_status('failed')` ... але save() with task_id ніколи не виконалась на step 3!

Результат: `status='generating'` з `task_id=None` → stuck forever, retry loop не перезапускається.

**FIX DEPLOYED & END-TO-END VERIFIED 02.05**: видалено Step 3 (4 рядки): `set_format_status('generating')` + orphaned `save()`. Step 5 вже коректно обробляє failed case. **Status: RESOLVED & TESTED** на tool_use_integration-1 → status=ready, end-to-end confirmed. Fix working.

**4 TOPICS PROCESSED**: tool_use_integration-1 (✅ ready), production_reliability-2/3 (✅ pending, reset), rag_retrieval-1 (✅ pending, reset). production_reliability-5 потребує manual reset (retry до ~03.05 19:26).

**5 PODCASTS READY**: agent_architecture-1/3 (old deep-dive, ~9.5 min), multi_model_orchestration-1/2, system_operations-5 (legacy з modules/notebooklm.py, не перегенеровані у Фазі Б). Подальше: перегенерація при Фазі В чи bulk-regen.

**8 PENDING PODCASTS**: production_reliability-5 (retry до 03.05 19:26), multi_model_orchestration-1/2, system_operations-2/3/4/5, rag_retrieval-1 (ready, потребує `/regen` для podcast_nblm). 13 тем у попередньому bulk-regen 01.05, 5 ready, 8 pending.

**2 FAILED PODCASTS (new isolation)**: rag_retrieval-1 (notebook 0daaf506 broken, sources скорочено до 1 вручну), system_operations-5 (notebook 2d0285dd silent rc=1 навіть після cleanup, 6+ sources → 1). Потребує нових clean notebook'ів або прямої NBLM CLI диагностики.

**STALE TASK_ID FALLBACK** (окремий баг, низький пріоритет): video format 19826355 + 7af67aad — task_id протухає через ~24h в NBLM API. Fallback потребує реалізації: N timeout × 5 → `artifact list` → match by format → URL patch (відкладено).

**RETRY_DELAYS CANDIDATE**: 72h послідовно (71 година × 72 = 5112h total, або ~24d для послідовного retry) — кандидат на скорочення на 24h залежно від API recovery SLA. Потребує тестування.

## Фаза Б: core/content_gen/ пакет (IMPLEMENTED, MERGED, УКРСЕНІЗАЦІЯ COMPLETE)

```yaml
last_touched: 2026-05-03
tags: [architecture, content-gen, brief, phase-b, backend-agnostic]
status: done
```

**Фаза Б — core/content_gen/ архітектура РЕАЛІЗОВАНА & MERGED до main**: Backend-agnostic design для генерації контенту. Модулі:
- `brief.py`: BriefGenerator (Haiku pre-analysis) → instruction set (1-2 рядка), cache у Topic/Article.formats[key].brief. **03.05 update**: укрсенізація merged, brief output in Ukrainian, Haiku JSON parse fail на укр промпті (fallback спрацьовує, потребує дослідження).
- `presets.py`: instruction-темплети для 3 варіантів (audio=детальний, visual=структурований, quiz=інтерактивний). **03.05 update**: укрсенізація merged, presets in Ukrainian.
- `backends/base.py`: ContentBackend base клас, кожен backend отримує Topic/Article + brief + контекст.
- `backends/nblm.py`: NBLM podcast-генерація, deep-dive+length+format_modifier параметри. **03.05 investigation**: auto ADD_SOURCE при regen засмічує notebook, потребує дослідження add_source логіки.
- `backends/tts.py`: TTS для audio-articles.
- `backends/interactive.py`: quiz/flashcards з інтерактивною логікою.

**Schema БЕЗ міграції**: schema_version=1 без змін, ContentBrief додано через `data.get("brief")` fallback (старі JSON завантажуються коректно). ContentBrief dataclass у Topic/Article. Merge у main: 340+ рядків коду, 0 breaking changes завдяки lazy re-attach шіму.

**Test результати (agent_architecture-3)**: Haiku-brief генерація ~4с, 6 концептів у brief, NBLM з параметрами (deep-dive, length, format_modifier) передаються коректно, звук явно кращий за дефолт. **01.05 UPDATE: MERGE COMPLETE** — stable, готова до production. **03.05 UPDATE**: укрсенізація complete, production-deployed, brief output in Ukrainian.

## NBLM formato deep-dive integration (Фаза А — COMPLETE)

```yaml
last_touched: 2026-05-03
tags: [nblm, format, рефакторинг, quality]
status: done
```

**Фаза А NBLM рефакторингу ЗАВЕРШЕНА**: глобальний проброс `--format deep-dive --length default` у pipeline для article-generation. Звучить явно краще за дефолт, протестовано на `agent_architecture-1` теми (~9.5 хв регенерація). Інтеграція у `notebooklm_module.py` проста. Topic.content_style = Literal["audio", "visual"] (не місце для інструкцій). 4 файли змінено (core/notebooklm_module.py, curriculum/pipeline.py, modules/notebooklm.py, modules/article.py). Merge виконано 01.05, stable. **03.05 update**: deep-dive параметри підтримуються, 5 podcasts ready з deep-dive форматом, укр brief активна.

## Bulk-регенерація 13 подкастів (Фаза Б Phase 2 — ACTIVE, 2 FAILED ISOLATED)

```yaml
last_touched: 2026-05-03
tags: [bulk-regen, podcast-nblm, phase-b, debugging]
status: active
```

**Запущено 01.05 о 19:57**: `/regen --only podcast_nblm` для 13 тем (всі крім agent_architecture-1 і agent_architecture-3). Теми: tool_use_integration-1, agent_architecture-2/3, production_reliability-2/3/4/5, multi_model_orchestration-1/2, system_operations-2/3/4/5. Параметри: brief через Haiku (кешується), NBLM з deep-dive+length. Статус: **PAUSED** через bug виявлення (premature mark generating). 3 topic reset до pending.

**02.05 UPDATE: RESUMED**: tool_use_integration-1 end-to-end verified ready, fix confirmed working. **03.05 UPDATE**: 5 podcasts ready, 8 pending rate-limit, **2 FAILED ISOLATED**: rag_retrieval-1 (notebook 0daaf506 broken), system_operations-5 (silent rc=1 2d0285dd). Наступний крок: нові clean notebook'и для обох тем, reset до pending, `/regen --only podcast_nblm`. Моніторинг: першi 1-2 теми швидко (< 1 хв), решта в rate-limit retry-loop (RETRY_DELAYS = 71 година послідовно, ~24-72 год total). Lazy re-attach бере на себе async polling.

## RSS feed pipeline

```yaml
last_touched: 2026-05-03
tags: [rss, podcast, feed, server]
status: active
```

4 нові модулі у `core/`: `audio_downloader.py` (idempotent NBLM download, `--no-clobber`), `rss_feed.py` (RSS 2.0 + iTunes ns, curriculum + orphan bonus), `rss_server.py` (aiohttp, Accept-Ranges для Pocket Casts seek), `nblm_orphan_sync.py` (list→dedup→filter→download→meta). `sam-rss.service` — bind `100.86.239.46:8765`, окремий процес від Sam (незалежний lifecycle). Feed: topics з `podcast_nblm status=ready` + articles + orphan notebooks не з curriculum. Orphan dedup по title (case-insensitive, keep newest `created_at`). Metadata: `data/audio/orphan_meta.json`. Hook у `notebooklm_module.py`: після `save()` при `ok and fmt=="podcast_nblm"` → `asyncio.create_task(regenerate_feed_async())`, non-fatal. Debug hooks: `/dbg_download`, `/dbg_rss`, `/dbg_rss_server`, `/dbg_nblm_sync`. Ed: `skip_judge: true` у `engine.py` — детерміністичні кейси без LLM judge ($0). Блоки 20/21/22 PASS. **03.05 update**: 14 items у feed, AntennaPod app працює коректно, укр brief활 в meta.

## Curriculum v2 — єдине джерело правди

```yaml
last_touched: 2026-05-03
tags: [architecture, curriculum, data-model]
status: active
```

`sam/curriculum/` — пакет з `models.py`, `storage.py`, `mutations.py`, `islands.py`, `migration.py`, `renderer.py`. Стан у `data/curriculum.json` (schema_version=1, без змін). 17 тем, 8 островів, 16 audio + 2 visual. Topic IDs `{island-slug}-{n}`. **27.04 update**: Article dataclass з 5-ти форматів, task_id поле для async tracking — верифіковано на проді через lazy re-attach. **01.05 update**: ContentBrief додано у Topic/Article, без зміни schema_version. **03.05 update**: 16/18 тем з podcast_nblm статусом (5 ready, 8 pending, 2 failed + orphan), укр brief активна.

## Article pipeline (Phase 6.2 — ACTIVE)

```yaml
last_touched: 2026-05-03
tags: [architecture, article, pipeline, nblm]
status: active
```

Нова архітектура для статей. `/article <URL>` → fetch контенту → Claude аналіз → генерація артефактів. Dataclass: `Article(id, url, title, content, formats: dict[str, ArticleFormat])`. ArticleFormat: `{"status": "pending|generating|ready|failed", "task_id": null|str, "url": null|str, "consumed": false}`. Формати: slides, podcast_nblm, infographic, flashcards, video (5 форматів). State у `data/articles.json` або `CurriculumState.articles`. Мутації: `add_article(url)`, `remove_article(id)`, `set_article_format_status(id, fmt, status)`, `set_article_format_task_id(id, fmt, task_id)`. Pinned: '📑 Статті (N)' з розширюваним списком чекбоксів. **01.05 update**: article pipeline отримав `--format deep-dive --length default` параметри через modules/article.py. Flow: `/article` → opt-in via 🚀 → генерація послідовна → NBLM async polling для кожного формату. **ПОТРЕБУЄ (PRIORITY Фаза В)**: article deep-link dispatcher у `_handle_deep_link()` перед smoke-тестом.

## NBLM async polling — критична для articles (ACTIVE)

```yaml
last_touched: 2026-05-03
tags: [nblm, async, architecture, critical, add-source-bug]
status: active
```

**Архітектура верифікована (26-27.04)**:
- `generate <type> --no-wait --json` → миттєво `{task_id, status}`, не блокує.
- `artifact wait <task_id> --timeout 1800` → асинхронне опитування (30 хв).
- TopicFormat.task_id + ArticleFormat.task_id додані, `set_format_status()` приймає task_id.

**27.04 update — Stale task_id баг** (критичний): task_id протухає через ~24h у API, навіть якщо артефакт готовий. CLI `artifact wait` повертає `timeout` замість `completed`. Видно по 5+ timeout поспіль без completed між ними. Fallback: `artifact list -n <notebook_id>` → match by format → URL → JSON patch. **Потребує реалізації** у `_wait_for_artifact()` (не критична для Фази Б, можна відкласти). **01.05 update**: Фаза Б не залежить від цього fallback, можна реалізувати паралельно. **03.05 update**: fallback still pending, low priority.

**03.05 update — ADD_SOURCE auto bug (новий)**: auto ADD_SOURCE при regen засмічує notebook, cleanup sources не допомагає. Потребує дослідження `backends/nblm.py::add_source()` логіки (куди додаються sources, чи глобальні для notebook). Можливе рішення: skipp ADD_SOURCE якщо notebook вже має > N sources, або видалити old sources перед ADD_SOURCE.

**Lazy re-attach верифіковано**: task 7af67aad (video для article_6a578102) re-attach при рестарті 18:54 успішно. `post_init` скан `curriculum.json` для formats з `status=generating + task_id`, `asyncio.create_task(generate_and_notify(...))` зі `skip_source=True`. Phase 1 пропущена (skip-source + наявний task_id), Phase 2 wait loop активна. **01.05 update**: Lazy re-attach шім у modules/notebooklm.py (14 рядків) дозволяє main.py не знати про brief — backward-compatible з старим кодом. **03.05 update**: shim working, no issues with Ukrainian brief.

## Activity tracking окремо від curriculum

```yaml
last_touched: 2026-04-26
tags: [architecture, state]
status: active
```

`data/learning_state.json` тримає `last_activity` + `streak_days`. `modules/state_manager.py::touch_activity()` при user-активності. Artifact-consumed у `Topic.formats[key].consumed`.

## Sam engine-free + layout власний

```yaml
last_touched: 2026-04-26
tags: [refactor, architecture]
status: active
```

Sam не імпортує жодного `shared.curriculum_engine`. Залишились справжні shared: `agent_base`, `logger`, `token_tracker`, `errors`, `conversation_store`, `catchup_module`, `digest_module`. `modules/curriculum.py` — три команди: `cmd_cur_add`, `cmd_done`, `cmd_regen`. `main.py` отримує `DATA_DIR` напряму.

## Sam layout

```yaml
last_touched: 2026-04-26
tags: [layout, imports]
status: active
```

WorkingDirectory=/workspace/sam + sys.path.insert(0, '/workspace'). ENV: systemd EnvironmentFile=/workspace/sam/.env.

## Phase 3 — EXAM (done)

```yaml
last_touched: 2026-04-24
tags: [exam, phase-3]
status: done
```

`modules/exam.py` — stateful тест. Session у `data/exam_session.json`. 5 питань, LLM генерує + оцінює. PASS_THRESHOLD=3. Deep-link `exam_{topic_id}` в pinned. Intercept в handle_text.

## Phase 4 — Proactive triggers (done)

```yaml
last_touched: 2026-04-24
tags: [proactive, phase-4]
status: done
```

Три тригери: ready не-consumed → "подивись", all consumed → "екзамен?", failed → "regen". Exam subtopic suggestion.

## Phase 5 — Island map (done)

```yaml
last_touched: 2026-04-24
tags: [map, phase-5]
status: done
```

`modules/island_map.py::render_island_map()` — текстова карта. Per-island progress, per-topic count. Deep-link `map`. Pinned footer: `🗺 Карта островів`.

## Phase 6.1 — Flashcards interactive (done)

```yaml
last_touched: 2026-04-24
tags: [flashcards, phase-6]
status: done
```

Перереиспользується NBLM ключ. Card mode & Quiz mode через inline кнопки. Deep-link `flashcards_{topic_id}` в pinned. Ed тести: 3 блоки, 3/3 PASS.

## Regen + NBLM retry

```yaml
last_touched: 2026-05-03
tags: [pipeline, regen, nblm]
status: active
```

`/regen` — масова дорегенерація failed формативів. Reset failed→pending, `run_pipeline` послідовно у фоні. NBLM retry: `RETRY_DELAYS = [0] + [3600] * 71` (~72 год, потребує перевірки скорочення на 24h). **03.05 update**: 2 failed topics потребують нових clean notebook'ів перед retry (rag_retrieval-1 + system_operations-5), решта 8 pending в rate-limit loop.

## TTS deep-link fix (done)

```yaml
last_touched: 2026-04-24
tags: [ui, tts, deep-links]
status: done
```

Проблема: `/tts_{topic_id}` не надсилав файл. Виправлено: абсолютний путь + файл-перевірка.

## NBLM reset для Multi-agent координації (done)

```yaml
last_touched: 2026-04-24
tags: [nblm, pipeline]
status: done
```

MISSING→pending, перезапуск через `run_pipeline()`.

## Pinned панель — interactive deep-links

```yaml
last_touched: 2026-05-01
tags: [ui, pinned]
status: active
```

`modules/pinned.py` на `render_pinned()`. Per-topic NB · TTS · Exam · Flashcards (deep-links). `curriculum/renderer.py`: deep-links для articles. Footer: `🗺 Карта островів` + timestamp. `_handle_deep_link`: fmtcheck_, pipeline_, exam_, map, tts_, flashcards_, **article_** (ПОТРЕБУЄ реалізації dispatcher для articles — PRIORITY Фаза В).

## Pipeline orchestrator

```yaml
last_touched: 2026-05-01
tags: [pipeline, generation]
status: active
```

`curriculum/pipeline.py::run_pipeline()` — послідовна генерація 7 форматів (без exam). Skip ready/generating. Refresh pinned між кроками. Auto-pipeline при add_topic. **26.04 update**: розширення для article-артефактів. **01.05 update**: article pipeline отримав deep-dive параметри. **Потребує**: article deep-link dispatcher у pinned.py для Фази В.

## Tool add_topic в agentic loop

```yaml
last_touched: 2026-04-24
tags: [tools, agentic]
status: active
```

`core/tools.py`: 6 tools у SAM_TOOLS. `add_topic` handler — LLM визначає острів, why/read/do/content_style. Auto-pipeline після add_topic.

## BotCommand list

```yaml
last_touched: 2026-05-01
tags: [ui, telegram]
status: active
```

`set_my_commands`: cur, jobs, notebooks, status, regen, flashcards. **ПОТРЕБУЄ додавання**: `article`, `article_del` (LOW PRIORITY, Фаза В).

## Roadmap по маніфесту

```yaml
last_touched: 2026-05-03
tags: [roadmap]
status: active
```

Фаза 0-5 ✅ | Фаза 6.1 ✅ | **Фаза 6.2** 🚧 ACTIVE (articles) | **Фаза А (NBLM deep-dive)** ✅ 01.05 DONE | **Фаза Б (brief.py + backend-agnostic)** ✅ 01.05 IMPLEMENTED + merge COMPLETE, **укрсенізація 03.05 COMPLETE** | **Bulk-регенерація 13 подкастів** 🔄 ACTIVE (5 ready, 8 pending, 2 failed isolated) | **Фаза В (article dispatcher + BotCommand)** 📋 NEXT | Фаза 6.3+ (SR / export / Depth Mode — відкладена після 1-2 тижнів використання articles). Паралельно: масштабування триярусної пам'яті на Meggy, Ed, Garcia, Abby-v2.

## Ключові архітектурні рішення

```yaml
last_touched: 2026-05-03
tags: [decisions]
status: active
```

**03.05 updates**: Укрсенізація brief.py + presets.py merged, production-active, brief output in Ukrainian. 16/18 podcasts ready/pending, 2 failed (rag_retrieval-1 UUID 0daaf506 broken, system_operations-5 rc=1 2d0285dd) потребують нових clean notebook'ів. ADD_SOURCE auto bug виявлено (засмічує notebook), потребує дослідження. Haiku JSON parse fail на укр промпті (fallback спрацьовує). **01.05 updates (Фаза Б)**: Brief-генерація через Haiku, backend-agnostic: backends/ дерево (nblm, tts, interactive), кожен backend отримує brief + контент через ContentBackend ABC. `prepare_and_generate()` API. БЕЗ schema migration. ContentBrief у Topic/Article. Lazy re-attach шім для backward-compat. **01.05 update (bug fix)**: Premature 'mark generating' (Step 3) видалено з nblm.py:268-273; Step 5 (failed handling) достатньо. 3 topics reset до pending. **01.05 update (Фаза А)**: Deep-dive format через --format flag у notebooklm_module, звучить краще. Інтегровано в article pipeline. Topic.content_style = Literal[audio/visual], НЕ місце для інструкцій. **27.04 updates**: Lazy re-attach верифіковано через рестарт з active task (task 7af67aad). `post_init` скан `curriculum.json` для `status=generating + task_id` → `asyncio.create_task(generate_and_notify(...))` зі skip-Phase-1 логікою. **Stale task_id fallback**: timeout × 5 → `artifact list` → match by format → URL → JSON patch (потребує реалізації, не критична). **Article dispatcher (Фаза В)**: потребує `article_` handler у `_handle_deep_link` (PRIORITY). Інші рішення як раніше: Аккордеон через editMessageText, Exam stateful session в JSON, Regen через create_task, Island map текстовий, Proactive 3 тригери, Flashcards переиспользує NBLM, Ed MessageEdited listener, Articles окремо від тем.

## Workspace-репо архітектура

```yaml
last_touched: 2026-04-24
tags: [infrastructure, git]
status: active
```

Workspace-репо метарепо над 7 ботами. Sam — standalone repo. Workspace + sam обидва пушаються у github. З 23.04: 6 проектів з HOT/WARM/COLD.

## Garcia — поза скоупом

```yaml
last_touched: 2026-04-24
tags: [garcia, deprecated]
status: paused
```

Garcia deprecated у Sam контексті. З 23.04 мігрована на triadic memory.

## Принципи з маніфесту

```yaml
last_touched: 2026-04-24
tags: [principles]
status: active
```

MVP → feedback → ітерація. Суб'єктивне відчуття > метрики. Ментор, не надсистема. Структура еволюціонує. Анти-патерни: немає авто-статусів за часом, немає prerequisites, немає спаму, немає Depth Mode на старті.

## Триярусна пам'ять — структура проекту

```yaml
last_touched: 2026-04-24
tags: [infrastructure, memory]
status: active
```

HOT (переписується щосесії) | WARM (архітектура + рішення, інкрементально) | COLD (append-only історія). З 2026-04-19. chkp2 автоматизує. З 23.04 масштабована на 6 проектів.

## chkp — yaml-registry для триярусної пам'яті

```yaml
last_touched: 2026-04-24
tags: [infrastructure, chkp, tools]
status: active
```

`meta/chkp/projects.yaml` реєстр. `--init` scaffold. Готова для 6 проектів.

## Workspace administration

```yaml
last_touched: 2026-04-24
tags: [infrastructure, workspace]
status: blocked
```

Структура 18 memory-файлів + kit/ утиліти не визначена. Варіанти: окремий workspace-memory/ репо, монолітна kit/, децентралізовано. Потребує дизайну перед масштабуванням.

## Meggy, Ed, Abby-v2, Insilver-v3 на триярусній пам'яті

```yaml
last_touched: 2026-04-24
tags: [infrastructure, projects]
status: active
```

Ед + Інсільвер готові до розробки. Meggy потребує реальної сесії. Abby-v2 має key blocker (paid generation button broken). Garcia паузована.
