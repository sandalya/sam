---
project: sam
updated: 2026-05-01
---

# HOT — Sam

## Now

**Дебаг post-session: bug root cause localized, fix deployed, 3 stuck topics reset**

Вiдpаховано проблему у nblm.py:268-273: `set_format_status('generating')` без task_id запускалась ДО rate-limit retry loop. Якщо всі retry повернули rate_limit, то `save()` з task_id ніколи не виконується → стан зависає на generating з task_id=None назавжди. Fix: видалено 4 рядки (step 3 mark + orphaned save). Step 5 вже обробляє failed коректно. 3 теми (завислі) reset до pending, 5 подкастів ready (legacy з modules/notebooklm.py), 10 missing. NBLM rate-limited до ночи. Відкриті: stale task_id для video (два артефакти, 19826355 + 7af67aad) — окремий баг. RETRY_DELAYS=72h кандидат на скорочення.

## Last done

**Сесія 01.05 вечір (14:00 UTC) — Bug fix + reset**

- Проаналізовано логи `tool_use_integration-1`: rate_limit loop з task_id=None, topic.formats['podcast_nblm'].status='generating' вічно.
- Знайдено корінь: nblm.py:268-273 set_format_status('generating') БЕЗ task_id запускається до retry loop; якщо loop повертає rate_limit, save() з task_id ніколи не викликається.
- Fix: видалено 4 рядки (Step 3 mark + orphaned save), step 5 (failed handling) вже покривав error case.
- Reset 3 stuck topics (tool_use_integration-1, production_reliability-2/3) → status=pending.
- 5 подкастів ready (agent_architecture-1/3, multi_model_orchestration-1/2, system_operations-5) — legacy з modules/notebooklm.py, не перегенеровувались.
- 10 тем missing podcast (решта 13 з bulk-regen, рухаються через rate-limit loop).
- NBLM rate-limited до ночи, API recovery очікується.

## Next

1. **Morning session: перевірити tool_use_integration-1 статус**
   - Якщо ready/failed: ✅ fix end-to-end confirmed, restart bulk на решті 12 (rate-limit loop очищений).
   - Якщо pending: retry все ще в loop (стара версія в пам'яті?), потребує перезавантаження модулю або restart daemon.
   - Command: `python3 -c 'import json; d=json.load(open("data/curriculum.json")); t=[x for x in d["topics"] if x["id"]=="tool_use_integration-1"]; print(t[0]["formats"]["podcast_nblm"] if t else "NOT_FOUND")'`

2. **Якщо fix confirmed (ready/failed)**:
   - Restart `/regen --only podcast_nblm` для 13 тем (або 12 + tool_use_integration-1 окремо якщо failed).
   - Моніторинг: першi 1-2 швидко, решта rate-limit retry-loop (71+ год sequentially).
   - Brief cache перекористовується (вже згенерований).

3. **Паралельно (не блокує)**:
   - Розглянути RETRY_DELAYS = 72h; залежно від API можна скоротити на 24h (потребує тестування).
   - Stale task_id fallback (19826355, 7af67aad video) — низький пріоритет, окремий баг.

## Blockers

- **Rate-limit loop**: 13 подкастів мають NBLM rate-limit, API recovery очікується. Фаза В (article dispatcher) не залежить.
- **Потенційна проблема з кешем**: якщо модуль не перезавантажився після fix, retry loop може продовжити старим кодом → перевірити morning session.

## Active branches

- **sam-репо (`main`)** — bug fix merged (4 рядка видалено з nblm.py), тести passing, готова до production.

## Open questions

- **tool_use_integration-1 morning статус**: ready/failed/pending?
- **Потрібен ли manual restart daemon чи достатньо reload модуля?** (залежить від як запущено generate_and_notify).
- **RETRY_DELAYS скорочення**: 72h → 24h? Потребує тестування на API behavior.

## Reminders

- **Фаза А + Б на production** — deep-dive + brief система працює, merge stable.
- **Bug root cause**: premature 'mark generating' (Step 3) ДО retry loop. Step 5 вже обробляє failed коректно.
- **3 reset topics**: tool_use_integration-1, production_reliability-2/3 → pending, готові до retry.
- **5 ready podcasts**: legacy, не перегенеровувались.
- **Stale task_id**: окремий баг, потребує fallback реалізації (не критична).
- **Brief cache**: перекористовується, дорого але не кожен рендер.
- **Паралельна робота**: під час rate-limit loop можна почати article dispatcher (Фаза В) — не залежить.
