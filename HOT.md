---
project: sam
updated: 2026-05-03
---

# HOT — Sam

## Now

**Session 03.05: NBLM diagnostic complete — 2 failed topics isolated, root causes identified**

NBLM CLI діагностика завершена: знайдено nblm CLI у venv (`/workspace/venv/bin/`), прочитано backends/nblm.py 428 рядків, прямі CLI виклики верифіковані на 3 notebook'ах. **broken-A (0daaf506)** = dangling UUID, RPC null response. **broken-B (2d0285dd)** = справжній Google RATE_LIMITED на NB-specific. Беклог-теза silent rc=1 спростована — обидва дають structured JSON. **Bug 2 (ADD_SOURCE дублі)** підтверджений на healthy notebook 8aca66e9. **Bonus баг**: manual JSON edit не перериває in-flight asyncio task без рестарту. Укрсенізація brief.py + presets.py merged, production-active, brief output in Ukrainian. 16/18 podcasts: 5 ready, 8 pending rate-limit, 2 failed (rag_retrieval-1 + system_operations-5 потребують нових clean notebook'ів).

## Last done

**Session 03.05 (diagnostic deep-dive, 2+ hours)**

- **NBLM CLI локалізована**: `/workspace/venv/bin/nblm` найдена, прямі команди `nblm artifact status`, `nblm artifact list` верифіковані.
- **backends/nblm.py аналіз**: прочитано 428 рядків, виділено ключові секції:
  - Line 165: substring detect для format matching
  - Line 184-200: wait-loop з eksponential backoff
  - Line 261: add_source call (AUTO засмічує notebook)
  - RETRY_DELAYS = 71*3600 послідовно (кандидат на скорочення)
- **Notebook UUIDs верифіковані через CLI**:
  - healthy 8aca66e9 (agent_architecture-1): `artifact status` → OK
  - broken-A 0daaf506 (rag_retrieval-1): `artifact status` → null RPC response, UUID dangling
  - broken-B 2d0285dd (system_operations-5): `artifact status` → RATE_LIMITED (429), Google rate-limit
- **Bug 2 (ADD_SOURCE дублі) підтверджений**: healthy notebook має 2 ідентичних sources 18/19 (додані manual via CLI `artifact add-source`). Потребує дослідження: чи auto ADD_SOURCE перевіряє існуючі sources перед додаванням.
- **Bonus баг виявлено**: manual JSON edit файлу notebook (додано fake source) не перериває in-flight asyncio task (wait loop продовжується з старими параметрами) без рестарту. Симптом: змінили JSON, task_id = null, rate-limit loop ігнорує change. Потребує: або reload-on-change, або warning що task活 при JSON edit.
- **Укрсенізація merged**: brief.py + presets.py з українським контентом інтегровані, brief output вже в українській мові. Haiku JSON parse fail на укр промпті (fallback спрацьовує, low priority).
- **Моніторинг bulk-regen**: 5 podcasts ready (agent_architecture-1/3, multi_model_orchestration-1/2, system_operations-5 legacy), 8 pending rate-limit (production_reliability-5/multi_model_orchestration/system_operations), 2 failed (rag_retrieval-1 + system_operations-5 потребують action).

## Next

1. **Сесія 2 CC: Intervention 2+3** (5-6 годин на два intervene)
   - **Intervention 2: idempotent ADD_SOURCE** — перевірити source list перед додаванням, skip якщо вже є. Файл: backends/nblm.py line 261 `add_source()`. Тест на healthy 8aca66e9 — додати source 2x вручну, перевірити що не дублюється.
   - **Intervention 3: rate_limit retry redesign** — скоротити RETRY_DELAYS з 71*3600 (72h послідовно) до 3-5h cap. Файл: nblm.py RETRY_DELAYS. Додати інформативний error на null-RPC (сигнал про broken UUID, потребує нового notebook).
   - Подготовити CC-prompt у chornetka/ для обох вмешательств перед сесією 2.

2. **Нові clean notebook'и для обох failed тем** (ПАРАЛЕЛЬНО)
   - rag_retrieval-1: видалити старий 0daaf506, створити новий пустий notebook через NBLM UI чи CLI, reset topic до pending у curriculum.json.
   - system_operations-5: видалити старий 2d0285dd, створити новий, reset до pending.
   - Після notebook replace: `/regen --only podcast_nblm` для обох тем (нові notebook'и = чистий аркуш).

3. **Resume bulk-regen для 10 тем** (після fixes + notebook replace)
   - `/regen --only podcast_nblm` для 8 pending + 2 новостворених (або 10 тем залежно від що буде done).
   - Моніторинг: rate-limit loop продовжиться, але з чистого аркуша для rag_retrieval-1 & system_operations-5.

4. **Parallel: bonus bug fix** (можна залишити на later priority)
   - Manual JSON edit не перериває in-flight asyncio task. Потребує: reload-on-change у _wait_for_artifact() або warning. Низька пріоритет, не блокує bulk-regen.

5. **Haiku JSON parse fail on укр** (дослідити, low priority)
   - Чому укр промпт приводить до JSON parse fail? Special chars? Token limit? Fallback спрацьовує, деталі потім.

## Blockers

- **Intervention 2+3 потребує CC:** idempotent ADD_SOURCE + rate_limit redesign. Готуємо CC-prompt.
- **2 failed topics потребують нових notebook'ів**: rag_retrieval-1 (0daaf506 broken) + system_operations-5 (2d0285dd RATE_LIMITED) → manual creation + reset curriculum.json.
- **Bonus баг JSON edit**: in-flight task ignores changes, потребує reload logic. Не критично для bulk-regen.

## Active branches

- **sam-репо (`main`)** — укрсенізація merged (brief.py + presets.py), 16/18 podcasts у pipeline, stable.
- **Production Pi5** — sam.service + sam-rss.service active, 14 items RSS feed, rate-limit loop для 8 подкастів.

## Open questions

- **ADD_SOURCE дублювання**: чи `add_source()` має перевірку `if source in notebook.sources`? Потребує code review nblm.py.
- **RETRY_DELAYS мінімальна тривалість**: скорочення з 72h на 3-5h — які sont SLA для Google rate-limit recovery? Потребує тесту на реальної ситуації.
- **Broken UUID handling**: чи є спосіб перехопити null RPC response раніше у flow? Чи це NBLM API констрейнт?
- **JSON edit + async task**: як перезагрузити task параметри при manual edit? Потребує architecture review.

## Reminders

- **5 ready podcasts**: agent_architecture-1/3 (deep-dive, ~9.5 min), multi_model_orchestration-1/2, system_operations-5 (legacy).
- **8 pending podcasts**: production_reliability-5 (retry до ~03.05 19:26, можна reset), multi_model_orchestration-1/2, system_operations-2/3/4/5, rag_retrieval-1.
- **2 failed podcasts**: rag_retrieval-1 (UUID 0daaf506 broken, RPC null), system_operations-5 (UUID 2d0285dd RATE_LIMITED) → потребують нових notebook'ів.
- **Укр-переклад активний**: brief.py + presets.py тепер у production, output in Ukrainian.
- **Stale task_id для відстежування**: 19826355 (agent_architecture-2 video), 7af67aad (article_6a578102 video) — не торкатись, окремий баг, low priority.
- **AntennaPod + RSS feed**: 14 items, активно працює.
- **Наступна фаза (В)**: article dispatcher + BotCommand додавання — паузована під час rate-limit loop.