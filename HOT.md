---
project: sam
updated: 2026-05-01
---

# HOT — Sam

## Now

**Фаза А NBLM рефакторингу завершена. Підготовка до Фази Б: core/content_gen/ пакет з brief.py**

Фаза А успішно інтегрована: проброс `--format deep-dive --length default` у pipeline, тестована на `agent_architecture-1` — звучить помітно краще. Підготовка до Фази Б: архітектура Haiku brief-генерації замість Topic.content_style для інструкцій. Backend-agnostic дизайн: `core/content_gen/brief.py` + `core/backends/` дерево.

## Last done

**Сесія 01.05 — Фаза А NBLM рефакторингу (завершена)**

- Додано `--format deep-dive --length default` у `notebooklm_module.py`
- Тестування на `agent_architecture-1` успішне — глибина помітно вища
- Topic.content_style визначена як `Literal["audio", "visual"]` (інструкції НЕ йдуть сюди)
- Підтверджено: Фаза Б потребує brief.py для інструкцій через Haiku pre-analysis
- Регенерація агент-теми зайняла ~9.5 хв (очікувано, deep-dive медленніше за дефолт)

## Next

1. **Фаза Б — Core/content_gen пакет (Priority)**
   - Créate `core/content_gen/brief.py` — Haiku читає Topic/Article контекст → генерує instruction set (1-2 рядки)
   - Adapter API: brief + контент → backends-ам (не Topic.content_style)
   - Інстанціювати мінімум 3 instruction-варіанти: audio, visual, quiz
2. **Мігрувати article + topic pipeline** на brief-driven instructability
3. **Smoke-test на 2-3 темах** — переконатись що глибина + якість stable
4. **Решту: article dispatcher fix, article_del BotCommand додати**

## Blockers

Немає.

## Active branches

- **sam-репо (`main`)** — f29c0a8 запушено (NBLM deep-dive + Фаза А готова)

## Open questions

- Скільки Haiku instruction-варіантів у brief.py? (мінімум 3: audio, visual, quiz) чи динамічна генерація на основі format?
- Content_style enum `Literal` або config-driven (YAML/JSON пресети)?
- Brief cache: чи зберігаємо brief для переиспользування, чи генеруємо щоразу?

## Reminders

- **Deep-dive + default length** працює через notebooklm_module, поки в article-pipeline не мігрований.
- **Topic.content_style** — просто тег, інструкції при генерації через brief.py (Фаза Б).
- **RSS pipeline stable** — Pocket Casts ready, orphan sync на запит через `/dbg_nblm_sync`.
- **Lazy re-attach верифікована** — articles/topics при рестарті re-attach задачі автоматично.
- **Stale task_id recovery fallback** — при 5+ timeout поспіль → `artifact list` → match by format → URL patch (не реалізовано, нотовано).
- **Article deep-link dispatcher** — потребує реалізації у `_handle_deep_link` для pinned deep-links (article_X).
- **Article BotCommand** — article, article_del потребують додавання у BotCommand list (set_my_commands).