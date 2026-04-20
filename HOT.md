---
project: sam
updated: 2026-04-20
---

# HOT — Sam

## Now

Phase 2 пункт (2) — **callback handlers для pinned акордеону**. Рендерер готовий з минулої сесії (`render_pinned()` + `build_keyboard()` заглушка), перенос `shared/curriculum/` + `shared/{notebooklm,podcast}_module.py` у `sam/` виконано цією сесією. Імпорти чисті, `sys.path.insert` хаки прибрані, sam бігає на новому layout-і.

## Last done

**Phase 3 (relocate) + catch-up workspace-репо — виконано за одну сесію.**

### Catch-up workspace-репо (5 комітів, -10000+ рядків):
- Видалено 45 backup-файлів: 19 у `sam/data/*.{bak,deprecated,old,stub,merged}-*`, 17 у `sam/{main,modules/*,core/tools}.py.bak-phase22..29-*`, 9 у `shared/*.{bak-phase23..29,deprecated-phase25}-*`.
- **Фундаментальний фікс:** `git rm --cached -r sam/` + `echo "sam/" >> .gitignore` у workspace-репо. Причина: sam/ історично був доданий як звичайна папка ДО появи `sam/.git/`, і workspace-репо тримав 45 blob-файлів паралельно з sam-репо. Це була першопричина `chkp2` "бага з shared/" — більше немає.
- Untracked `health_monitor.log` (356KB runtime noise) + додано у `.gitignore`.
- BACKLOG.md додано у workspace-репо.
- Submodule-like pointer bumps для abby-v2, ed, insilver-v3. Skipped insilver-v2, kit (локальний runtime шум, не наша сесія).

### Phase 3 relocate (2 коміти):
- `shared/curriculum/` (7 файлів) → `sam/curriculum/`
- `shared/notebooklm_module.py` → `sam/core/notebooklm_module.py`
- `shared/podcast_module.py` → `sam/core/podcast_module.py`
- Rewrite imports у 7 sam-файлах: `core/tools.py`, `modules/{base,curriculum,pinned,state_manager,notebooklm,podcast}.py`.
- Прибрано `sys.path.insert(parent.parent.parent)` хаки у `modules/notebooklm.py` і `modules/podcast.py`.
- Fixed relative imports у `core/podcast_module.py`: `from .agent_base` → `from shared.agent_base`, `from .curriculum` → `from curriculum`.
- 35 replacements у docstrings/comments/log-names у 12 файлах для ментальної гігієни.
- `.gitignore` у sam-репо: + `__pycache__/`, `*.pyc` (були tracked раніше).
- **Live-tested:** `/pin` → `msg_id=1222` OK, "як справи" → `Router: intent=chat conf=0.95` → `Tool use iteration 1: ['get_hub']` → відповідь згенерована. Найгарячіший шлях (agentic loop з читанням курікулома) — зелений.

## Next

**Phase 2 пункт (2) — callback handlers:**

- `cur_toggle_{id}` / `cur_pipeline_{id}` / `fmt_check_{id}_{fmt}` + `cur_new` / `cur_map` реалізація.
- Акордеон: expand-in-place через `editMessageText`, persistent state у `data/pinned_expanded.json` (або поле у `pinned_state.json` — відкрите питання у WARM).
- Розширити `build_keyboard()` щоб генерувала per-topic кнопки для expanded тем.
- Переключити `modules/pinned.py` з старої `render()` на нову `render_pinned()` + `build_keyboard()`.
- Smoke + integration.

**Час:** ~2 год.

## Blockers

Жодних.

## Active branches

- **sam-репо** (`main`): `2d5e265` (Phase 3 relocate). Запушено у origin/main.
- **workspace-репо** (`master`): `513f608` (remove shared curriculum+notebooklm+podcast). Запушено у origin/master.

## Open questions at the moment

- `pinned_expanded.json` як окремий файл чи поле у `pinned_state.json`? (не вирішено, низький пріоритет).
- Після Фази 2 — чи потрібен `/pipeline` як окрема команда, чи достатньо кнопки `cur_pipeline_{id}` у pinned?

## Reminders

- Перед тестуванням — запустити `journalctl -u sam -f` **до** надсилання повідомлення боту.
- Використовувати `/home/sashok/.openclaw/workspace/sam/` (ніяких `~/sam/`).
- API keys маскувати до останніх 4 символів.
- **`chkp2` НЕ оновлює 3 яруси сам** — це робота Claude ПЕРЕД викликом chkp2. `chkp2` тільки комітить+пушить + guard `read -p "Ready?"`.
- **`chkp2` баг з shared/ — ліквідовано структурно.** Workspace-репо тепер не трекає `sam/`, тож конфлікту "sam modifications vs shared modifications у одному git status" більше немає. Workspace-репо комітиться вручну (там живе shared/, BACKLOG, infra).
- **SSH: no base64, no scp, no nano .md.** Точкові правки — sed. Великі блоки — `cat > /tmp/patch.py << 'PYEOF' ... PYEOF && python3 /tmp/patch.py`. Threshold для WinSCP — >200 рядків.

## Remotes nuance (не баг, артефакт)

Обидва репо (sam і workspace) пушаться у `github.com/sandalya/sam.git`, sam → `main`, workspace → `master`. Це historical naming-артефакт, функціонально працює. Низький пріоритет переносу у окремий repo.
