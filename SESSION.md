# SESSION — 2026-04-14 21:45

## Проект
sam

## Що зробили
Рефакторинг /cur → hub стиль: артефакти в тексті меседжу, deep links ✨згенерувати/🔊послухати, спрощений item keyboard (тільки статуси), hub_renderer.py в shared/

## Наступний крок
NbLM адаптивна черга з backoff без помилок в чат

## Контекст
hub_renderer.py читає data_dir динамічно; /hub прибрано з routes; sam/modules/hub.py залишається як re-export
