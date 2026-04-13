# SESSION — 2026-04-13 23:36

## Проект
sam

## Що зробили
NbLM error handling: retry rate_limit+rc=1 (3 спроби 0/15/30хв), одне підсумкове повідомлення замість спаму, _md_escape для Markdown в _item_text

## Наступний крок
Повернути RETRY_DELAYS назад на [0, 1560, 3060] якщо ще тестові — перевірити grep

## Контекст
curriculum_engine.py: _run_all_formats збирає results dict і пише одне повідомлення. generate_fmt повертає (ok, err_type). Тестові затримки [0,10,10] можливо ще в engine
