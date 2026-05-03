Проект: sam
Стан: NBLM diagnostic complete (03.05) — 3 notebook UUIDs верифіковані (healthy OK, broken-A RPC null, broken-B RATE_LIMITED), 3 bugs ізольовані для Intervention 2+3. Укрсенізація brief.py + presets.py merged, production-active. 16/18 podcasts: 5 ready, 8 pending rate-limit, 2 failed потребують нових notebook'ів.

Що далі:
Сесія 2 CC (5-6h): 
- Intervention 2: idempotent ADD_SOURCE — перевірити source list перед додаванням у backends/nblm.py line 261.
- Intervention 3: rate_limit retry redesign — скоротити RETRY_DELAYS з 71*3600 (72h) на 3-5h, додати інформативний error для null-RPC кейсу.
- Підготувати CC-prompt у chornetka/ перед сесією.

Паралельно: нові clean notebook'и для rag_retrieval-1 (0daaf506) і system_operations-5 (2d0285dd), reset у curriculum.json, потім `/regen --only podcast_nblm` для обох.

Блокери: потребує CC для вмешательств 2+3, потім manual notebook creation.

Діліти HOT.md + WARM.md для контексту.