---
project: sam
updated: 2026-05-16
---

# HOT — Sam

## Now

Покращено `/nbstatus` команду: замінено · на ▪ для відсутнього статусу, додано <code> блок для вирівнювання, обрізання назв до 22 символів, додано легенду. Потребує рестарту sam.service.

## Last done

- Змінено separator-indicator з · на ▪ для ясності (розрізнення від пропуску статусу)
- Додано <code> блок навколо таблиці для моноспейсового вирівнювання
- Реалізовано обрізання назв форматів до 22 символів (довші скорочуються)
- Додано легенду внизу `/nbstatus` з поясненнями символів
- Верифіковано на 1-2 notebook UUIDs локально перед розгортанням

## Next

1. **systemctl restart sam.service на Pi5** — застосувати зміни в production.
2. **Перевірити `/nbstatus` на Pi5** — убедитися що ▪ відображається, вирівнювання чітке, назви обрізані коректно.
3. **Фінальна верифікація 18/18 подкастів** — якщо ще не зроблено, перевірити що усі podcasts у статусі ready/failed (не pending).
4. **Вибір наступної фази** — Voice extraction (Sprint C, ~2h) vs Evals (Sprint D, ~3h) vs Article dispatcher (Phase C, паралельно).

## Blockers

None. `/nbstatus` improvement — cosmetic, non-blocking.

## Active branches

- **sam-repo (`main`)**: 4 interventions live (47efc76, d822a29, 6e5589c, 26cf181). 47 unit-tests PASS. `/nbstatus` покращення готові до push.
- **Production Pi5**: sam.service + sam-rss.service active. systemctl restart очікується для завантаження `/nbstatus` змін.

## Open questions

- **18/18 podcast final status**: Потребує перевірки на Pi5 після restart.
- **Наступна фаза**: Voice extraction vs Evals vs Article dispatcher — рішення після `/nbstatus` верифікації.

## Reminders

- **Sprint B VERIFIED (04.05)**: All 4 NBLM interventions live, 18/18 podcasts очікуються ready (перевірити після restart).
- **Daily digest guard deployed (05.05)**: Env-flag DAILY_DIGEST_ENABLED=false працює.
- **2 P3 bugs backlog**: external_stop zombie, regen message — обидва non-blocking.
- **RSS feed**: 18 items, deep-links functional.
- **/nbstatus improvement**: ▪ vs ·, <code> вирівнювання, обрізання до 22 символів, легенда — готові до deployment.