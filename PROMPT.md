Проект: sam

**Стан**: Укрсенізація brief.py + presets.py активована (output in Ukrainian), 16/18 podcasts ready/pending (5 ready, 8 pending rate-limit, 2 failed isolated). Виявлено: ADD_SOURCE auto засмічує notebook, Haiku JSON parse fail на укр промпті (fallback спрацьовує). 

**Наступний крок**: (1) Знайти NBLM CLI на Pi5, прямо виконати на 2d0285dd для диагностики; (2) Прочитати add_source логіку в backends/nblm.py — чому засмічує notebook?; (3) Створити нові clean notebook'и для rag_retrieval-1 + system_operations-5 замість cleanup; (4) Полагодити укр-промпт brief.py що ламає Haiku JSON (special chars? token limit?).

**Блокери**: NBLM CLI не знайдена, system_operations-5 silent rc=1 незрозумілий.

**Поділи HOT.md + WARM.md при старті.**