---
project: sam
updated: 2026-05-01
---

# HOT — Sam

## Now

**Фаза Б: Проектування架構 core/content_gen/ пакету (backend-agnostic design)**

Фаза А NBLM deep-dive завершена, протестована, готова до merge. Тепер готуємося до Фази Б: переведення інструкцій з Topic.content_style на backend-agnostic архітектуру з Haiku brief-аналізом. Архітектура: `core/content_gen/brief.py` читає контекст теми/статті, генерує instruction set через Haiku, передає backends-ам для інтерпретації. Кожен backend (audio, visual, quiz, TTS, flashcards) отримує brief + контент, сам вирішує як його використати.

## Last done

**Сесія 01.05 — Фаза А NBLM рефакторингу ЗАВЕРШЕНА + архітектура Фази Б дизайнована**

- Успішно добавлено `--format deep-dive --length default` у notebooklm_module, curriculum/pipeline, modules/notebooklm, modules/article.
- Тестування на `agent_architecture-1`: ~9.5 хв, звук явно деталізованіший за дефолт.
- Topic.content_style = Literal["audio", "visual"] — підтверджено як тег, НЕ місце для інструкцій.
- Дизайнована архітектура Фази Б: brief.py (Haiku pre-analysis) → instruction set → backends-ам.
- Визначені відкриті питання: 3+ instruction-варіанти (audio/visual/quiz чи динамічні?), backend spec (plain text vs JSON), brief cache, Haiku API quota/fallback.
- 4 файли модифіковано. Diff готовий до merge.

## Next

1. **Фаза Б — Очерк дизайну (цей тиждень)**
   - Визначити: мінімум instruction-варіанти (audio, visual, quiz →硬код) чи динамічна генерація на основі Topic.formats/Article.formats?
   - Backend spec: brief як plain text string чи JSON {"type": "audio", "instructions": "..."}?
   - Brief cache: зберігати у Topic/Article.formats[key] чи статичний дизайн — brief один раз на тему, шериться між всіма форматами?
   - Прототип: `core/content_gen/brief.py::BriefGenerator` клас із методом `generate_brief(topic: Topic, article: Optional[Article]) -> str`.
2. **Smoke-test Фази А (перед push)**
   - Sam стартує без помилок.
   - `regen agent_architecture-1 --only podcast_nblm` — щомісяцю тема, порівняти зі старим notebook 8aca66e9-b637-478f-be90-ab19bb6d2a72.
   - Якщо ОК → `git push`.
3. **Паралельно (можна робити одночасно)**
   - Article dispatcher у pinned.py: реалізувати `article_` handler у `_handle_deep_link()` (PRIORITY для smoke-тесту статей).
   - BotCommand list: додати article, article_del у set_my_commands.
   - stale task_id fallback (LOW, можна відкласти на послідуючу сесію).

## Blockers

- **stale task_id fallback не реалізовано**: video артефакт готовий у NBLM UI, але CLI `artifact wait` повертає `timeout`. Fallback: `artifact list` → match by format → URL patch. Можна відкласти, не блокує Фазу Б.

## Active branches

- **sam-репо (`main`)** — Фаза А готова, бранчу ще не пушено, очікується на smoke-test.

## Open questions

- **brief.py design**: Мінімум 3 instruction-варіанти (audio, visual, quiz) чи динамічна генерація на Topic.formats/Article.formats?
- **Backend spec**: Яка форма передачі brief-у: plain text string чи JSON структурований?
- **Brief cache**: Зберігати у Topic/Article.formats[key].brief чи один раз на тему, шериться статично?
- **Haiku API quota**: Скільки запитів на день? Fallback при rate-limit?
- **Article deep-link dispatcher**: Точна імплементація у pinned.py для article_X links.

## Reminders

- **Фаза А готова до merge** — diff у repo, не закомічено.
- **Deep-dive параметри** тепер у 4-х файлах — pipeline, notebooklm_module, modules/article, modules/notebooklm.
- **RSS feed stable** — orphan sync работает, hook non-fatal.
- **Lazy re-attach верифіковано** — articles/topics при рестарті re-attach через post_init.
- **Article dispatcher потребує** реалізації у _handle_deep_link() перед smoke-тестом статей.
- **BotCommand list** — article, article_del потребують додавання.
