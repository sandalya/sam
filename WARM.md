---
project: sam
updated: 2026-05-01
---

# WARM — Sam

## Фаза Б: core/content_gen/ пакет (IMPLEMENTED)

```yaml
last_touched: 2026-05-01
tags: [architecture, content-gen, brief, phase-b, backend-agnostic]
status: active
```

**Фаза Б — core/content_gen/ архітектура реалізована**: Backend-agnostic design для генерації контенту. Модулі:
- `brief.py`: BriefGenerator (Haiku pre-analysis) → instruction set (1-2 рядка), cache у Topic/Article.formats[key].brief.
- `presets.py`: instruction-темплети для 3 варіантів (audio=детальний, visual=структурований, quiz=інтерактивний).
- `backends/base.py`: ContentBackend base клас, кожен backend отримує Topic/Article + brief + kontekst.
- `backends/nblm.py`: NBLM podcast-генерація, deep-dive+length+format_modifier параметри.
- `backends/tts.py`: TTS для audio-articles.
- `backends/interactive.py`: quiz/flashcards з інтерактивною логікою.

**Schema БЕЗ міграції**: schema_version=1 без змін, ContentBrief додано через `data.get("brief")` fallback (старі JSON завантажуються коректно). ContentBrief dataclass у Topic/Article. Merge у main успішна, 12 файлів, +747/-520 рядків, 0 breaking changes.

**Test результати (agent_architecture-3)**: Haiku-brief генерація ~4с, 6 концептів у brief, NBLM з параметрами (deep-dive, length, format_modifier) передаються коректно, звук явно кращий за дефолт.

## NBLM formato deep-dive integration (Фаза А — COMPLETE)

```yaml
last_touched: 2026-05-01
tags: [nblm, format, рефакторинг, quality]
status: done
```

**Фаза А NBLM рефакторингу ЗАВЕРШЕНА**: глобальний проброс `--format deep-dive --length default` у pipeline для article-generation. Звучить явно краще за дефолт, протестовано на `agent_architecture-1` теми (~9.5 хв регенерація). Інтеграція у `notebooklm_module.py` проста. Topic.content_style = Literal["audio", "visual"] (не місце для інструкцій). 4 файли змінено (core/notebooklm_module.py, curriculum/pipeline.py, modules/notebooklm.py, modules/article.py). Diff готовий до merge, merge виконано 01.05.

## RSS feed pipeline

```yaml
last_touched: 2026-04-30
tags: [rss, podcast, feed, server]
status: active
```

4 нові модулі у `core/`: `audio_downloader.py` (idempotent NBLM download, `--no-clobber`), `rss_feed.py` (RSS 2.0 + iTunes ns, curriculum + orphan bonus), `rss_server.py` (aiohttp, Accept-Ranges для Pocket Casts seek), `nblm_orphan_sync.py` (list→dedup→filter→download→meta). `sam-rss.service` — bind `100.86.239.46:8765`, окремий процес від Sam (незалежний lifecycle). Feed: topics з `podcast_nblm status=ready` + articles + orphan notebooks не з curriculum. Orphan dedup по title (case-insensitive, keep newest `created_at`). Metadata: `data/audio/orphan_meta.json`. Hook у `notebooklm_module.py`: після `save()` при `ok and fmt=="podcast_nblm"` → `asyncio.create_task(regenerate_feed_async())`, non-fatal. Debug hooks: `/dbg_download`, `/dbg_rss`, `/dbg_rss_server`, `/dbg_nblm_sync`. Ed: `skip_judge: true` у `engine.py` — детерміністичні кейси без LLM judge ($0). Блоки 20/21/22 PASS.

## Curriculum v2 — єдине джерело правди

```yaml
last_touched: 2026-04-27
tags: [architecture, curriculum, data-model]
status: active
```

`sam/curriculum/` — пакет з `models.py`, `storage.py`, `mutations.py`, `islands.py`, `migration.py`, `renderer.py`. Стан у `data/curriculum.json` (schema_version=1, без змін). 17 тем, 8 островів, 16 audio + 2 visual. Topic IDs `{island-slug}-{n}`. **27.04 update**: Article dataclass з 5-ти форматів, task_id поле для async tracking — верифіковано на проді через lazy re-attach. **01.05 update**: ContentBrief додано у Topic/Article, без зміни schema_version.

## Article pipeline (Phase 6.2 — ACTIVE)

```yaml
last_touched: 2026-05-01
tags: [architecture, article, pipeline, nblm]
status: active
```

Нова архітектура для статей. `/article <URL>` → fetch контенту → Claude аналіз → генерація артефактів. Dataclass: `Article(id, url, title, content, formats: dict[str, ArticleFormat])`. ArticleFormat: `{"status": "pending|generating|ready|failed", "task_id": null|str, "url": null|str, "consumed": false}`. Формати: slides, podcast_nblm, infographic, flashcards, video (5 форматів). State у `data/articles.json` або `CurriculumState.articles`. Мутації: `add_article(url)`, `remove_article(id)`, `set_article_format_status(id, fmt, status)`, `set_article_format_task_id(id, fmt, task_id)`. Pinned: '📑 Статті (N)' з розширюваним списком чекбоксів. **01.05 update**: article pipeline отримав `--format deep-dive --length default` параметри через modules/article.py. Flow: `/article` → opt-in via 🚀 → генерація послідовна → NBLM async polling для кожного формату. **Потребує**: article deep-link dispatcher у `_handle_deep_link()` перед smoke-тестом.

## NBLM async polling — критична для articles (ACTIVE)

```yaml
last_touched: 2026-05-01
tags: [nblm, async, architecture, critical]
status: active
```

**Архітектура верифікована (26-27.04)**:
- `generate <type> --no-wait --json` → миттєво `{task_id, status}`, не блокує.
- `artifact wait <task_id> --timeout 1800` → асинхронне опитування (30 хв).
- TopicFormat.task_id + ArticleFormat.task_id додані, `set_format_status()` приймає task_id.

**27.04 update — Stale task_id баг** (критичний): task_id протухає через ~24h у API, навіть якщо артефакт готовий. CLI `artifact wait` повертає `timeout` замість `completed`. Видно по 5+ timeout поспіль без completed між ними. Fallback: `artifact list -n <notebook_id>` → match by format → URL → JSON patch. **Потребує реалізації** у `_wait_for_artifact()` (не критична для Фази Б, можна відкласти). **01.05 update**: Фаза Б не залежить від цього fallback, можна реалізувати паралельно.

**Lazy re-attach верифіковано**: task 7af67aad (video для article_6a578102) re-attach при рестарті 18:54 успішно. `post_init` скан `curriculum.json` для formats з `status=generating + task_id`, `asyncio.create_task(generate_and_notify(...))` зі `skip_source=True`. Phase 1 пропущена (skip-source + наявний task_id), Phase 2 wait loop активна. **01.05 update**: Lazy re-attach шим у modules/notebooklm.py (14 рядків) дозволяє main.py не знати про brief — backward-compatible з старим кодом.

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

Переиспользується NBLM ключ. Card mode & Quiz mode через inline кнопки. Deep-link `flashcards_{topic_id}` в pinned. Ed тести: 3 блоки, 3/3 PASS.

## Regen + NBLM retry

```yaml
last_touched: 2026-04-26
tags: [pipeline, regen, nblm]
status: active
```

`/regen` — масова дорегенерація failed формативів. Reset failed→pending, `run_pipeline` послідовно у фоні. NBLM retry: `RETRY_DELAYS = [0] + [3600] * 71` (~72 год). **26.04 update**: NBLM async polling архітектура верифікована. Dead-code `_generate_fmt_via_cli` потребує видалення перед merge.

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

`modules/pinned.py` на `render_pinned()`. Per-topic NB · TTS · Exam · Flashcards (deep-links). `curriculum/renderer.py`: deep-links для articles. Footer: `🗺 Карта островів` + timestamp. `_handle_deep_link`: fmtcheck_, pipeline_, exam_, map, tts_, flashcards_, **article_** (потребує реалізації dispatcher для articles — PRIORITY Фаза Б).

## Pipeline orchestrator

```yaml
last_touched: 2026-05-01
tags: [pipeline, generation]
status: active
```

`curriculum/pipeline.py::run_pipeline()` — послідовна генерація 7 форматів (без exam). Skip ready/generating. Refresh pinned між кроками. Auto-pipeline при add_topic. **26.04 update**: розширення для article-артефактів. **01.05 update**: article pipeline отримав deep-dive параметри. **Потребує**: article deep-link dispatcher у pinned.py.

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

`set_my_commands`: cur, jobs, notebooks, status, regen, flashcards, **article, article_del** (потребує додавання у list — LOW PRIORITY).

## Roadmap по маніфесту

```yaml
last_touched: 2026-05-01
tags: [roadmap]
status: active
```

Фаза 0-5 ✅ | Фаза 6.1 ✅ | **Фаза 6.2** 🚧 ACTIVE (articles) | **Фаза А (NBLM deep-dive)** ✅ 01.05 DONE | **Фаза Б (brief.py + backend-agnostic)** ✅ 01.05 IMPLEMENTED + test PASSED | **Bulk-регенерація 17 подкастів** 📋 NEXT | Фаза 6.3+ (SR / export / Depth Mode — відкладена після 1-2 тижнів використання articles). Паралельно: масштабування триярусної пам'яті на Meggy, Ed, Garcia, Abby-v2.

## Ключові архітектурні рішення

```yaml
last_touched: 2026-05-01
tags: [decisions]
status: active
```

**01.05 updates (Фаза Б)**: Brief-генерація через Haiku, backend-agnostic: backends/ дерево (nblm, tts, interactive — останні два заглушки), кожен backend отримує brief + контент через ContentBackend ABC. `prepare_and_generate()` API. БЕЗ schema migration. ContentBrief у Topic/Article. Lazy re-attach шім для backward-compat. **01.05 update (Фаза А)**: Deep-dive format через --format flag у notebooklm_module, звучить краще. Інтегровано в article pipeline. Topic.content_style = Literal[audio/visual], НЕ місце для інструкцій. **27.04 updates**: Lazy re-attach верифіковано через рестарт з active task (task 7af67aad). `post_init` скан `curriculum.json` для `status=generating + task_id` → `asyncio.create_task(generate_and_notify(...))` зі skip-Phase-1 логікою. **Stale task_id fallback**: timeout × 5 → `artifact list` → match by format → URL → JSON patch (потребує реалізації, не критична). **Article dispatcher**: потребує `article_` handler у `_handle_deep_link` (PRIORITY). Інші рішення як раніше: Аккордеон через editMessageText, Exam stateful session в JSON, Regen через create_task, Island map текстовий, Proactive 3 тригери, Flashcards переиспользує NBLM, Ed MessageEdited listener, Articles окремо від тем.

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