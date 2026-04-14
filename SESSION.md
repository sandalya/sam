# SESSION — 2026-04-14 19:05

## Проект
sam

## Що зробили
NbLM rate limiting: RETRY_DELAYS повернуто на [0,1560,3060], пауза 45с між форматами, підсумкове повідомлення одне на тему після всіх форматів. Формати оновлено до 5 (video/podcast/flashcards/slides/infographic). TTS іконки уніфіковано з NbLM стилем

## Наступний крок
Наступне: превью в /cur картках прибрати, або продовжити по Опусу Фаза 3 Smart Router

## Контекст
curriculum_engine.py: _item_keyboard, _run_all_formats, RETRY_DELAYS
