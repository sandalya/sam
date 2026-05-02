Проект: sam

Стан: bug root cause виявлено в nblm.py:268-273 (premature 'mark generating' без task_id перед retry loop). Fix: 4 рядки видалено. 3 topics reset до pending, 5 podcastів ready, 10 missing. NBLM rate-limited, RETRY_DELAYS=72h кандидат на скорочення.

Что зробити: Morning session перевір tool_use_integration-1 статус (ready/failed/pending?). Якщо ready/failed → fix end-to-end confirmed, restart bulk на 13 тем (rate-limit loop очищений). Якщо pending → retry залишається в loop, потребує перезавантаження модулю.

Блокери: rate-limit loop (API recovery очікується, 24-72 год). Parallelno: article dispatcher (Фаза В) не залежить.

Зробити: поділи HOT.md + WARM.md на старті.