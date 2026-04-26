---
project: sam
updated: 2026-04-26
---

# HOT — Sam

## Now

**Phase 6.2 — NBLM async polling + Article pipeline FIX.** Верифіковано NBLM async архітектуру для topic-форматів (task_id, `/status` показує 6 генеруючих). Однак article pipeline має критичний баг: `/article <URL>` не генерує формати. Мета цієї сесії: видалити dead-code `_generate_fmt_via_cli`, дефіксити article генерацію.

## Last done

**Сесія 26.04 — NBLM async верифіковано, article pipeline баг ізольований**

- **NBLM async polling архітектура готова** — `generate --no-wait --json` + `artifact wait <task_id> --timeout 1800` верифіковано на 6 topic-форматах у `generating` стані.
- **TopicFormat.task_id поле працює** — мутація `set_format_status()` приймає task_id, записує успішно. `/status` показує стан.
- **Lazy re-attach логіка вбудована** — задачі можуть переприкріпитись без перегенерування при рестарті.
- **Dead-code `_generate_fmt_via_cli` знайдено** — commit 8eaa1c2 видалив 35 рядків, потребує merge.
- **Article pipeline баг ізольований** — `/article <URL>` додає Article але `formats={}` лишаються пусто. Генерація не запускається. Раніше фіналізував '⏳ Генерую 4 формат...' — зараз немає.
- **Дебаг спрямування**: проблема в (а) create Article без форматів, (б) `run_pipeline()` не викликається, (в) `_start_generation()` не срабатує для articles.
- **Smoke-тест видалено** — video генерація дотікає на task_id 7af67aad, lazy re-attach не верифіковано явно при активному task.

## Next

1. **Видалити dead-code `_generate_fmt_via_cli`** — Patch 3c, очистити перед merge async polling.
2. **Дефіксити article pipeline — формати не створюються** — розбір в `add_article()`: чому `Article.formats` залишається `{}` замість ініціалізації 5-ти форматів (slides, podcast_nblm, infographic, flashcards, video).
3. **Перевірити `run_pipeline()` call** — в `add_article()` чи в `cmd_article` що повинна запустити генерацію після додання статті.
4. **Smoke-тест article full-cycle** — запустити `/article <реальна URL>` з 3-4 форматами, перевірити task_ids у стані, `/status` показує `generating`.
5. **Верифіцити lazy re-attach явно** — перезавантажити бот з активним task_id (як 7af67aad video), перевірити що задача re-attach, а не перезапускається.

## Blockers

- **Article pipeline не генерує** — `/article <URL>` додає Article але генерація не стартує. Батіжить auto-pipeline при додаванні статті.
- **Lazy re-attach не верифіковано явно** — был рестарт при task_id 7af67aad video, потребує явного тесту.

## Active branches

- **sam-репо (`main`)** — готов до merge dead-code очистки і article fix.
- **ed-репо (`main`)** — синхронізований, не впливає на Sam.

## Open questions

- Чому `Article(id, url, title, content, formats={})` не ініціалізує `formats` як dict[str, ArticleFormat] з pending статусами?
- Яка функція має викликати `run_pipeline()` для articles — `add_article()` чи контроллер?
- Чи Article.url поле дублюється з content.source_url (у JSON)? Потребує чистити чи обидва мають сенс?
- Оптимальна timeout для `artifact wait` для articles — 1800s (30 хв) достатня для video?

## Reminders

- **NBLM async архітектура верифікована** — це правильний шлях для articles.
- **Dead-code очистка чекає** — Patch 3c видалити перед merge.
- **Article dataclass розширено** — task_id поле додано для articles (як для topics).
- **Pi5 sam-сервіс активний** — готовий до smoke-тестування.
- **Phase 6.3 відкладена** — після 1-2 тижнів реального використання articles, потім SR/export/Depth Mode.
