Проект: sam

Стан: Фаза А NBLM deep-dive завершена (--format deep-dive --length default інтегровано, тестовано на agent_architecture-1). Готуємось до Фази Б: backend-agnostic архітектура через brief.py + Haiku pre-analysis для реальних інструкцій. Topic.content_style = тег, інструкції генеруються динамічно.

Наступне: (1) Smoke-test Фази А — Sam стартує, regen agent_architecture-1 --only podcast_nblm, порівняти зі старим notebook, push якщо OK; (2) Дизайн Фази Б — визначити instruction-варіанти (3 hardcoded vs динамічні?), backend spec (plain text vs JSON), brief cache; (3) Article dispatcher у pinned.py для deep-links article_X.

Блокери: stale task_id fallback (можна відкласти), article dispatcher (PRIORITY).

Скинь HOT.md + WARM.md для контексту, почнемо з планування Фази Б.