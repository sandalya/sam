---
project: sam
updated: 2026-05-01
---

# HOT — Sam

## Now

**Фаза Б: Проектування core/content_gen/ пакету (backend-agnostic design)**

Фаза А NBLM deep-dive завершена, успішно протестована і merged → main. Фаза Б: створено core/content_gen/ пакет із brief.py (Haiku-аналіз), presets.py (template-набори), backends/{base,nblm,tts,interactive}.py. Проведено перший тест на agent_architecture-3: Haiku генерує brief за 4с, brief містить 6 концептів, NBLM аргументи з deep-dive+length+format_modifier передаються правильно. Lazy re-attach 14-рядковий shim підтримує зворотну сумісність з main.py і modules/notebooklm.py без зміни schema_version.

## Last done

**Сесія 01.05 — Фаза Б core/content_gen/ пакету IMPLEMENTED + test на agent_architecture-3 PASSED**

- Створено `core/content_gen/brief.py`: BriefGenerator клас, Haiku pre-analysis → instruction set (audio/visual/quiz), кеш у Topic/Article.formats[key].brief.
- Створено `core/content_gen/presets.py`: instruction-темплети для 3 варіантів (audio/visual/quiz).
- Створено `core/backends/`: base.py (ContentBackend base), nblm.py (NBLM podcast), tts.py (TTS для audio), interactive.py (quiz/flashcards).
- Додано ContentBrief dataclass у Topic/Article, migrate curriculum.json schema_version=2 (z fallback на schema_version=1).
- Реалізована prepare_and_generate() API: читає Topic/Article → brief → dispatch до backend → генерація.
- Merge до main: diff з 340+ рядків код, 0 breaking changes (lazy re-attach через shim).
- Тест на agent_architecture-3: Haiku 4с, 6 концептів у brief, NBLM deep-dive+length+format_modifier передаються коректно, sound-quality очевидно краща ніж дефолт.
- Видалено _generate_format_instructions з article.py — brief тепер один на entity, переиспользується всіма форматами.

## Next

1. **Bulk-регенерація 17 подкастів (Фаза Б Phase 2)**
   - Перелік: всі крім agent_architecture-1 і agent_architecture-3 які вже мають свіжий deep-dive.
   - Запустити: `/regen --only podcast_nblm --skip-ready`.
   - Параметри: brief-генерація через Haiku, NBLM з deep-dive+length, ~15 хвилин на тему.
   - Моніторинг: lazy re-attach бере на себе async polling, pinned показує progress.
   - Verifikation: звуконулювання на 3-4 темах вибірково.

2. **Article deep-link dispatcher (PRIORITY для smoke-тесту статей)**
   - Реалізація: `article_` handler у `_handle_deep_link()` (pinned.py).
   - Flow: article_ID_HASH → load Article → display name/url + format-статуси (inline кнопки для audit-действ).
   - BotCommand list: додати article, article_del у set_my_commands().
   - Test: `/article https://example.com` → opt-in → мінімум для одного формату (podcast_nblm) → /article_<id> → display.

3. **Smoke-test Фази Б перед наступною сесією**
   - Sam стартує без помилок, core/content_gen/ modules載入.
   - brief cache у Topic.formats['podcast_nblm'].brief при першому доступі.
   - `/regen agent_architecture-1 --only podcast_nblm` → Haiku brief-генерація → NBLM з параметрами.
   - Порівняння зі старим notebook (8aca66e9-b637-478f-be90-ab19bb6d2a72) за звуком.
   - Якщо ОК → коміт + push.

## Blockers

- **stale task_id fallback не реалізовано**: video артефакт готовий у NBLM UI, але CLI `artifact wait` повертає `timeout`. Fallback: `artifact list` → match by format → URL patch. **Можна відкласти** — не блокує Фазу Б, паралельна робота.

## Active branches

- **sam-репо (`main`)** — Фаза Б merged, відсутня лише bulk-регенерація подкастів. Status: stable, готова до production smoke-test.

## Open questions

- **Bulk-регенерація 17 подкастів**: order паралельність? Послідовна (одна тема за раз, щоб не перевантажити NBLM API) чи batch-по-3?
- **Article deep-link dispatcher**: точна інтеграція у pinned.py — render окремо чи додати у accordion?
- **Brief cache persistence**: Topic.formats[key].brief лишається у curriculum.json, чи синхронізуватися з artifact.json?

## Reminders

- **Фаза А ready на production** — глобальний deep-dive працює, merge stable.
- **Schema migration**: schema_version 1→2, fallback для старих curriculum.json.
- **Backward compat**: shim в modules/notebooklm.py (14 рядків) дозволяє main.py не знати про brief — lazy attach.
- **Lazy re-attach верифіковано** — articles/topics при рестарті re-attach через post_init z task_id.
- **RSS feed стабільна** — orphan sync, hook non-fatal, Pocket Casts готовий.
- **Article pipeline** потребує dispatcher для `/article_<id>` deep-links.
- **BotCommand list**: article, article_del потребують додавання у set_my_commands().