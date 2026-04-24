---
project: sam
updated: 2026-04-24
---

# HOT — Sam

## Now

ТТС глибокі посилання (deep-links) та NBLM reset для Multi-agent координації завершені. TTS посилання тепер коректно надсилають аудіо у чат (баг користувача #1 закритий). NBLM /regen крутиться коректно для agent_architecture-2 (баг користувача #2 закритий). Планування Flashcards interactive узгоджено: переиспользуем ключ NBLM, використовуємо Sonnet generator, SR (spaced repetition) йде у бекілог.

## Last done

**Сесія 24.04 — TTS deep-link fix + NBLM reset для Multi-agent**

- **TTS посилання баг** — користувач скаржився що /tts_{topic_id} посилання не надсилають аудіо в чат прямо. Виявлено: `_handle_deep_link()` викликав `send_audio()` але путь до файлу був неправильний (відносний замість абсолютного в `/workspace/sam/data/audio/`). Виправлено: змінено рядок у `modules/pinned.py::_handle_deep_link()` на `tts_{id}` обробник — абсолютний путь + перевірка файлу перед `send_audio()`. Тест: `/tts_ai-101` успішно надіслав MP3 у чат.
- **NBLM reset для agent_architecture-2** — тема з failed NBLM форматом (статус MISSING). Запущено `/regen`, відбулось переписання статусу з MISSING→pending, NBLM generator знов запустився за retry schedule (перша спроба успішна). Внутрішня механіка: `reset_failed_to_pending()` в `curriculum/mutations.py` + `run_pipeline()` перепускає формат через `nblm_generate()`. Статус тепер "ready" за 8 хвилин.
- **Flashcards interactive — план узгоджено** (окремий task, деталі нижче).

## Next

1. **Flashcards interactive (Phase 6.1)** — реалізація почне наступну сесію. План: 
   - Переиспользування NBLM ключа (один блокнот NBLM на тему, одна бібліотека карток всередині).
   - Sonnet generator для контенту карток (питання/відповіді з усього notebook).
   - Без SR наразі — базові карточки, алгоритм повтору (SM-2/Leitner) в бекілог.
   - Глибокі посилання: `flashcards_{topic_id}` в pinned renderer.
2. **Моніторинг token_audit** (з 23.04) — через 2-3 дні: перевірити логи на `cache_read` (Sam) та `cache_created` 1h TTL (Abby). Якщо економія не з'явилась — діагностика.
3. **Абби-v2 image-gen баг** — кнопка Image 4 платного генерування все ще не працює. Блокує повне тестування. Приоритет після Flashcards якщо час.
4. **Garcia мігрування** — прочитати `brain.py` щоб підтвердити гіпотези і запустити G1-G3 для себе (if time).

## Blockers

Немає блокерів на Flashcards. TTS і NBLM баги закриті.

## Active branches

- **sam-репо (`main`)** — готовий до коміту: TTS deep-link fix + NBLM reset в `modules/pinned.py` і `curriculum/pipeline.py`. Flashcards черга для наступної сесії.
- **workspace-репо (`main`)** — невеликі оновлення у `meta/notes/BACKLOG.md` (Flashcards запис).

## Open questions

- Чи користувач буде часто використовувати Flashcards або це разова активність за темою? Залежить від паттерну навчання.
- Чи варто вже у Phase 6.1 додати експорт карток (ANKI format) чи це Phase 6.3?
- Чи NBLM ключ перестав бути бутлнеком на retry? (Рейт-ліміт 6/день — тепер 16 тем у фоні, але з новим retry 72h стратегія).

## Reminders

- Перед тестуванням Flashcards — запустити `journalctl -u sam -f` перед надсиланням повідомлення.
- Після фіксів в pinned.py — обов'язково тестувати тісно пов'язані команди: `/cur`, `/done` (які оновлюють pinned).
- NBLM retry логи в `/workspace/sam/data/nblm_retry.log` — слідкувати за статусами "retrying" та "success".
