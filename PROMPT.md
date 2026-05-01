Проект: Sam

Стан: Фаза Б core/content_gen/ пакету на 100% реалізована, успішно merged до main. Запущено bulk-регенерацію 13 подкастів через `/regen --only podcast_nblm` (очікується 24-72 год через rate-limit). Статус stable, чекаємо поки завершиться.

Наступні кроки:
1. Моніторити bulk-regen (перевіка: `python3 -c 'import json; d=json.load(open("data/curriculum.json")); print({s: sum(1 for t in d["topics"] if t.get("formats",{}).get("podcast_nblm",{}).get("status","missing")==s) for s in ["ready","pending","generating","failed"]})'`).
2. Паралельно: реалізувати article deep-link dispatcher у `_handle_deep_link()` (Фаза В PRIORITY).
3. Smoke-test звучання на 3-4 темах після bulk-завершення.

Блокери: Rate-limit loop на 13 подкастів. Низький пріоритет: stale task_id fallback, BotCommand додавання article/article_del.

Гот/Ворм/Колд прикріплені. Без них не починайте роботу!