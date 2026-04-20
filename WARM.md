---
project: sam
updated: 2026-04-19
---

# WARM — Sam

## Curriculum v2 — єдине джерело правди

```yaml
last_touched: 2026-04-19
tags: [architecture, curriculum, data-model]
status: active
```

`shared/curriculum/` — пакет з `models.py` (Island/Topic/TopicFormat/CurriculumState), `storage.py` (load/save), `mutations.py` (add_topic/add_island/set_topic_state/mark_format_consumed). Весь стан курікулома живе у `data/curriculum.json` (schema_version=1). 18 тем, 8 островів, 16 audio + 2 visual. Topic IDs у форматі `{island-slug}-{n}`, `legacy_id` збережено для маппінгу на `notebooklm_notebooks.json`. Формати: `slides / podcast_nblm / podcast_tts / video / infographic / flashcards / exam`.

## Activity tracking окремо від curriculum

```yaml
last_touched: 2026-04-19
tags: [architecture, state]
status: active
```

`data/learning_state.json` тримає тільки `last_activity` + `streak_days`. `modules/state_manager.py::touch_activity()` викликається при user-активності. Artifact-consumed tracking переміщений у `Topic.formats[key].consumed` — `learning_state.json.topics` (legacy) більше не використовується.

## Sam engine-free

```yaml
last_touched: 2026-04-19
tags: [refactor, architecture]
status: active
```

Sam більше не імпортує `shared/curriculum_engine.py` — файл видалений (`.bak-phase29` у shared/). `modules/curriculum.py` скорочений до двох команд: `cmd_cur_add` (LLM визначає острів + метадані) і `cmd_done`. Ніяких `SamCurriculum`, `_instance_cache`, shim-делегацій. `main.py` отримує `DATA_DIR` напряму з `modules/base.py`.

## Proactive engine — базовий

```yaml
last_touched: 2026-04-19
tags: [proactive, ux]
status: active
```

`modules/proactive.py::generate_proactive_message()` викликається з `job_daily_digest`. Реагує на три тригери: `days_inactive ≥ 3`, є ready-артефакти не переглянуті, всі артефакти consumed → пропозиція наступної теми. Контракт — dict через `state_manager.get_current_progress()`. Тригери з маніфесту §3.5 ("нова тема", "після тесту") — **не реалізовані**, це Фаза 4.

## Pinned панель — read-only

```yaml
last_touched: 2026-04-19
tags: [ui, pinned, incomplete]
status: active
```

`modules/pinned.py` (120 рядків) + `shared/curriculum/renderer.py` (175 рядків). Рендерить HTML-текст з групуванням по островах, показує тільки active-теми, порожні острови → секція "Прогалини". Клікабельні `📓 NB` (NotebookLM URL) і `🔊 TTS` (deep-link). **Стара `render()` — read-only** (досі використовується `modules/pinned.py`). **Нова `render_pinned()` + `build_keyboard()`** додані 20.04 і готові до використання, але `modules/pinned.py` на них ще не переключено — зробимо у пункті (2) Phase 2 разом з callback-handlers.

## Pipeline — single-format only

```yaml
last_touched: 2026-04-19
tags: [pipeline, generation, incomplete]
status: active
```

`shared/notebooklm_module.py::generate_and_notify()` + `_generate_fmt_via_cli()` — генерують по одному NBLM-формату. `shared/podcast_module.py` → `SamPodcast` — TTS. **Немає orchestrator** що запускає всі 7 форматів за Audio/Visual-first порядком (маніфест §5.1). Після `cmd_cur_add` тема створюється з `formats={}`, нічого автоматично не генерується.

## Roadmap по маніфесту

```yaml
last_touched: 2026-04-19
tags: [roadmap]
status: active
```

Фаза 0 (маніфест) ✅ | Фаза 1 (модель даних, bootstrap) ✅ | **Фаза 2 (пайплайн + interactive pinned) 🟡 — поточна** | Фаза 3 (діалоговий тест) ⬜ | Фаза 4 (проактивні тригери 3.5) ⬜ | Фаза 5 (велика карта островів) ⬜ | Фаза 6 (Depth Mode, відкладена) ⬜.

## Phase 2 декомпозиція

```yaml
last_touched: 2026-04-19
tags: [phase-2, plan]
status: active
```

(1) ✅ **Renderer v2 — done** (коміт `d204a47` у workspace-репо + `1ac7b01` у sam-репо, 20.04). `render_pinned()` + `_render_topic_v2()` + лічильники `N/7 ✓●○` + `build_keyboard()` заглушка. (2) Callback handlers — `cur_toggle_{id}`, `cur_pipeline_{id}`, `cur_new`, `cur_map`, `fmt_check_{id}_{fmt}`, persistent `pinned_expanded.json` ~2 год. (3) Pipeline orchestrator — новий `shared/curriculum/pipeline.py::run_pipeline()` за content_style порядком, оновлення status, рефреш pinned ~2-3 год. (4) Smoke + integration ~1 год. Залишилось ~4-7 год. Перед пунктом (2) — окрема сесія: catch-up workspace-репо + перенос `shared/curriculum` + `notebooklm_module` + `podcast_module` у `sam/` (див. HOT).

## Ключові архітектурні рішення

```yaml
last_touched: 2026-04-19
tags: [decisions]
status: active
```

Акордеон у Telegram → варіант A (expand in-place через editMessageText), бо маніфест §8.4 забороняє спам у чаті. Автопайплайн при `cmd_cur_add` — НЕ в Фазі 2: Саша явно клікає `[▶ Продовжити]`. Проактивне "хочеш пайплайн?" — Фаза 4. `artifacts_remaining` у proactive = тільки `status=="ready" & not consumed` (не тягнути на pending).

## Відкриті питання

```yaml
last_touched: 2026-04-19
tags: [open-questions]
```

Renderer v2 — розширити існуючий чи переписати? (рекомендація: розширити, додати окрему `build_keyboard()`). Persistent state акордеону — окремий файл `pinned_expanded.json` чи поле у `pinned_state.json`? Після Фази 2 — чи потрібен `/pipeline` як окрема команда, або достатньо кнопки в pinned?

## Garcia — поза скоупом

```yaml
last_touched: 2026-04-19
tags: [garcia, deprecated]
status: paused
```

Garcia вважається deprecated. `shared/curriculum_engine.py` і `hub_renderer.py` існували заради Garcia — видалені, бо Sam engine-free, а Garcia не пріоритет. `notebooklm_module.py` і `podcast_module.py` лишаються — Sam-only, без Garcia-залежностей.

## Принципи з маніфесту (живі)

```yaml
last_touched: 2026-04-19
tags: [principles]
status: active
```

MVP → feedback → ітерація (не будуємо всі фази наперед). Суб'єктивне відчуття засвоєння важливіше за метрики — Саша сам каже "mastered". Ментор, не надсистема — Sem пропонує, Саша вирішує. Структура островів еволюціонує з використання. Анти-патерни: немає авто-статусів за часом, немає блокуючих prerequisites, немає спаму у чаті, немає Depth Mode на старті.