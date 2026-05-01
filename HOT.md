---
project: sam
updated: 2026-05-01
---

# HOT — Sam

## Now

**Фаза А NBLM рефакторингу — deep-dive формат через notebooklm_module/pipeline/article**

Проброс `--format deep-dive --length default` у pipeline. Верифіковано на `agent_architecture-1` — deep-dive звучить помітно краще за дефолт. Підготовка до Фази Б: новий `core/content_gen/` пакет з `brief.py` (Haiku pre-analysis).

## Last done

**Сесія 01.05 — Фаза А NBLM рефакторингу**

- Додано `--format deep-dive --length default` у `notebooklm_module.py` для проходження через pipeline
- Тестування на `agent_architecture-1` теми — результат помітно кращий за дефолт
- Arquitectura Topic.content_style визначена як `Literal["audio", "visual"]` (інструкції НЕ йдуть сюди)
- Backend-agnostic план підтвердив: інструкції через Фазу Б (brief.py), backends/ дерево для TTS/quiz/flashcards

## Next

1. **Фаза Б (Priority)** — Створити `core/content_gen/` пакет:
   - `brief.py` — Haiku pre-analysis за `--format deep-dive --length default`
   - Adapter API для інструкцій (замість Topic.content_style)
   - Тестування на curriculum item
2. **Перевести pipeline на новий API** — migrate article + topic formats до brief-driven instructability
3. **Smoke-test на 2-3 темах** — переконатися что глибина і якість stable

## Blockers

Немає.

## Active branches

- **sam-репо (`main`)** — f29c0a8 запушено (RSS pipeline + deep-dive prep)

## Open questions

- Скільки Haiku instruction-варіантів мати у brief.py? (мінімум ~3: audio, visual, quiz) чи динамічна генерація?
- Content_style enum Literal або config-driven?

## Reminders

- **Deep-dive + default length** працює через notebooklm_module, не розповсюджується на article-pipeline поки що.
- **Topic.content_style** — это просто тег, інструкції при генерації йдуть через brief, не через модель даних.
- **RSS pipeline stable** — Pocket Casts ready, orphan sync на запит через `/dbg_nblm_sync`.
- **Lazy re-attach верифікована** — articles/topics при рестарті re-attach задачі автоматично.
- **Stale task_id recovery** — fallback нотована, не критична для поточної сесії (Фаза А не генерує нові задачі).