---
project: sam
updated: 2026-04-20
---

# HOT — Sam

## Now

Phase 2-5 завершено. Regen молотить у фоні (16 тем, retry 72h). Наступне — Phase 6 (Depth Mode) після 1-2 тижнів використання.

## Last done

**Сесія 20.04, третя — Phase 3-5 + /regen + retry 72h**

- **NBLM retry 72h**: `RETRY_DELAYS = [0] + [3600] * 71` замість 3 спроб за 45 хв.
- **`/regen`**: масова дорегенерація всіх MISSING/failed форматів, працює у фоні через `asyncio.create_task`. Reset failed→pending перед запуском.
- **Reset stuck**: `tool_use_integration-1` slides скинуто з generating → pending.
- **Phase 3 — EXAM**: `modules/exam.py` — stateful 5-question dialog test. LLM генерує питання, LLM оцінює відповіді. Deep-link `exam_{id}` з pinned. Inline кнопки: ✅ Mastered, 🔄 Retry. `/exam_cancel` команда. Exam intercept в `handle_text` — якщо активний екзамен, всі повідомлення йдуть туди.
- **Phase 4 — Proactive triggers**: exam subtopic suggestion (кнопка "➕ Додати підтему по прогалині" з LLM-generated назвою). `proactive.py` переписано на curriculum v2 (3 тригери: unconsumed content, ready for exam, failed formats).
- **Phase 5 — Island map**: `modules/island_map.py` — повна карта островів з progress bars, per-topic status, gap detection vs AI-ландшафт. Deep-link `map` в pinned footer. Прогалини фільтруються по existing islands.
- **BotCommand list**: cur, jobs, notebooks, status, regen (прибрано start/digest/science/catchup/onboarding/profile/podcast/cur_add).
- **Case study doc**: `docs/AGENTIC_LOOP_CASESTUDY.md` — розбір agentic loop архітектури.
- **f-string fix**: Python 3.11 `\n` in f-string → винесено в змінні.
- **Digest fix**: max_tokens 3000→8000 (response обрізався, JSON не закривався). Fallback парсер для truncated JSON.

## Next

1. Тема "Agentic Loop & Tool Use" в курікулумі (case study як source material) — коли Саша готовий.
2. Phase 6 — Depth Mode (після 1-2 тижнів використання).

## Blockers

- Google NBLM rate limit ~6/день. Regen ретраїть кожну годину.

## Active branches

- **sam-репо** (`main`): Phase 3-5 done. НЕ запушено (4 коміти ahead).

## Open questions

- Немає.

## Reminders

- Перед тестуванням — запустити `journalctl -u sam -f` **до** надсилання повідомлення боту.
- Використовувати `/home/sashok/.openclaw/workspace/sam/`.
- API keys маскувати до останніх 4 символів.
- **`chkp2` НЕ оновлює 3 яруси сам** — це робота Claude ПЕРЕД викликом chkp2.
- Workspace-репо комітиться вручну (не через chkp2).
- **Не робити git commit перед chkp2** — chkp2 сам комітить.
