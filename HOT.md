---
project: sam
updated: 2026-04-24
---

# HOT — Sam

## Now

**Phase 6.1 Flashcards — завершено.** 18/18 тем мають flashcards ready (10 карток кожна). Ed тести `11_flashcards.json` — 3/3 PASS за 1:44. Повний UI-потік (card mode + quiz mode + completion) перевірений автоматично.

## Last done

**Сесія 24.04 — Phase 6.1 finalize**

- **Міграція flashcards 18/18 тем** — reset pending → `/regen --only flashcards` → Sonnet згенерював усі 18 деків без жодного фейлу (0 retry) за ~8 хв.
- **`cmd_regen --only <fmt>`** (`modules/curriculum.py`) — опція парсить `--only flashcards` у будь-якій позиції args, фільтрує теми лільки за вказаним форматом, передає в `_run_regen(silent=True)` щоб приглушити per-topic повідомлення.
- **`run_pipeline(silent=True)`** (`curriculum/pipeline.py`) — приглушує `🚀 Pipeline для...`, `🏁 Pipeline завершено...`, `Flashcards готові...`, `✅ Всі формати вже згенеровані`. Помилки (`❌ Тема не знайдена`, `⚠️ Помилка fmt_key`, `Flashcards — помилка генерації`) залишаються видимими. Фінальне summary `_run_regen`: `🏁 Regen завершено: N/M ok`.
- **log.info у handlers** (`modules/flashcards.py`) — 1 у dispatcher + 8 у кожен `_on_*` (mode_pick, show_answer, self_eval, quiz_pick, next, retry, switch_mode, exit). Формат: `fc {handler_name}: chat={chat_id} data={data!r}`.
- **Ed transport `events.MessageEdited`** (`ed/transports/telegram.py`) — новий listener `on_bot_edit` замінює повідомлення в `_responses` за id (або додає як нове якщо не знайдено). **Без цього Ed не бачив edit_message_text** → перший прогон фейлив timeout-ами (90с × 3). З патчем: 3/3 PASS за 1:44. Критично для **всіх ботів з FSM на edit** (flashcards, exam, можливо інші).
- **`11_flashcards.json`** (3 блоки):
  - `fc_card_mode_basic` — deep-link → card mode → show → know → next
  - `fc_quiz_mode_basic` — deep-link → quiz mode → pick → feedback → next
  - `fc_quiz_completion` — 22 steps: 10 карток × (pick + next) → фінальний екран + retry/switch buttons
- Комітнуто: sam `a0e8b84`, ed `eb0c26e`. Пуш у обидва репо ок.

## Next

1. **Phase 6.2 SR (spaced repetition)** — відкласти на 1-2 тижні реального використання flashcards, щоб зрозуміти що саме потрібно (SM-2 / Leitner / власний алгоритм, персистентна історія).
2. **chkp3 max_tokens bug** — Haiku обрізає JSON при WARM+context >13k tokens, Sonnet fallback timeout 120s. HOT цієї сесії оновлено руками. Варіанти: max_tokens=16000, chunk WARM, timeout=300s.
3. **NBLM RPC ADD_SOURCE failed** — окремий баг. Діагностика (токен протух / квота / сесія). Блокує slides/podcast_nblm/infographic/video, хоча нас конкретно Phase 6.1 не блокувало.
4. **6 тем у `generating`** — `tool_use_integration-1`, `agent_architecture-2`, `system_operations-5` форматів slides/podcast_nblm/video/infographic застрягли після failed NBLM. Reset скрипт: знайти всі `generating` і перевести в `pending`.

## Blockers

- **chkp3 зламаний** на сесіях з великим WARM — Haiku max_tokens=8000 обрізає JSON, Sonnet fallback timeout 120s. Чекпоінт цієї сесії зроблено руками.
- **NBLM pipeline лежить** (RPC ADD_SOURCE failed) — блокує slides/podcast_nblm/infographic/video. Flashcards не чіпає. Низький пріоритет без явної потреби слухати podcast.

## Active branches

- **sam-репо (`main`)** — на HEAD `a0e8b84`. Clean.
- **ed-репо (`main`)** — на HEAD `eb0c26e`. Clean.
- **workspace-репо** — без змін.

## Open questions

- Phase 6.2 SR — скільки чекати перед стартом? 1-2 тижні, або раніше як з'явиться дані через `deck_size`/`last_mode` use patterns?
- `_SESSIONS` — in-memory dict, рестарт бота = втрата сесії. Для 6.2 потрібна персистентність (можливо JSON файл `data/flashcards_sessions.json` з TTL).
- Ed: чи є сенс додати `assert_callback_fired` — перевіряти що `q.answer()` був викликаний? Зараз фіксимо лише через видимий UI-стан.

## Reminders

- **Ed `MessageEdited` тепер підключений** — якщо майбутні тести FSM-ботів не працюють, це НЕ та проблема; шукати інше.
- **`/regen --only <fmt>`** — для будь-якого одиночного формату. `flashcards`, `slides`, `podcast_tts`, etc.
- **`/regen --only flashcards <topic_id>`** теж працює — силант-міграція для конкретної теми.
- Перед тестуванням flashcards ручками — `journalctl -u sam.service -f | grep fc ` для debug (тепер кожен callback логується).
- `rag_retrieval-1` в `active` state — видимо в pinned. Інші теми (не-active) видимі тільки через deep-link `fc_<topic_id>`, у pinned не з'являться.