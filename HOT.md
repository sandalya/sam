---
project: sam
updated: 2026-04-20
---

# HOT — Sam

## Now

Phase 2 пункт (3) — **Pipeline orchestrator** готовий. Масова перегенерація NBLM подкастів запущена (6/16 started, 8 rate-limited на завтра, 2 broken notebooks).

## Last done

**Phase 2 — renderer rewrite + pipeline (сесія 20.04, друга)**

- `curriculum/renderer.py`: повний rewrite — компактний UI без акордеону. Per-topic рядок: `▸ Title` + `📓 NB · 🎙 TTS · 🧠 EXAM` на другому рядку. Прибрано: expand/collapse deep-links, `_render_topic_expanded`, `_format_counter`, `build_keyboard`, `pinned_expanded.json`. Тільки active теми в pinned (pending/mastered сховані). "Курікулом"→"Курікулум".
- `curriculum/pipeline.py`: новий файл — orchestrator `run_pipeline()`. Послідовна генерація за content_style порядком (audio-first/visual-first), skip ready/generating/skipped, refresh pinned між кроками, фінальне повідомлення.
- `core/podcast_module.py`: додано `generate_tts_for_pipeline()` — standalone функція для pipeline без залежності від Update/AgentBase.
- `main.py`: pipeline stub замінено на `asyncio.create_task(run_pipeline(...))`. Прибрано expand/collapse handlers і toggle imports.
- `modules/pinned.py`: `_render_current()` спрощено — прибрано expanded params.
- Стан тем: 4 active (tool_use_integration-1, agent_architecture-1/2/3), 12 pending, 1 mastered. `evaluation_testing-2` (Test Topic For Cleanup) видалено.
- NBLM podcast regen: 6 started (2 completed, 2 pending), 8 rate-limited, 2 broken notebooks (agent_architecture-2, rag_retrieval-1).

## Next

1. Перезапустити rate-limited NBLM podcast генерацію (10 тем).
2. Розібратись з 2 broken notebooks (multi-agent координація, RAG).
3. Автозапуск pipeline при `add_topic`.
4. `/status` або `/queue` команда.
5. Phase 2 пункт (4) — smoke + integration.

## Blockers

- Google NBLM rate limit — ~6 audio генерацій на день.
- 2 broken notebooks (RPC failed).

## Active branches

- **sam-репо** (`main`): Phase 2 — pipeline + renderer rewrite. НЕ запушено.

## Open questions

- Автозапуск pipeline при add_topic — чи робити в цій фазі чи відкласти?
- `/pin` в меню бота біля скрепочки — додати.

## Reminders

- Перед тестуванням — запустити `journalctl -u sam -f` **до** надсилання повідомлення боту.
- Використовувати `/home/sashok/.openclaw/workspace/sam/`.
- API keys маскувати до останніх 4 символів.
- **`chkp2` НЕ оновлює 3 яруси сам** — це робота Claude ПЕРЕД викликом chkp2.
- Workspace-репо комітиться вручну (не через chkp2).
