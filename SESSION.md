# SESSION — 2026-04-11 21:12

## Проект
sam

## Що зробили
Інтеграція NotebookLM: автоматична генерація відео/подкасту через notebooklm-py. Новий модуль modules/notebooklm.py — створює notebook на тему, додає джерело, генерує контент з --wait, надсилає посилання в TG коли готово.

## Наступний крок
Зробити зручний перегляд notebooks з Telegram (/notebooks або кнопка в /cur)

## Контекст
Cookies в ~/.notebooklm/storage_state.json. Notebook IDs зберігаються в data/notebooklm_notebooks.json
