# SESSION — 2026-04-14 00:02

## Проект
sam

## Що зробили
Мігрували token tracking на shared/token_tracker.py (TokenTracker), /cost показує реальні витрати (-bash.42 за сесію), keyword pre-router працює, сумісність старого формату token_logger в get_stats()

## Наступний крок
Фаза 2 по Опусу: learning_state.json або /nbstatus команда

## Контекст
token_log.jsonl в shared/, старі записи мають cost_usd/cache_write — compat патч в token_tracker.py рядок ~125
