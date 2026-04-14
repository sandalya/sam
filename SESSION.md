# SESSION — 2026-04-14 19:13

## Проект
sam

## Що зробили
Оновлено _item_keyboard: всі 5 NbLM форматів + TTS в одному місці, уніфіковані іконки. Оновлено NOTEBOOKLM_FORMATS/FORMAT_NAMES. podcasts_state.json доповнено 9/12/13. NbLM rate limiting: RETRY_DELAYS [0,1560,3060], пауза 45с між форматами. hub.py оновлено з TTS міткою.

## Наступний крок
Рефакторинг /cur → об'єднаний cur+hub: список з посиланнями + генерація одним кліком + архівування тем

## Контекст
curriculum_engine.py: _curriculum_message потребує переписки на hub-стиль. /hub → аліас /cur після рефакторингу
