---
project: sam
updated: 2026-05-01
---

# HOT — Sam

## Now

**Фаза Б: ЗАВЕРШЕНА і MERGED, буде чекатися bulk-регенерація подкастів (24-72 год)**

Фаза Б core/content_gen/ пакету на 100% реалізована, тестована на agent_architecture-3, успішно merged до main о 19:57 01.05. Запущено bulk-регенерацію 13 подкастів через `/regen --only podcast_nblm` (всі теми крім agent_architecture-1 і agent_architecture-3 які вже мають свіжий deep-dive brief). Паралельно готуємось до Фази В (article deep-link dispatcher + BotCommand додавання).

## Last done

**Сесія 01.05 — Фаза Б COMPLETE + merge + bulk-regen запущена**

- Фаза Б core/content_gen/ пакету на 100% реалізована: brief.py (Haiku pre-analysis), presets.py (audio/visual/quiz шаблони), backends/{base,nblm,tts,interactive}.py, ContentBrief dataclass у Topic/Article, prepare_and_generate() API.
- Schema_version залишається 1, fallback через `data.get("brief")` для backward-compat.
- Merge до main: 340+ рядків коду, 0 breaking changes завдяки lazy re-attach шіму (14 рядків у modules/notebooklm.py).
- Тест на agent_architecture-3: Haiku-генерація ~4с, brief з 6 концептів, NBLM параметри (deep-dive, length, format_modifier) передаються коректно, звук явно кращий за дефолт.
- Видалено _generate_format_instructions з article.py — brief тепер один на entity, переиспользується всіма форматами.
- Запущено bulk-регенерацію: `/regen --only podcast_nblm` о 19:57 для 13 тем (tool_use_integration-1, agent_architecture-2/3 відповідно; production_reliability-2/3/4/5; multi_model_orchestration-1/2; system_operations-2/3/4/5). Монітор: першi 1-2 підуть швидко (< 1 хв), решта — rate-limit retry-loop (RETRY_DELAYS = 71 година послідовно). Brief кешується після першої генерації.

## Next

1. **Чекати bulk-регенерацію 13 подкастів (24-72 год, rate-limit limited)**
   - Статус: запущено о 19:57. Моніторити через pinned (lazy re-attach polling).
   - Верифікація: `python3 -c 'import json; d=json.load(open("data/curriculum.json")); print({s: sum(1 for t in d["topics"] if t.get("formats",{}).get("podcast_nblm",{}).get("status","missing")==s) for s in ["ready","pending","generating","failed"]})'`
   - По завершенню: smoke-test звучання на 3-4 темах вибірково, порівняння зі старим deep-dive (agent_architecture-1).

2. **Фаза В — Article deep-link dispatcher (PRIORITY після bulk-regen)**
   - Реалізація: `article_` handler у `_handle_deep_link()` у pinned.py.
   - Flow: article_ID_HASH → load Article → display name/url + format-статуси (inline кнопки для audit-дій).
   - BotCommand: додати `article`, `article_del` у set_my_commands().
   - Test: `/article https://example.com` → opt-in via 🚀 → мінімум podcast_nblm ready → `/article_<id>` → display.

3. **Smoke-test Фази Б перед наступною сесією (коли bulk-regen впаде)**
   - Sam стартує без помилок, core/content_gen/ modules завантажуються.
   - Brief cache у Topic.formats['podcast_nblm'].brief при першому доступі.
   - `/regen agent_architecture-1 --only podcast_nblm` → Haiku brief-генерація → NBLM з параметрами.
   - Порівняння звучання зі старою версією (8aca66e9-b637-478f-be90-ab19bb6d2a72).
   - Якщо ОК → коміт + push.

## Blockers

- **Rate-limit loop**: 13 подкастів, з яких 1-2 підуть швидко, решта чекатимуть 71+ год на API recovery. Паралельно: можна робити article dispatcher, не блокує Фазу В.
- **Stale task_id fallback** (низький пріоритет): NBLM API task_id протухає через ~24h. Fallback не реалізовано, можна відкласти до паралельної роботи.

## Active branches

- **sam-репо (`main`)** — Фаза Б merged, bulk-regen запущена. Status: stable, готова до production smoke-test після bulk-завершення.

## Open questions

- **Bulk-регенерація 13 подкастів**: тривалість по темам? Очікується 24-72 год через rate-limit. Першi два-три швидко, решта в retry-loop.
- **Article dispatcher**: рендер у pinned як окремий accordion-блок чи інлайн у список статей?
- **Brief cache persistence**: Topic.formats[key].brief лишається у curriculum.json ou синхронізуватися з artifact.json?

## Reminders

- **Фаза А + Б на production** — deep-dive + brief система працює, merge stable.
- **Schema НЕ мігрована**: schema_version=1, ContentBrief додано через fallback `data.get("brief")`.
- **Lazy re-attach шім** (14 рядків у modules/notebooklm.py) забезпечує backward-compat.
- **Brief генерується 1 раз** і кешується — дорого, але не кожен рендер.
- **BotCommand list** потребує додавання article/article_del — низький пріоритет.
- **Паралельна робота**: під час bulk-regen можна почати article dispatcher (не залежить).
