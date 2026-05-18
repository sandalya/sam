---
project: sam
updated: 2026-05-18
---

# HOT — Sam

## Now

Тестував prompt caching після фіксу max_tokens і SYSTEM_PROMPT — верифікація роботи у production режимі.

## Last done

- Застосував фіксу max_tokens у prompt caching механізмі
- Оновив SYSTEM_PROMPT для коректної роботи з кешем
- Провів end-to-end тестування prompt caching на проді
- Перевірив що кеш активується і скорочує latency

## Next

Продовжити роботу над flashcards — реалізація нових фіч або поліпшення інтерактивності.

## Blockers

None.

## Active branches

- **sam-repo (`main`)**: 4 NBLM interventions live (47efc76, d822a29, 6e5589c, 26cf181). 47 unit-tests PASS. Prompt caching deployed & verified (18.05).
- **Production Pi5**: sam.service + sam-rss.service active. Prompt caching tested on prod.

## Open questions

- Flashcards interactive mode — які саме фіч потребують поліпшення?
- Voice extraction vs Evals vs Article dispatcher — рішення після flashcards iteration?

## Reminders

- **Sprint B VERIFIED (04.05)**: All 4 NBLM interventions live, 18/18 podcasts ready.
- **Daily digest guard deployed (05.05)**: Env-flag DAILY_DIGEST_ENABLED=false активна.
- **2 P3 bugs backlog**: external_stop zombie, regen message — non-blocking.
- **RSS feed**: 18 items, deep-links functional.
- **Prompt caching (18.05)**: max_tokens + SYSTEM_PROMPT фікс deployed, tested on prod.
- **Flashcards Phase 6.1**: Card mode & Quiz mode, deep-links functional, 3/3 Ed тести PASS.