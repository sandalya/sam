---
project: sam
updated: 2026-04-24
---

# HOT — Sam

## Now

Phase 6.1 Flashcards interactive MVP — завершена e2e. LLM-генератор flashcards (Sonnet, inline cards у curriculum.json), UI (pinned FC label), FSM (card + quiz mode), deep-link `fc_{topic_id}` — все працює на живому боті. Тест зроблено на `rag_retrieval-1`: deck ready з 10 картками, пройдено card mode + quiz mode.

## Last done

**Сесія 24.04 — Flashcards interactive Phase 6.1**

- **models.py** — додано `cards`, `deck_size`, `last_mode` у `TopicFormat`.
- **pipeline.py** — `LLM_FORMATS = {"flashcards"}`, `CARDS_PER_TOPIC=10`, `_FLASHCARDS_PROMPT_TEMPLATE`, `FLASHCARDS_MAX_RETRIES=1`, новий генератор `_generate_flashcards_llm` (Sonnet via `shared.agent_base`, `asyncio.to_thread` для sync-client виклику), валідатор `_parse_and_validate_cards` (JSON + schema checks). Flashcards винесено з NBLM_FORMATS.
- **modules/curriculum.py** — `cmd_regen` прийнтає опціональний `topic_id`: `/regen rag_retrieval-1` робить regen тільки однієї теми. Повідомляє якщо тема не існує або не потребує regen.
- **curriculum/renderer.py** — `_fc_label` + вставка `FC` у `_render_topic_line` між TTS і Exam. Неклікабельно якщо `!ready` або `!cards`.
- **main.py** — імпорт `modules.flashcards`, `elif payload.startswith("fc_")` у `_handle_deep_link`, `CallbackQueryHandler(handle_flashcards_callback, pattern=r"^fc_")`.
- **modules/flashcards.py** — новий файл ~280 рядків. `_Session` dataclass (in-memory, chat_id → session), handlers для mode picker, flashcard FSM (show/know/dunno), quiz FSM (shuffle permutation, pick, feedback), next/retry/switch_mode/exit, фінальний екран із статистикою. Quiz feedback скорочений (без дублю питання).
- **e2e тест**: `rag_retrieval-1` → FC deep-link → mode picker → card mode 3 картки → вихід. Потім quiz mode → правильна/неправильна відповідь + feedback. Логи чисті, Sonnet генерує 10 карток за ~42 секунди (1 attempt).

## Next

1. **Міграція flashcards для решти 17 тем** — reset `flashcards.status` → `pending` для всіх де немає `cards`, потім `/regen` (масовий або батч по 3-4 теми щоб не чекати Sonnet × 17 одразу). Орієнтовно 15-20 хв очікування на генерацію.
2. **Ed тести `11_flashcards.json`** — три блоки: `11a_flashcard_mode`, `11b_quiz_mode`, `11c_completion_and_retry`. Перевірити чи є асертіци `assert_button_count`, `click_button_by_index`, `assert_text_matches_any`; додати в `ed/runner/assertions.py` якщо нема (≤30 хв).
3. **Додати `log.info` у `_on_*` handlers у `modules/flashcards.py`** — 5 хв, зараз handler-и callback-ів не логуються і debug важкий.
4. **NBLM slides/infographic RPC ADD_SOURCE failed** — окремий баг, blocker для повного pipeline. Потребує діагностики (токен протух? квота? сесія?). **Не стосується Phase 6.1**.

## Blockers

- `chkp3` зламався на цій сесії: Haiku max_tokens=8000 обрізало JSON, Sonnet fallback timeout 120s. HOT оновлено руками замість AI-summarization. Потребує фіксу (підняти max_tokens, або chunk WARM).
- 6 тем у стані `generating` (tool_use_integration-1: slides/podcast_nblm/video; agent_architecture-2: slides/infographic; system_operations-5: slides). Застрягли після failed NBLM. Потребує reset → pending (одноразовий скрипт). Низький пріоритет, не блокер для Phase 6.1.

## Active branches

- **sam-репо (`main`)** — потребує коміт: всі зміни Phase 6.1 (5 файлів нових/змінених).
- **workspace-репо** — без змін.

## Open questions

- Чи робити Phase 6.2 SR (spaced repetition) зразу після міграції, або чекати 1-2 тижні реального використання щоб зрозуміти потребу?
- `_SESSIONS` — in-memory dict, скидається при рестарті бота. Якщо Саша в процесі сесії, і бот рестартнеться — сесія губиться. Для Phase 6.1 прийнятно, для 6.2 переглянути персистентність.

## Reminders

- Перед тестуванням flashcards — запустити `journalctl -u sam.service -f` ПЕРЕД кліком у боті.
- `tool_use_integration-1` має статус `state: pending` — `rag_retrieval-1` довелося перевести в `active` щоб з'явитись у pinned (pinned показує тільки active). Врахувати у міграції — теми для яких генеруємо flashcards мусять бути `active` щоб FC label був видимий.
- `/regen {topic_id}` — нова одиночна команда, працює. Для масової міграції — `/regen` без аргументу.
