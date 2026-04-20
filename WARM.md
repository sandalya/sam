---
project: sam
updated: 2026-04-20
---

# WARM — Sam

## Curriculum v2 — єдине джерело правди

```yaml
last_touched: 2026-04-20
tags: [architecture, curriculum, data-model]
status: active
```

`sam/curriculum/` — пакет з `models.py` (Island/Topic/TopicFormat/CurriculumState), `storage.py` (load/save), `mutations.py` (add_topic/add_island/set_topic_state/mark_format_consumed/set_format_status/set_format_url), `islands.py` (LLM-кластеризація), `migration.py` (legacy→v2), `renderer.py` (pinned rendering). Раніше жив у `shared/curriculum/` — перенесено 20.04 у власність Sam (домейн-код, не shared-інфра). Стан у `data/curriculum.json` (schema_version=1). 18 тем, 8 островів, 16 audio + 2 visual. Topic IDs `{island-slug}-{n}`, `legacy_id` для маппінгу на `notebooklm_notebooks.json`. Формати: `slides / podcast_nblm / podcast_tts / video / infographic / flashcards / exam`.

## Activity tracking окремо від curriculum

```yaml
last_touched: 2026-04-19
tags: [architecture, state]
status: active
```

`data/learning_state.json` тримає тільки `last_activity` + `streak_days`. `modules/state_manager.py::touch_activity()` викликається при user-активності. Artifact-consumed tracking у `Topic.formats[key].consumed` — `learning_state.json.topics` (legacy) не використовується.

## Sam engine-free + layout власний

```yaml
last_touched: 2026-04-20
tags: [refactor, architecture]
status: active
```

Sam не імпортує жодного `shared.curriculum_engine`/`shared.curriculum`/`shared.notebooklm_module`/`shared.podcast_module` — всі перенесені у sam/. Залишились справжні shared-модулі що **не** chяпаємо: `agent_base`, `logger`, `token_tracker`, `token_logger`, `errors`, `memory_store`, `conversation_store`, `catchup_module`, `digest_module`. `modules/curriculum.py` скорочений до двох команд: `cmd_cur_add` і `cmd_done`. `main.py` отримує `DATA_DIR` напряму з `modules/base.py`.

## Sam layout (post-Phase-3)

```yaml
last_touched: 2026-04-20
tags: [layout, imports]
status: active
```

Sam запускається з `WorkingDirectory=/workspace/sam` + `sys.path.insert(0, '/workspace')`. Тому:
- **Top-level у sam:** `curriculum`, `core`, `modules`, `data` — імпорти без префіксу (`from curriculum import load`).
- **Через workspace:** `shared.agent_base`, `shared.token_tracker` — для спільних утиліт.
- **ENV:** systemd `EnvironmentFile=/workspace/sam/.env` — прокидає `ANTHROPIC_API_KEY`, `TELEGRAM_TOKEN`, `OWNER_CHAT_ID`.

## Proactive engine — базовий

```yaml
last_touched: 2026-04-19
tags: [proactive, ux]
status: active
```

`modules/proactive.py::generate_proactive_message()` викликається з `job_daily_digest`. Три тригери: `days_inactive ≥ 3`, ready-артефакти не переглянуті, всі артефакти consumed → пропозиція наступної теми. Контракт — dict через `state_manager.get_current_progress()`. Тригери з маніфесту §3.5 ("нова тема", "після тесту") — не реалізовані, Фаза 4.

## Pinned панель — interactive deep-links (пункт 2 done)

```yaml
last_touched: 2026-04-20
tags: [ui, pinned]
status: done
```

`modules/pinned.py` переключено на `render_pinned()`. Expanded state у `data/pinned_expanded.json` (`load_expanded`, `save_expanded`, `toggle_topic_expanded`, `toggle_mastered_expanded`). `render_pinned(state, expanded_topic_ids, expanded_mastered)` рендерить per-topic deep-links: `expand_{id}` / `collapse_{id}`, `fmtcheck_{id}_{fmt}`, `pipeline_{id}`, `expand_mastered` / `collapse_mastered`, `map`. Footer: `/cur_add` підказка + `[🗺 Карта]`. `_render_topic_expanded()` — per-format чеклист з deep-links. `build_keyboard()` — deprecated (inline-кнопки прибрані на користь deep-links у тексті). `main.py::_handle_deep_link()` — dispatcher: парсить payload з `/start`, виконує дію, refresh pinned, silent delete.

## Pipeline orchestrator (Phase 2.3 done)

```yaml
last_touched: 2026-04-20
tags: [pipeline, generation]
status: done
```

`curriculum/pipeline.py::run_pipeline()` — orchestrator. Послідовна генерація всіх 6 форматів (без exam) за content_style порядком (audio-first/visual-first). Skip ready/generating/skipped. Refresh pinned між кроками. NBLM формати через `notebooklm_module.generate_and_notify()`, TTS через `podcast_module.generate_tts_for_pipeline()` (standalone, без Update/AgentBase). `main.py` deep-link `pipeline_{id}` → `asyncio.create_task(run_pipeline(...))`. Автозапуск при add_topic — ще не реалізовано.

## Roadmap по маніфесту

```yaml
last_touched: 2026-04-19
tags: [roadmap]
status: active
```

Фаза 0 (маніфест) ✅ | Фаза 1 (модель даних, bootstrap) ✅ | **Фаза 2 (пайплайн + interactive pinned) ✅ — пункт (1) ✅, пункт (2) наступний** | Фаза 3 (діалоговий тест) ⬜ | Фаза 4 (проактивні тригери 3.5) ⬜ | Фаза 5 (велика карта островів) ⬜ | Фаза 6 (Depth Mode, відкладена) ⬜.

## Phase 2 декомпозиція

```yaml
last_touched: 2026-04-20
tags: [phase-2, plan]
status: active
```

(1) ✅ **Renderer v2** (коміт `d204a47` у workspace, `1ac7b01` у sam, 20.04). (2) ✅ **Callback handlers + deep-links (done 20.04).** `cur_toggle_{id}`, `cur_pipeline_{id}`, `cur_new`, `cur_map`, `fmt_check_{id}_{fmt}` + persistent `pinned_expanded.json`. (3) ✅ Pipeline orchestrator — done 20.04. (4) ✅ Auto-pipeline + /status + smoke — done 20.04. Phase 2 завершено.

## Tool add_topic в agentic loop

```yaml
last_touched: 2026-04-20
tags: [tools, agentic]
status: active
```

`core/tools.py`: schema `add_topic` (6-й tool у SAM_TOOLS), handler `_h_add_topic`. Sem додає теми через розмову ("додай тему X"). Handler викликає `_enrich_topic_via_llm` з `modules/curriculum.py` (LLM визначає острів, why/read/do/content_style), потім `curriculum.mutations.add_topic()` + save. Live-tested через `/cur_add`. Auto-pipeline запускається після add_topic (і cmd_cur_add, і tool в agentic loop).

## Ключові архітектурні рішення

```yaml
last_touched: 2026-04-19
tags: [decisions]
status: active
```

Акордеон у Telegram → варіант A (expand in-place через editMessageText) — маніфест §8.4 забороняє спам у чаті. Автопайплайн при `cmd_cur_add` — НЕ в Фазі 2: Саша явно клікає `[▶ Продовжити]`. Проактивне "хочеш пайплайн?" — Фаза 4. `artifacts_remaining` у proactive = тільки `status=="ready" & not consumed`.

## Workspace-репо архітектура (post-catchup)

```yaml
last_touched: 2026-04-20
tags: [infrastructure, git]
status: active
```

Workspace-репо (`/workspace/`) — метарепо над 7 ботами. Що tracked:
- `shared/` — справжні shared-модулі (agent_base, logger, token_tracker, ...).
- `BACKLOG.md` — cross-project беклог.
- `abby-v2`, `ed`, `insilver-v3`, `insilver-v2`, `kit`, `household_agent`, `abby`, `sam-v2` — gitlinks (submodule-like pointers без .gitmodules).
- Всі `*.sh`, `*.md` в корені workspace.

Що **НЕ** tracked (ignored):
- `sam/` — standalone repo, власний .git.
- `garcia/` — standalone repo, deprecated.
- `venv/`, `health_monitor.log` — runtime.

Workspace-репо і sam-репо обидва пушаться у `github.com/sandalya/sam.git` (master / main) — historical artifact, працює.

## Відкриті питання

```yaml
last_touched: 2026-04-19
tags: [open-questions]
```

Persistent state акордеону — окремий файл `pinned_expanded.json` чи поле у `pinned_state.json`? Після Фази 2 — чи потрібен `/pipeline` як окрема команда, чи достатньо кнопки в pinned?

## Garcia — поза скоупом

```yaml
last_touched: 2026-04-20
tags: [garcia, deprecated]
status: paused
```

Garcia deprecated. `shared/curriculum_engine.py` видалений ще 19.04. `shared/{notebooklm,podcast}_module.py` перенесені у sam/ — Garcia мала імпорти `from shared.notebooklm_module` і `from shared.podcast_module`, які тепер **зламані**. Це ок: `garcia/modules/{curriculum,notebooklm,podcast}.py` — мертвий код, не підключений у `garcia/main.py`. Якщо Garcia воскресне — окрема сесія.

## Принципи з маніфесту (живі)

```yaml
last_touched: 2026-04-19
tags: [principles]
status: active
```

MVP → feedback → ітерація (не будуємо всі фази наперед). Суб'єктивне відчуття засвоєння > метрики — Саша сам каже "mastered". Ментор, не надсистема — Sem пропонує, Саша вирішує. Структура островів еволюціонує з використання. Анти-патерни: немає авто-статусів за часом, немає блокуючих prerequisites, немає спаму у чаті, немає Depth Mode на старті.
