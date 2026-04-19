---
project: sam
updated: 2026-04-19
---

# HOT — Sam

## Now

Phase 2 пайплайну + interactive pinned. Pozицiя: пункт (1) Renderer v2 — розширюю `shared/curriculum/renderer.py`, додаю групування по станах (🟢/🟡/✅), лічильники виду "3/7 ✓✓✓○○○○", окрема функція `build_keyboard()`.

## Last done

- Curriculum v2 data-model закрита: `shared/curriculum/` пакет живий (`models.py`, `storage.py`, `mutations.py`), 18 тем / 8 островів у `data/curriculum.json`.
- Sam engine-free: `shared/curriculum_engine.py` видалено (`.bak-phase29` залишився у shared/).
- `modules/curriculum.py` скорочено до `cmd_cur_add` + `cmd_done`.
- Activity tracking відокремлено: `data/learning_state.json` тримає тільки `last_activity` + `streak_days`.
- Proactive engine базовий: три тригери (inactive ≥3, ready-артефакти, all-consumed) через `job_daily_digest`.
- Pinned read-only: `modules/pinned.py` + `renderer.py` рендерять HTML без клавіатури.

## Next

Розширити `shared/curriculum/renderer.py::render_pinned()`:
- Додати лічильники по островах: `3/7 ✓✓✓○○○○`.
- Виділити окрему `build_keyboard()` у тому ж файлі (поки порожню-заглушку, callback-handlers — пункт (2) Phase 2).
- Не ламати поточний read-only вивід — рендер має працювати як з keyboard, так і без.

Очікуваний час: 1.5-2 год.

## Blockers

None.

## Active branch

TBD — перевірити `git status` на початку сесії. Якщо ще на main — створити гілку `phase-2/renderer-v2`.

## Open questions at the moment

- Renderer v2 — розширити існуючий чи переписати? **Рекомендація**: розширити, додати окрему `build_keyboard()`. Переписувати немає сенсу, `render_pinned()` короткий.

## Reminders

- Перед тестуванням — запустити `journalctl -u sam -f` **до** надсилання повідомлення боту.
- Використовувати `/home/sashok/.openclaw/workspace/sam/` (ніяких `~/sam/`).
- API keys маскувати до останніх 4 символів.
