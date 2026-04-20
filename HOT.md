---
project: sam
updated: 2026-04-20
---

# HOT — Sam

## Now

Phase 2 пункт (1) Renderer v2 **закрито**. Наступне — перенос `shared/curriculum/` + `shared/notebooklm_module.py` + `shared/podcast_module.py` у `sam/` (структура: `sam/curriculum/` + `sam/core/notebooklm_module.py` + `sam/core/podcast_module.py`). Це передумова перед пунктом (2) Phase 2 (callback handlers), щоб не плодити нових імпортів `shared.curriculum` по коду.

**Перенос буде окремою "великою" сесією разом з catch-up workspace-репо** — див. BACKLOG Infrastructure.

## Last done

- **Renderer v2 готовий** у `shared/curriculum/renderer.py` (~390 рядків). Додано:
  - `render_pinned(state, bot_username, now_hhmm, expanded_mastered)` — групування 🟢/🟡/✅ + `🗺 Острови: ...` + прогалини.
  - `_render_topic_v2()` з лічильником `N/7 ✓●○` (exam = 7-й формат).
  - `build_keyboard()` — заглушка з `[🆕 Нова тема] [🗺 Карта]`, без per-topic кнопок (це пункт (2)).
  - Стара `render()` і `_render_topic()` не чіпані — `modules/pinned.py` працює без змін.
- Smoke-тест на реальних даних пройшов. Mastered колапсить до `✅ Засвоєні (N) ▸`.
- Фікс навздогін: renderer.py було незакомічено у workspace-репо (chkp2 не дійшов), зафіксовано у коміті `d204a47 (master)`, тег `pre-relocate-20260420-130709`.

## Next

**Окрема сесія — "Великий рефакторинг shared":**

1. **Catch-up workspace-репо:** зафіксувати Phase 29 deletes + модифікації у `shared/curriculum/` + прибрати зайві backup-файли у sam/data/. ~30-40 хв.
2. **Перенос:** `shared/curriculum/` → `sam/curriculum/`, `shared/notebooklm_module.py` → `sam/core/notebooklm_module.py`, `shared/podcast_module.py` → `sam/core/podcast_module.py`. ~1 год.
3. Оновити ~15 імпортів по файлах: `core/tools.py` (×2), `modules/{state_manager,pinned,base,curriculum,notebooklm,podcast}.py`. Прибрати `sys.path.insert(...)` хаки в обгортках `modules/notebooklm.py` + `modules/podcast.py`.
4. Restart `sam.service` + smoke. Якщо ок → `chkp2`.

**Потім — Phase 2 пункт (2) callback handlers:**

- `cur_toggle_{id}` / `cur_pipeline_{id}` / `fmt_check_{id}_{fmt}` + `cur_new` / `cur_map` реалізація.
- Акордеон: expand-in-place через `editMessageText`, persistent state у `data/pinned_expanded.json`.
- Розширити `build_keyboard()` щоб генерувала per-topic кнопки для expanded тем.

## Blockers

Жодних технічних. Workspace-репо брудний (багато Phase 29 deletes не зафіксовано), але це не блокує наступну сесію — просто треба її почати з catch-up.

## Active branch

sam-репо: `main` (чистий, все на origin/main). Workspace-репо: `master` (d204a47, 3 коміти попереду origin/master — не пушені навмисно, пушнемо разом з catch-up).

## Open questions at the moment

- **Жодних — план ясний.** Перелік що переносити і куди: закрито минулою сесією.

## Reminders

- Перед тестуванням — запустити `journalctl -u sam -f` **до** надсилання повідомлення боту.
- Використовувати `/home/sashok/.openclaw/workspace/sam/` (ніяких `~/sam/`).
- API keys маскувати до останніх 4 символів.
- **`chkp2` баг** — не комітить зміни у `shared/`. Якщо наступна сесія чіпатиме shared/ — після `chkp2 sam ...` треба ще вручну `cd workspace; git add -A; git commit -m "..."`. Фікс у BACKLOG.
- **Гіркий урок:** workspace-репо має submodule-архітектуру. `sam/` це submodule. Зміни в `shared/` — у workspace-репо. Зміни в `sam/` — у sam-репо. `chkp2` про це не знає.

## Garcia — статус на момент переносу

Garcia запущена і працює, але **podcast не використовує** (`garcia/modules/podcast.py` — мертвий файл, не імпортований `garcia/main.py`). Тому перенос `shared/podcast_module.py` у sam/ його не зламає. Імпорт у мертвому файлі стане "поламаним", це ок — додати у BACKLOG позначити deprecated або видалити.

## Sam-v2 — також ігнорується

`sam-v2/` це неактуальна паралельна гілка проекту (ти підтвердив: "якийсь момент робили паралельно, перестрибнули на 1 версію"). Імпорти `shared.curriculum*` у ньому перестануть працювати після переносу — не переживаємо, проект мертвий.
