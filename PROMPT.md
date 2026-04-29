Проект: sam

Стан: Phase 6.2 (NBLM async polling) активна, lazy re-attach верифіковано на проді (task 7af67aad успішно re-attach при рестарті 18:54). Виявлено критичний stale task_id баг: NBLM артефакти готові в UI але CLI wait повертає timeout (~24h протухання). Дві HOT memory drifts очищені.

Наступний крок: реалізувати stale task_id recovery (fallback на `artifact list` після 5+ timeout-ів) → закрити video вручну або через fallback → three-tier migration для Meggy/Ed/Garcia/Abby-v2.

Блокери: немає. Активна гілка: main (b39bfaf).

---

Не забути: скинь HOT.md + WARM.md з `/workspace/sam/` на старті сесії. Читай Правило нуль у MEMORY.md.