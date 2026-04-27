Проект: Sam

Сучасний стан: Phase 6.2 заблокована на критичному бузі article pipeline. NBLM async polling архітектура верифікована для topic-форматів (task_id повертаються, /status показує generating, 6 форматів), але articles не генеруються — формати залишаються пусто `formats={}` замість ініціалізації 5-ти форматів. Раніше бачили '⏳ Генерую 4 формат...' — зараз нічого. Dead-code `_generate_fmt_via_cli` видалено (commit 8eaa1c2, -35 рядків), чекає merge.

Что далі: Видалити dead-code, дефіксити article pipeline (чому формати не ініціалізуються в `add_article()` / чому `run_pipeline()` не викликається), smoke-тест article full-cycle з 3-4 форматів, верифіцити lazy re-attach явно при активному task_id.

Блокери: Article генерація не стартує. Lazy re-attach не верифіковано явно (був рестарт 7af67aad video).

Перед роботою: поділись HOT.md + WARM.md з /workspace/sam/.
