---
project: sam
updated: 2026-04-23
---

# WARM — Sam

## Curriculum v2 — єдине джерело правди

```yaml
last_touched: 2026-04-20
tags: [architecture, curriculum, data-model]
status: active
```

`sam/curriculum/` — пакет з `models.py` (Island/Topic/TopicFormat/CurriculumState), `storage.py` (load/save), `mutations.py` (add_topic/add_island/set_topic_state/mark_format_consumed/set_format_status/set_format_url), `islands.py` (LLM-кластеризація), `migration.py` (legacy→v2), `renderer.py` (pinned rendering). Раніше жив у `shared/curriculum/` — перенесено 20.04 у власність Sam (домейн-код, не shared-інфра). Стан у `data/curriculum.json` (schema_version=1). 17 тем, 8 островів, 16 audio + 2 visual. Topic IDs `{island-slug}-{n}`, `legacy_id` для маппінгу на `notebooklm_notebooks.json`. Формати: `slides / podcast_nblm / podcast_tts / video / infographic / flashcards / exam`.

## Activity tracking окремо від curriculum

```yaml
last_touched: 2026-04-19
tags: [architecture, state]
status: active
```

`data/learning_state.json` тримає тільки `last_activity` + `streak_days`. `modules/state_manager.py::touch_activity()` викликається при user-активності. Artifact-consumed tracking у `Topic.formats[key].consumed` — `learning_state.json.topics` (legacy) не використовується. Міграція consumed не потрібна — legacy даних немає.

## Sam engine-free + layout власний

```yaml
last_touched: 2026-04-20
tags: [refactor, architecture]
status: active
```

Sam не імпортує жодного `shared.curriculum_engine`/`shared.curriculum`/`shared.notebooklm_module`/`shared.podcast_module` — всі перенесені у sam/. Залишились справжні shared-модулі що **не** чіпаємо: `agent_base`, `logger`, `token_tracker`, `token_logger`, `errors`, `memory_store`, `conversation_store`, `catchup_module`, `digest_module`. `modules/curriculum.py` — три команди: `cmd_cur_add`, `cmd_done`, `cmd_regen`. `main.py` отримує `DATA_DIR` напряму з `modules/base.py`.

## Sam layout (post-Phase-5)

```yaml
last_touched: 2026-04-20
tags: [layout, imports]
status: active
```

Sam запускається з `WorkingDirectory=/workspace/sam` + `sys.path.insert(0, '/workspace')`. Тому:
- **Top-level у sam:** `curriculum`, `core`, `modules`, `data`, `docs` — імпорти без префіксу (`from curriculum import load`).
- **Через workspace:** `shared.agent_base`, `shared.token_tracker` — для спільних утиліт.
- **ENV:** systemd `EnvironmentFile=/workspace/sam/.env` — прокидає `ANTHROPIC_API_KEY`, `TELEGRAM_TOKEN`, `OWNER_CHAT_ID`.

## Phase 3 — EXAM (done)

```yaml
last_touched: 2026-04-20
tags: [exam, phase-3]
status: done
```

`modules/exam.py` — stateful діалоговий тест. Session у `data/exam_session.json`. 5 питань, LLM генерує (`_generate_questions`) і оцінює (`_evaluate_answer`). `PASS_THRESHOLD=3` правильних із 5. Deep-link `exam_{topic_id}` з pinned (renderer `_exam_label` — клікабельний). Exam intercept в `handle_text` — якщо `is_exam_active()`, всі повідомлення → `handle_exam_answer()`. Inline кнопки: ✅ Mastered (`exam_mastered_{id}` → `set_topic_state(mastered)`), 🔄 Retry (`exam_retry_{id}`), ➕ Підтема (`exam_subtopic_{id}` → `_generate_subtopic_title` LLM). `/exam_cancel` — скасовує. `CallbackQueryHandler(handle_exam_callback, pattern=r"^exam_")`.

## Phase 4 — Proactive triggers (done)

```yaml
last_touched: 2026-04-20
tags: [proactive, phase-4]
status: done
```

`modules/proactive.py` переписано на curriculum v2. Три тригери: (1) є ready не-consumed формати → "подивись", (2) все consumed → "готовий до екзамену?", (3) failed формати → "спробуй /regen". Exam subtopic suggestion — при завершенні екзамену з помилками, кнопка "➕ Додати підтему по прогалині" + `_generate_subtopic_title()` (LLM). Маніфест §3.5 тригер "нова тема → пайплайн" — done через auto-pipeline в Phase 2.

## Phase 5 — Island map (done)

```yaml
last_touched: 2026-04-20
tags: [map, phase-5]
status: done
```

`modules/island_map.py::render_island_map()` — текстова карта островів. Per-island progress bar (`▓░`), per-topic consumed/ready count, порожні острови. Gap detection: порівняння з `REFERENCE_ISLANDS` (12 AI-ландшафт категорій), фільтрація по existing island words + topic words. Deep-link `map` в `_handle_deep_link`. Pinned footer: `renderer.py` додає `🗺 Карта островів` deep-link перед timestamp.

## Regen + NBLM retry

```yaml
last_touched: 2026-04-20
tags: [pipeline, regen]
status: active
```

`/regen` (`cmd_regen` в `modules/curriculum.py`) — масова дорегенерація. Знаходить всі теми з MISSING або failed форматами, reset failed→pending, запускає `run_pipeline` послідовно для кожної теми у фоні (`asyncio.create_task(_run_regen(...))`). NBLM retry: `RETRY_DELAYS = [0] + [3600] * 71` — кожну годину, до 72 годин. Раніше було 3 спроби за 45 хв.

## Pinned панель — interactive deep-links

```yaml
last_touched: 2026-04-20
tags: [ui, pinned]
status: done
```

`modules/pinned.py` переключено на `render_pinned()`. `curriculum/renderer.py`: per-topic NB · TTS · Exam (deep-links). Exam label клікабельний (`exam_{id}`). Footer: `🗺 Карта островів` deep-link + timestamp. `_handle_deep_link` dispatcher: `fmtcheck_`, `pipeline_`, `exam_`, `map`, `tts_`.

## Pipeline orchestrator

```yaml
last_touched: 2026-04-20
tags: [pipeline, generation]
status: done
```

`curriculum/pipeline.py::run_pipeline()` — orchestrator. Послідовна генерація всіх 6 форматів (без exam) за content_style порядком. Skip ready/generating/skipped. Refresh pinned між кроками. Auto-pipeline при add_topic (і cmd_cur_add, і tool в agentic loop).

## Tool add_topic в agentic loop

```yaml
last_touched: 2026-04-20
tags: [tools, agentic]
status: active
```

`core/tools.py`: 6 tools у SAM_TOOLS. `add_topic` handler `_h_add_topic` — LLM визначає острів, why/read/do/content_style. Auto-pipeline запускається після add_topic. Case study doc: `docs/AGENTIC_LOOP_CASESTUDY.md`.

## BotCommand list

```yaml
last_touched: 2026-04-20
tags: [ui, telegram]
status: done
```

`set_my_commands` в `post_init`: cur, jobs, notebooks, status, regen. Прибрані: start, digest, science, catchup, onboarding, profile, podcast, cur_add. Hidden utilities: pin, unpin, cost, done, exam_cancel, getfileid.

## Roadmap по маніфесту

```yaml
last_touched: 2026-04-23
tags: [roadmap]
status: active
```

Фаза 0 (маніфест) ✅ | Фаза 1 (модель даних, bootstrap) ✅ | Фаза 2 (пайплайн + interactive pinned) ✅ | Фаза 3 (діалоговий тест) ✅ | Фаза 4 (проактивні тригери) ✅ | Фаза 5 (карта островів) ✅ | Фаза 6 (Depth Mode, відкладена — після 1-2 тижнів використання) ⬜. Паралельно: рефакторинг kit-репо для yaml-registry chkp3 (готовий до merge, 2026-04-23).

## Ключові архітектурні рішення

```yaml
last_touched: 2026-04-20
tags: [decisions]
status: active
```

Акордеон у Telegram → expand in-place через editMessageText. Exam — stateful session в JSON файлі, intercept в handle_text перед роутером. Regen — background task через create_task, не блокує бот. Island map — текстовий (mermaid/d3 — Phase 6+). Proactive — 3 тригери з curriculum v2, не зі старого state_manager. `artifacts_remaining` у proactive = тільки `status=="ready" & not consumed`.

## Workspace-репо архітектура (post-catchup)

```yaml
last_touched: 2026-04-20
tags: [infrastructure, git]
status: active
```

Workspace-репо (`/workspace/`) — метарепо над 7 ботами. Sam — standalone repo, власний .git. Workspace-репо і sam-репо обидва пушаються у `github.com/sandalya/sam.git` (master / main). Workspace комітиться вручну, sam — через chkp2.

## Garcia — поза скоупом

```yaml
last_touched: 2026-04-20
tags: [garcia, deprecated]
status: paused
```

Garcia deprecated. Імпорти `from shared.notebooklm_module` і `from shared.podcast_module` зламані — це ок, мертвий код.

## Принципи з маніфесту (живі)

```yaml
last_touched: 2026-04-20
tags: [principles]
status: active
```

MVP → feedback → ітерація. Суб'єктивне відчуття засвоєння > метрики. Ментор, не надсистема. Структура островів еволюціонує. Анти-патерни: немає авто-статусів за часом, немає блокуючих prerequisites, немає спаму у чаті, немає Depth Mode на старті.

## Триярусна пам'ять — структура проекту

```yaml
last_touched: 2026-04-20
tags: [infrastructure, memory]
status: active
```

Проект використовує три файли для управління контекстом:
- **HOT.md** — переписується щосесії, поточний крок і результати (~60 рядків).
- **WARM.md** — архітектура, рішення, відкриті питання (~400 рядків, оновлюється інкрементально).
- **COLD.md** — append-only історія, архіви завершених фаз.

Структура прийнята 2026-04-19, `chkp3` тестування почалось 2026-04-20, миграція на yaml-registry завершена 2026-04-23. Скрипт `chkp2.sh` автоматизує git commit, claude-інстанції читають HOT+WARM на старті сесії (Правило нуль в MEMORY.md).

## chkp3 — yaml-registry для триярусної пам'яті

```yaml
last_touched: 2026-04-23
tags: [infrastructure, chkp3, tools]
status: active
```

`kit/projects.yaml` — реєстр усіх проектів (path, language, memory_model). `chkp3` мігрована на YAML замість хардкоду. Нова команда `--init` скаффолдить HOT/WARM/COLD для нового проекту. Готова до роботи з Meggy, Ed, Garcia, Abby-v2. Структура:
```yaml
projects:
  sam:
    path: /workspace/sam
    language: uk
    memory_model: triadic
  meggy:
    path: /workspace/meggy
    language: uk
    memory_model: triadic
```
chkp3 --init meggy — scaffold три файли с базовим template.
