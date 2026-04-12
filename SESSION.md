# SESSION — 2026-04-12 18:50

## Проект
sam

## Що зробили
Додали кнопку 🎙️ Подкаст у /cur → картка теми. Адаптивна довжина: short (~8-12 хв) якщо тема мала, deep (~15-20 хв) якщо велика (за розміром why+do+title). _generate_podcast_for_item в curriculum_engine.py запускає через asyncio.create_task.

## Наступний крок
Наступне: протестувати NbLM відео після reset квоти. Потім shared/notebooklm.py для Гарсіа.

## Контекст
podcast_module.py: _adaptive_format(item). ENGINE: cur_podcast callback + _generate_podcast_for_item метод. Кнопка поряд з NbLM.
