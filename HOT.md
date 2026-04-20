---
project: sam
updated: 2026-04-20
---

# HOT — Sam

## Now

Phase 2 завершено. Наступний крок — дочистити NBLM podcast regen + Phase 3 (діалоговий тест).

## Last done

**Phase 2(4) — auto-pipeline + /status + smoke (сесія 20.04, друга, продовження)**

- `core/tools.py`: `execute_tool()` отримав `bot`/`chat_id` params. Після `add_topic` tool — auto `run_pipeline()` через `asyncio.create_task`.
- `main.py`: `handle_chat_with_tools()` прокидає `bot`/`chat_id` в `execute_tool`.
- `modules/curriculum.py`: `cmd_cur_add()` — auto-pipeline після створення теми. Новий `cmd_status()` — показує ready/generating/failed/pending по всіх форматах.
- Smoke test: `/cur_add Test Pipeline Smoke` → LLM enrich → тема створена → notebook created → pipeline started → slides generating. Тестову тему видалено.

## Next

1. Дорегенерити rate-limited NBLM подкасти (10 тем).
2. Broken notebooks (agent_architecture-2, rag_retrieval-1).
3. Phase 3 — діалоговий тест (EXAM).
4. Case study doc agentic loop.

## Blockers

- Google NBLM rate limit ~6/день.

## Active branches

- **sam-репо** (`main`): Phase 2 done. НЕ запушено.

## Open questions

- `/pin` в меню бота біля скрепочки.

## Reminders

- Перед тестуванням — запустити `journalctl -u sam -f` **до** надсилання повідомлення боту.
- Використовувати `/home/sashok/.openclaw/workspace/sam/`.
- API keys маскувати до останніх 4 символів.
- **`chkp2` НЕ оновлює 3 яруси сам** — це робота Claude ПЕРЕД викликом chkp2.
- Workspace-репо комітиться вручну (не через chkp2).
