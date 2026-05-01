---
project: sam
updated: 2026-05-01
---

# HOT — Sam

## Now

**Фаза Б: Підготовка до реалізації core/content_gen/ пакету з brief.py (Haiku pre-analysis)**

Фаза А NBLM deep-dive успішно завершена та протестована. `--format deep-dive --length default` інтегровано у pipeline, звук явно кращий. Тепер готуємося до Фази Б: створення backend-agnostic архітектури для інструкцій через Haiku brief-аналіз. Topic.content_style = Literal["audio", "visual"] визначена як просто тег, реальні інструкції генеруватимуться через brief.py.

## Last done

**Сесія 01.05 — Фаза А NBLM рефакторингу ЗАВЕРШЕНА**

- Успішно додано `--format deep-dive --length default` параметри у `notebooklm_module.py`
- Тестування на `agent_architecture-1` теми показало помітно більшу глибину (~9.5 хв регенерація)
- Підтверджено: Topic.content_style = Literal["audio", "visual"] — це тільки тег, НЕ місце для інструкцій
- Визначено архітектуру Фази Б: brief.py (Haiku reads Topic/Article) → instruction set → backends-ам
- 4 файли модифіковано: core/notebooklm_module.py, curriculum/pipeline.py, modules/notebooklm.py, modules/article.py
- Готово до push і merge в main

## Next

1. **Фаза Б — core/content_gen пакет (Priority)**
   - Створити `core/content_gen/` пакет з `brief.py` модулем
   - Реалізувати Haiku brief-генерацію: читає Topic/Article контекст → генерує 1-2 рядка instruction set
   - Backend-agnostic adapter API: brief + контент → кожному backend-у
   - Мінімум 3 instruction-варіанти: audio, visual, quiz (або динамічна генерація?)
   - Структура: `core/content_gen/brief.py` (генерація) + `core/backends/` дерево (audio/, visual/, quiz/, tts/, flashcards/)
2. **Мігрувати article + topic pipeline** на brief-driven instruction generation
3. **Smoke-test на 2-3 темах** — верифікувати стабільність глибини та якості
4. **Паралельно**: article dispatcher fix у pinned.py, article_del BotCommand додати
5. **Опціонально**: stale task_id recovery fallback при 5+ timeout-ів (нижче в Blockers)

## Blockers

- **stale task_id fallback не реалізовано**: video артефакт готовий у NBLM UI, але CLI `artifact wait` повертає `timeout` на 5+ поспіль. Fallback: `artifact list` → match by format → URL patch. Потребує реалізації у `_wait_for_artifact()` або окремому recovery механізмі (не критична для Фази Б, можна відкласти).

## Active branches

- **sam-репо (`main`)** — f29c0a8 запушено. Фаза А 100% завершена, готова до Фази Б.

## Open questions

- **brief.py design**: Скільки instruction-варіантів генерувати? Мінімум 3 (audio, visual, quiz) чи динамічна генерація на основі Topic.formats/Article.formats?
- **Backend-agnostic spec**: Чи кожен backend отримує brief як plain text, чи JSON структурований?
- **Brief cache**: Зберігати brief у Topic.formats[key].brief, Article.formats[key].brief чи регенерувати щоразу?
- **Haiku API quota**: Скільки Haiku-запитів на день? Яка fallback логіка при rate-limit?
- **Article deep-link dispatcher**: Потребує реалізації у `_handle_deep_link()` для pinned deep-links (article_X).

## Reminders

- **Deep-dive + default length** — стабільне через notebooklm_module, article-pipeline теж отримав ці параметри.
- **Topic.content_style = Literal["audio", "visual"]** — просто тег, інструкції генеруються у Фазі Б через brief.py.
- **RSS pipeline stable** — Pocket Casts готовий на `/feed.xml`, orphan sync працює, hook non-fatal.
- **Lazy re-attach верифікована** — articles/topics при рестарті re-attach задачі автоматично через `post_init` scan.
- **Article dispatcher** — потребує реалізації у `_handle_deep_link` для deep-links типу article_X (потім smoke-test).
- **BotCommand list** — article, article_del потребують додавання у set_my_commands.
