Проект: sam

**Стан**: Intervention 1 (dangling UUID probe + soft fallback) щойно deployed на prod — commit 47efc76, 15/15 unit-тестів PASS. Dangling UUID detection + soft fallback для rate-limit 429 тепер захищають bulk-regen від false invalidation. End-to-end верифікація: /regen rag_retrieval-1 auto-детектує 0daaf506 dangling, створює новий notebook; orphaned video tasks успішно re-attach без інвалідації; rate-limit soft fallback працює. Intervention 2+3 (idempotent ADD_SOURCE, 4h RETRY_DELAYS cap) раніше deployed (commit d822a29).

**Що робити далі**: (1) Рестартни sam.service на Pi5 щоб загрузити commit 47efc76, моніторинь 1-2 retry cycles для system_operations-5 (2d0285dd RATE_LIMITED 429) на предмет soft fallback success. (2) Паралельно: investigate Intervention 4 (brief.py укр JSON parse fail) — чому Ukrainian prompts іноді приводять до Haiku JSON parse failure. Low priority, fallback спрацьовує. (3) Після verify: bulk-regen резюміється для 8 pending + 2 recovering, target 17/18 podcasts (5 ready, 8 pending 4h loops, 2 auto-recovering).

**Блокери**: system_operations-5 soft fallback на проді — потребує рестарту. rag_retrieval-1 auto-create — перевірити лог що новий notebook успішно створився.

Давай вмісту HOT.md + WARM.md з моєю попередньою сесією, перевірю що не забув деталей.