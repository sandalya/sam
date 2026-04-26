Проект: Sam (AI-лічба-ментор, Telegram-бот).

Стан: Phase 6.2 NBLM async polling — архітектура верифікована для topic-форматів (task_id повертається, /status показує generating). Але article pipeline має баг: `/article <URL>` додає Article але формати не генеруються (раніше було '⏳ Генерую 4 формат...'). Dead-code `_generate_fmt_via_cli` чекає видалення (Patch 3c).

Что зробити: (1) дебаг article auto-pipeline — чому формати не ініціалізуються і генерація не стартує, (2) видалити dead-code, (3) верифікувати full-cycle: `/article <URL>` → формати створені → `/status` показує задачі у generating.

Блокери: article-генерація не запускається, потребує дебагу в `add_article()`.

Шарити: HOT.md + WARM.md на старті сесії.