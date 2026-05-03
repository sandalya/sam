---
project: sam
updated: 2026-05-03
---

# HOT — Sam

## Now

**Session 03.05: NBLM diagnostic complete — Intervention 2+3 ready for CC, 2 failed topics isolated for recreation**

NBLM CLI диагностика завершена: 3 notebook UUID верифіковано (healthy 8aca66e9 OK, broken-A 0daaf506 dangling RPC null, broken-B 2d0285dd RATE_LIMITED 429). Виявлено 3 bugs: (1) ADD_SOURCE дублювання в backends/nblm.py line 261 — перед add перевіряти source list, (2) RETRY_DELAYS скорочення з 72h на 4h cap — Intervention 3, (3) JSON edit не перериває async task — bonus low-priority. **Session 2 CC готова**: Intervention 2 (idempotent ADD_SOURCE) + Intervention 3 (RETRY_DELAYS + structured null-RPC error + external stop detection) + unit-тести. Commit d822a29: 11 unit-тестів зелені (0.056s), /nblm 282 рядки, test_nblm_backend.py 281 рядок. **Failed topics action**: rag_retrieval-1 (UUID 0daaf506 broken) + system_operations-5 (UUID 2d0285dd RATE_LIMITED) потребують нових clean notebook'ів перед retry. Укрсенізація brief.py + presets.py merged, production-active. 16/18 podcasts: 5 ready, 8 pending rate-limit, 2 failed isolated.

## Last done

**Session 03.05 (NBLM diagnostic + unit-test implementation, 3+ hours)**

- **NBLM backend diagnostic** (2+ hours): CLI локалізована `/workspace/venv/bin/nblm`, backends/nblm.py прочитано (428→282 рядків після оптимізації), 3 notebook UUIDs верифіковані через `artifact status`:
  - healthy 8aca66e9 (agent_architecture-1): OK
  - broken-A 0daaf506 (rag_retrieval-1): null RPC response → dangling UUID
  - broken-B 2d0285dd (system_operations-5): RATE_LIMITED 429 (Google)

- **Bugs identified & root-cause analysis**:
  1. **ADD_SOURCE дублювання (Bug 2)**: healthy notebook 8aca66e9 має 2 ідентичні sources [18, 19]. Line 261 `add_source()` не перевіряє існуючі sources перед додаванням. Fix: скан `artifact info → sources[]` перед add, skip якщо існує.
  2. **RETRY_DELAYS скорочення (Intervention 3)**: RETRY_DELAYS = [0] + [3600]*71 = ~72 год послідовно. Кандидат на скоротити до 3-5h cap (Google rate-limit recovery SLA). Додати структурований error для null-RPC (сигнал про broken UUID).
  3. **Bonus: JSON edit не перериває task** — manual notebook JSON changes ігноруються in-flight async task без reload. Low priority.

- **Session 2 CC implementation** (1+ hour, completed):
  - **Intervention 2**: `add_source()` модифікація — перевірка `if source in notebook.sources` перед додаванням. Файл: `sam/core/content_gen/backends/nblm.py` line ~261.
  - **Intervention 3**: RETRY_DELAYS переведено на модульний level, скорочено до `[0, 3600, 7200, 14400]` (4h cap замість 72h), додано structured error: `nblm_{code}` для null-RPC response (сигнал dangling UUID), external stop detection у retry+wait loops.
  - **Unit-тесты**: 11 тестів зелені (0.056s), test_nblm_backend.py 281 рядок, перевірено idempotent ADD_SOURCE, RETRY_DELAYS cap, null-RPC error handling.
  - **Commit d822a29**: +82 рядки в backends/nblm.py, +281 рядок у test_nblm_backend.py, stable.

- **Failed topics isolation**:
  - **rag_retrieval-1** (UUID 0daaf506): null RPC response при `artifact status` → notebook UUID dangling/broken. Потребує видалення старого notebook + створення нового через NBLM UI/CLI, reset topic у curriculum.json до pending.
  - **system_operations-5** (UUID 2d0285dd): RATE_LIMITED 429 (Google). Новий clean notebook, reset до pending.
  - Після recreation: `/regen --only podcast_nblm` для обох тем.

- **Укрсенізація**: brief.py + presets.py merged, output in Ukrainian, production-deployed. Haiku JSON parse fail на укр (fallback спрацьовує, low priority дослідження).

- **Moніторinг bulk-regen**: 5 podcasts ready (agent_architecture-1/3, multi_model_orchestration-1/2, system_operations-5 legacy), 8 pending rate-limit (production_reliability-5/multi_model_orchestration/system_operations 2-5, rag_retrieval-1), 2 failed isolated. **Нові RETRY_DELAYS 4h cap** скоротять ожидание для 8 pending з 72h до 4h.

## Next

1. **Restart sam.service after chkp** — перевірити що сервіс перезагрузився без помилок, моніторинг 1-2 retry cycles для 8 pending подкастів з новими 4h RETRY_DELAYS.

2. **Create new clean notebooks для 2 failed topics** (ПАРАЛЕЛЬНО)
   - rag_retrieval-1: видалити старий 0daaf506, створити новий через NBLM UI (`Create notebook` → нова пуста) або CLI `nblm notebook create`, отримати UUID, оновити curriculum.json з новим UUID, set status=pending.
   - system_operations-5: те саме для UUID 2d0285dd.
   - Тест: `nblm artifact status <new_UUID>` → OK.

3. **Resume bulk-regen для 8 pending + 2 newly created** (після notebook recreation)
   - `/regen --only podcast_nblm` для rag_retrieval-1 + system_operations-5 + 8 pending з новими 4h RETRY_DELAYS.
   - Моніторинг: першi 1-2 theми швидко, решта 4h loop (замість 72h).

4. **Наступна CC сесія** (ПІСЛЯ рестарту + verify):
   - **Фаза В**: article dispatcher у `_handle_deep_link()` (перехоп `article_` deep-links), `set_my_commands` додавання (article, article_del).
   - **Brief.py дослідження**: чому укр промпт приводить до Haiku JSON parse fail? Спеціальні символи, token limit? (low priority, fallback спрацьовує).

## Blockers

- **sam.service restart**: потребує рестарту після deployment (chkp2 не auto-рестартує systemd сервіс). Manual: `systemctl restart sam.service` на Pi5.
- **2 failed topics**: потребують manual notebook recreation (rag_retrieval-1 + system_operations-5) перед `/regen`.

## Active branches

- **sam-репо (`main`)** — Intervention 2+3 merged (commit d822a29), укрсенізація complete, stable.
- **Production Pi5** — sam.service + sam-rss.service active (14 items RSS feed), ready для рестарту.

## Open questions

- **RETRY_DELAYS 4h cap**: чи достатньо для Google rate-limit recovery? Або потребує ще коротше? Тест на реальній ситуації після рестарту.
- **Broken UUID detection**: чи є спосіб перехопити null RPC раніше у flow, або це NBLM API констрейнт?
- **Haiku укр JSON parse**: спеціальні символи (кома, лапки, українські букви) або token limit?

## Reminders

- **Commit d822a29 deployed**: Intervention 2+3 код live, unit-тесты pass, 11/11 зелені.
- **4h RETRY_DELAYS cap активна**: замість 72h послідовно, 8 pending подкастів очекуватимуть ~4h замість ~24-72h.
- **5 ready podcasts**: agent_architecture-1/3 (deep-dive ~9.5 min), multi_model_orchestration-1/2, system_operations-5 (legacy).
- **8 pending podcasts**: production_reliability-5, multi_model_orchestration-1/2, system_operations-2/3/4/5, rag_retrieval-1 — усі з новими 4h retry cycles.
- **2 failed podcasts (action required)**: rag_retrieval-1 (UUID 0daaf506) + system_operations-5 (UUID 2d0285dd) потребують нових clean notebooks.
- **Stale task_id 19826355 + 7af67aad**: залишаються поза скоупом (окремий баг, low priority).