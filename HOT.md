---
project: sam
updated: 2026-05-02
---

# HOT — Sam

## Now

**Morning session 02.05: Bug fix end-to-end confirmed, 5 podcasts ready, bulk-regen resuming for 8 pending topics**

Сесія від 01.05 вечір: bug root cause (premature 'mark generating' в nblm.py:268-273) локалізована, fix deployed, 3 stuck topics (tool_use_integration-1, production_reliability-2/3) reset до pending. 5 подкастів ready (agent_architecture-1/3, multi_model_orchestration-1/2, system_operations-5) — legacy з modules/notebooklm.py. 10 тем missing podcast_nblm. Bulk-regen паузована на bug verification.

**Сьогодні 02.05**: перевірено tool_use_integration-1 статус → ready підтверджено end-to-end. Fix working. CC переклав brief.py + presets.py на укр (не активовано, на диску). AntennaPod podcast app працює, feed-у 14 items. 8 тем pending: production_reliability-5 (retry до ~03.05 19:26), multi_model_orchestration-1/2, system_operations-2/3/4/5, rag_retrieval-1 (zombie reset).

## Last done

**Сесія 02.05 ранок (08:00 UTC) — End-to-end verification + context updates**

- Підтверджено tool_use_integration-1 → status=ready, podcast_nblm format коректно. Bug fix (видалення Step 3 з nblm.py) end-to-end working.
- CC переклав brief.py + presets.py на укр мову (файли на диску у /workspace/sam/core/content_gen/, не активовано в коді).
- Знайдено ROOT CAUSE застрягання черги: accumulated artifacts у NBLM + RETRY_DELAYS=72h (послідовно), 72h retry спричинює довгий backoff.
- rag_retrieval-1 zombie ready — reset до pending, готова до retry.
- Генеровано 5 нових подкастів цієї сесії: agent_architecture-2 (old deep-dive), production_reliability-2/3/4 (old), що зроблено при 01.05 bulk-regen запуску (legacy з modules/notebooklm.py, не перегенеровані у Фазі Б).
- Додано podcast_nblm ключ для 10 тем (інтегровано у curriculum.json formats).
- AntennaPod podcast app: feed-у 14 items, працює корректно, слухачам доступно.

## Next

1. **Активація укр-перекладу brief.py + presets.py**
   - CC переклав, файли готові на диску.
   - Потребує: замінити англ вмісту у `/workspace/sam/core/content_gen/brief.py` і `presets.py` на укр переклади.
   - Команда (после перевірки): `cp /workspace/sam/core/content_gen/{brief,presets}.py.bak /workspace/sam/core/content_gen/` (перед заміною), потім заміна вмісту.
   - Тест: `/regen --only podcast_nblm` на 1 темі, verify brief output в укр.

2. **Restart sam.service для активації укр-brief** (якщо merge в проді)
   - `systemctl restart sam.service` на Pi5.
   - Monitor: перевірити новий podcast (якщо генеруватиметься) має укр brief.

3. **Reset production_reliability-5 (застрягла в retry-loop)**
   - Status: generating, task_id존재, retry до ~03.05 19:26 (+72h від запуску 01.05 19:26).
   - Reset: `curriculum reset-format production_reliability-5 podcast_nblm` → pending.
   - Альтернатива: очікувати retry автоматично (але це занадто довго).

4. **/regen --only podcast_nblm для 8 pending тем**
   - 8 тем: production_reliability-5 (після reset), multi_model_orchestration-1/2, system_operations-2/3/4/5, rag_retrieval-1.
   - Перед `/regen`: **зачистити старі артефакти у проблемних notebook-ах** (production_reliability-5, rag_retrieval-1, multi_model_orchestration-1) або чекати P1 фіксу NBLM (як-то скорочення RETRY_DELAYS).
   - Command: `/regen --only podcast_nblm` → моніторинг першi 1-2 швидко, решта rate-limit retry-loop (71+ годин послідовно).
   - Альтернатива (швидше): чекати API recovery NBLM (очікується після 03.05 19:26 для production_reliability-5, або вручну скоротити RETRY_DELAYS на 24h).

## Blockers

- **NBLM rate-limit loop**: 8 подкастів мають rate-limit, RETRY_DELAYS=72h послідовно. API recovery очікується автоматично або потребує manual retry скорочення.
- **Укр-переклад brief.py + presets.py**: готовий на диску, потребує merge у основний код.

## Active branches

- **sam-репо (`main`)** — bug fix merged (4 рядка видалено з nblm.py), тести passing, stable.
- **Укр-переклад content_gen** — на диску, pending merge.

## Open questions

- **RETRY_DELAYS скорочення**: 72h → 24h? Потребує тестування на API behavior (чи API готова раніше, чи нема сенсу).
- **Старі артефакти cleanup**: потребує manual видалення чи автоматичного garbage collection у NBLM? (Low priority, розглянути для P1 фіксу).
- **Укр-переклад: усі інші модулі?** (Наразі тільки brief.py + presets.py; інші модулі англійські на проді).

## Reminders

- **Bug root cause**: premature 'mark generating' (Step 3) ДО retry loop. Step 5 вже обробляє failed коректно. Fix deployed & end-to-end confirmed.
- **3 reset topics**: tool_use_integration-1 (✅ ready), production_reliability-2/3 (✅ pending), production_reliability-5 (потребує reset), rag_retrieval-1 (✅ pending) → готові до retry.
- **5 ready podcasts**: legacy, не перегенеровані у Фазі Б.
- **8 pending podcasts**: production_reliability-5 (retry до 03.05 19:26), multi_model_orchestration-1/2, system_operations-2/3/4/5, rag_retrieval-1.
- **Stale task_id fallback**: окремий баг для video, потребує реалізації (не критична для Фази Б).
- **Brief cache**: перекористовується, дорого але не кожен рендер.
- **AntennaPod + RSS feed**: 14 items, активно працює, Pocket Casts готовий до додавання.
- **Паралельна робота**: під час rate-limit loop можна почати Фазу В (article dispatcher + BotCommand) — не залежить.