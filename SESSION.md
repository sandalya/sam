# SESSION — 2026-04-11 22:24

## Проект
sam

## Що зробили
Додали podcast модуль (OpenAI TTS onyx, 10-15/20-25 хв, /podcast [N] [deep]). Динамічний curriculum (_get_full_curriculum, _generate_dynamic_topics, id>=100 ✨). Пасивний аналіз інтересів з розмов (update_interests в base.py). save_profile в BaseModule.

## Наступний крок
Мульти-вибір форматів у /cur + /notebooks команда. Тест NbLM відео після reset квоти.

## Контекст
Динамічні теми генеруються коли є interests в profile.json. Інтереси накопичуються автоматично з handle_text через _extract_interests.
