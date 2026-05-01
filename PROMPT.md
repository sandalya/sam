Проект: sam

**Стан**: Фаза А NBLM deep-dive успішно завершена 01.05 (--format deep-dive звучить явно краще). Готуємось до Фази Б: core/content_gen/ пакет з brief.py (Haiku pre-analysis для інструкцій). Topic.content_style = Literal[audio|visual] — просто тег, реальні інструкції генеруватимуться через backend-agnostic brief.

**Наступний крок**: Фаза Б — реалізувати brief.py модуль: Haiku читає Topic/Article контекст → 1-2 рядка instruction set → backends-ам (audio, visual, quiz). Паралельно: article deep-link dispatcher у pinned.py (потребує для smoke-test), article_del BotCommand додати.

**Blockers**: stale task_id fallback (timeout × 5 → artifact list recovery) — потребує реалізації але не критична для Фази Б.

Скинь HOT.md + WARM.md, готові почати Фазу Б.