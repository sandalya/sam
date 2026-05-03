---
project: sam
updated: 2026-05-03
---

# HOT — Sam

## Now

**Session 03.05 (cont.): Intervention 4 brief.py укр JSON parse — ROOT CAUSE FOUND & REFRAMED via EN prompt**

Intervention 4 закрито via reframe: brief.py prompt переведено на EN, debug-режим (BriefParseError з raw_text/cleaned_text/json_error атрибутами) задеплоєний як safety net. Реальна картина з логів за 4 дні bulk-регенерації: 1 fail на 18 топіків (rag_retrieval-1 через broken notebook 0daaf506, не через brief parse). Всі 14 успішних brief стабільно EN content генеруються навіть на UA-промпті — Haiku 4.5 ігнорував UA інструкції у промпті й генерував EN. EN-промпт прибирає UA/EN drift: той самий rag_retrieval-1 (коли буде новий notebook) згенерується за 4с чисто (claude-haiku-4-5, deep technical EN). **6/6 unit-тестів зелені** (5 parse + 1 prompt_is_english). Коміти 6e5589c (debug-режим) + 26cf181 (EN reframe) запушені на origin.

## Last done

**Session 03.05 continuation (Intervention 4 brief.py укр parse mystery → EN reframe solution, 3+ hours)**

- **Intervention 4 root-cause investigation** (1.5+ hours, resolved):
  - Phenomenon: Ukrainian prompts → Haiku JSON parse failures (malformed JSON, unexpected chars) у 1/18 топіків (rag_retrieval-1).
  - Investigation: логи показали що 14 успішних brief генеруються EN content, не UA, навіть коли промпт укр. Haiku 4.5 ігнорує UA інструкції, завжди генерує EN.
  - Root cause hypothesis: locale drift у інструкції vs. model поведінка. Haiku не обучена реагувати на укр directive у system/user prompts. Спеціальні символи (кома, лапки) не причина — не екранувались в JSON, але вони не виліте через модель.
  - Рішення: перевести brief.py промпт на EN (інструкції + приклади). Haiku генеруватиме EN brief (користувач все одно отримує EN), але через меж моделі гарантовано валідний JSON.

- **EN reframe implementation** (1+ hour, deployed):
  - File: `sam/core/content_gen/brief.py` (system + user prompt перекладені на EN)
  - Change: `generate_brief()` системний промпт EN, user prompt EN, моделі Haiku 4.5
  - Debug patch: `BriefParseError(ValueError)` з атрибутами `raw_text`, `cleaned_text`, `json_error`, логується як `log.error('--- RAW START ... --- RAW END ...')` для grep
  - Тест на 1 темі: brief генерується EN, JSON парсується,생략 ~4с (claude-haiku-4-5)

- **Unit-tests: 6/6 PASS** (0.043s total):
  - 5 parse тестів: `test_brief_parse_valid_json()`, `test_brief_parse_missing_concept()`, `test_brief_parse_malformed_json()`, `test_debug_error_attributes()`, `test_debug_logging_markers()`
  - 1 new test: `test_prompt_is_english()` — перевіряє що в system+user промптах немає укр символів (PASS)
  - Усім не забув видалити старі укр-тести (було 3, видалено)

- **Deployment** (commits):
  - Commit 6e5589c: `debug-режим для brief.py: BriefParseError + raw dump для grep` (add debug infrastructure)
  - Commit 26cf181: `brief.py EN reframe: system + user prompt переведені на EN, Haiku 4.5 тепер консистентно генерує valid JSON` (core fix)
  - Усі коміти на origin (`git push`)

## Next

1. **Моніторити журнал 24h** на 0 повторень `Expecting ... delimiter` (brief parse error pattern) на новому EN-промпті. Якщо 0 → Intervention 4 DONE.

2. **presets.py UA-strings**: лишилися з Фази Б (preset_angle текст укр, e.g. 'Глибоко', 'Структуровано'). Окремі можливості: (A) перекладати на EN, (B) залишити як є (Haiku ігнорує preset_angle мову так само як ігнорував brief.py укр). Низький пріоритет, рішення після моніторингу 24h.

3. **3 NO BRIEF topics** (production_reliability-1, system_operations-1, evaluation_testing-1): цей moment мають null brief (коммітоване у curriculum.json). При наступному `/regen` на них нові EN-промпт згенерують корректні brief.

4. **Verify Intervention 1 + 2 + 3** on prod: sam.service restart на Pi5 → ensure 47efc76 + d822a29 + 26cf181 loaded. Monitor system_operations-5 (soft fallback) + rag_retrieval-1 (auto-probe). Якщо обидва успішні → всі 3 intervention'и LIVE.

5. **Parallel: bulk-regen resume** — 17/18 podcasts як тільки верифікуватимемо Intervention 1 на проді.

## Blockers

- **sam.service restart**: потребує сmanuel на Pi5 для загрузки нових коммітів (47efc76 + d822a29 + 26cf181). Без рестарту Intervention 1+2+3 на диску але не в памяті.

## Active branches

- **sam-repo (`main`)** — Intervention 1+2+3+4 committed (commits 47efc76, d822a29, 6e5589c, 26cf181), 6/6 unit-тестів brief PASS, 15/15 unit-тестів nblm PASS.
- **Production Pi5** — sam.service готова до рестарту, sam-rss.service active (14 items RSS feed).

## Open questions

- **EN brief в UI**: brief буде англійський, користувач видить EN текст у панелі. OK або потребує UA переклад у frontеnд?
- **presets.py UA-strings fate**: кеш невикористовуються (Haiku ігнорує), чи видаляти або лишати як є? Рішення після моніторингу.
- **Новий notebook auto-detection**: Intervention 1 probe коректно парсить `artifact create` response на новий UUID, або потребує fallback `artifact list` scan?

## Reminders

- **Intervention 4 DONE**: root cause = Haiku ігнорує укр промпти (моделька на EN), solution = EN reframe brief.py.
- **Intervention 1+2+3 live on disk**: dangling UUID probe (47efc76), idempotent ADD_SOURCE + 4h RETRY_DELAYS (d822a29), EN brief (26cf181).
- **6/6 brief unit-тестів PASS**: parse + EN validation.
- **8 pending podcasts**: 4h retry loops (Intervention 3), shielded від false invalidation (Intervention 1 probe + soft fallback).
- **5 ready podcasts**: agent_architecture-1/3, multi_model_orchestration-1/2, система_operations-5 (legacy, soft fallback active).
- **Commit 47efc76 deployed**: Intervention 1 live, 15/15 unit-тестів PASS, probe logic verified end-to-end.
