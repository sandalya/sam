Проект: sam

**Поточний стан:** Фаза А NBLM рефакторингу — глобальний проброс `--format deep-dive --length default`. Верифіковано на `agent_architecture-1`. Перехід до Фази Б: `core/content_gen/` пакет з `brief.py` (Haiku pre-analysis) замість Topic.content_style інструкцій.

**Що далі:**
1. Створити `core/content_gen/brief.py` (Haiku → инструкции)
2. Перевести pipeline на новий API
3. Smoke-тест на 2-3 темах

**Контекст:** Topic.content_style — тег (audio/visual), інструкції через brief (Фаза Б). Backend-agnostic архітектура. RSS pipeline stable (Pocket Casts ready). Lazy re-attach + stale task_id fallback верифіковані.

Шкодлю HOT.md + WARM.md перед стартом.