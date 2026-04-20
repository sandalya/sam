---
project: sam
updated: 2026-04-20
---

# HOT — Sam

## Now

Phase 2 пункт (3) — **Pipeline orchestrator**. Рендер і callback handlers готові. Deep-links у pinned працюють (expand/collapse, fmtcheck, pipeline stub, map stub). Tool `add_topic` додано в agentic loop.

## Last done

**Phase 2 пункт (2) — callback handlers + deep-links (сесія 20.04).**

- `curriculum/renderer.py`: `render_pinned()` розширено — `expanded_topic_ids`, per-topic `_render_topic_expanded()` з deep-links (`fmtcheck_{id}_{fmt}`, `expand_{id}`, `collapse_{id}`, `pipeline_{id}`, `map`, `expand_mastered`). Footer з `/cur_add` підказкою + `[🗺 Карта]`.
- `modules/pinned.py`: переключено з `render()` на `render_pinned()`. Expanded state у `data/pinned_expanded.json` (load/save/toggle).
- `main.py`: `cmd_start` розширено deep-link dispatch (`_handle_deep_link`). Парсить payload → expand/collapse/fmtcheck/pipeline/map. Silent delete `/start` команди.
- `core/tools.py`: tool `add_topic` (schema + `_h_add_topic` handler) — Sem додає теми через розмову, використовує `_enrich_topic_via_llm` з `modules/curriculum.py`.
- Live-tested: `/pin` → expand → fmtcheck slides+podcast_nblm → counter 2/7 ✓ → collapse ✓. Pipeline + map — stubs.

## Next

**Phase 2 пункт (3) — Pipeline orchestrator** (`curriculum/pipeline.py`). `cur_pipeline_{id}` → запускає генерацію всіх 7 форматів за content_style порядком (audio-first або visual-first). ~2-3 год.

## Blockers

Жодних.

## Active branches

- **sam-репо** (`main`): Phase 2 пункт (2). Запушено у origin/main.
- **workspace-репо** (`master`): BACKLOG оновлений вручну.

## Open questions at the moment

- Після Фази 2 — чи потрібен `/pipeline` як окрема команда, чи достатньо deep-link `pipeline_{id}` у pinned? (Зараз є тільки deep-link.)

## Reminders

- Перед тестуванням — запустити `journalctl -u sam -f` **до** надсилання повідомлення боту.
- Використовувати `/home/sashok/.openclaw/workspace/sam/` (ніяких `~/sam/`).
- API keys маскувати до останніх 4 символів.
- **`chkp2` НЕ оновлює 3 яруси сам** — це робота Claude ПЕРЕД викликом chkp2.
- **SSH: no base64, no scp, no nano .md.** Точкові правки — sed. Великі блоки — PYEOF. Threshold для WinSCP — >200 рядків.
- Workspace-репо комітиться вручну (не через chkp2).

## Remotes nuance (не баг, артефакт)

Обидва репо (sam і workspace) пушаться у `github.com/sandalya/sam.git`, sam → `main`, workspace → `master`. Historical artifact.
