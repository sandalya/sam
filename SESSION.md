# SESSION — 2026-04-14 19:00

## Проект
sam

## Що зробили
Оновлено формати NbLM (video/podcast/flashcards/slides/infographic), _item_keyboard показує всі формати + TTS разом, hub оновлено з TTS міткою, podcasts_state.json доповнено темами 9/12/13

## Наступний крок
NbLM rate limiting черга (пункт 3), прибрати превью в /cur картках

## Контекст
NOTEBOOKLM_FORMATS в shared/curriculum_engine.py, hub.py читає podcasts_state.json для TTS мітки
