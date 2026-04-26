---
project: sam
updated: 2026-04-26
---

# HOT — Sam

## Now

**Phase 6.2 — NBLM async polling refactor (CRITICAL).** Верифіковано `/status` з новим async кодом: 6 topic-форматів у `generating` стані через `_start_generation()` (task_id повернений успішно, 0 failed). Аллокатор task_id в TopicFormat.task_id працює. Однак article auto-pipeline має баг: `/article` додає Article але `formats={}` остаються пустими, генерація не стартує (раніше бачили '⏳ Генерую 4 формат...').

## Last done

**Сесія 26.04 — Phase 6.2 NBLM async polling рефакт верифіковано + article pipeline баг**

- **TopicFormat.task_id поле добавлено** — Topic-формати тепер тримають task_id при запуску `_start_generation()`. Тест: прямий виклик повернув task_id успішно.
- **set_format_status оновлена** — приймає task_id параметр, записує у TopicFormat.task_id. Мутація працює.
- **_start_generation + _wait_for_artifact замість --wait** — замість синхронного `generate --wait` (300s таймаут), ділимо на: (1) `generate --no-wait --json` (повертає task_id миттєво), (2) окремий `artifact wait <task_id> --timeout 1800` асинхронно. Архітектура верифікована у коді.
- **Lazy re-attach логіка вбудована** — при перезавантаженні ботом, задачі з task_id можуть переприкріпитись до форматів без перегенерування.
- **/status показує articles з task_id** — Команда додала вивід task_id для кожного article-формату. Поточний стан видно.
- **Article pipeline баг виявлено** — `/article <URL>` додає Article об'єкт, але генерація не стартує. Формати створюються як `formats={}` (пусто), не як `formats={"slides": {"status": "pending", ...}}`. Раніше у smoke-test бачили фінальне повідомлення '⏳ Генерую 4 формат...', зараз його нема → генератор не запускається.
- **Ноутбук 87236f77** — використаний як тестовий під час smoke-test Phase 1+2, у нього є flashcards як побічний продукт тестування.
- **Dead-code _generate_fmt_via_cli** — знайдено у коді (Patch 3c), потребує видалення перед merge.

## Next

1. **Видалити dead-code _generate_fmt_via_cli (Patch 3c)** — очистити код перед merge async polling.
2. **Зафіксити article auto-pipeline — баг у форматах** — `/article <URL>` повинна створювати `formats={"slides": {"status": "pending", ...}, ...}` і запускати генерацію, як це було раніше. Розбір: (а) де формати не створюються, (б) чому генератор не запускається.
3. **Верифікація: article pipeline full-cycle** — запустити `/article <реальна URL>` з усіма 5 форматами, перевірити що `_start_generation` викликається, task_id записується у стан, `/status` показує задачі у `generating` стані.

## Blockers

- **Article pipeline генерація не стартує** — батіжить автоматичний запуск при `/article`, потребує дебагу. Перевірити: функція `add_article()` викликає `run_pipeline()` чи ні.

## Active branches

- **sam-репо (`main`)** — готов до комітів рефактора, dead-code очистка чекає.
- **ed-репо (`main`)** — синхронізований.

## Open questions

- Чому article-формати не створюються у add_article()? Код тягнув масив FORMAT_TYPES та створював пусту структуру раніше.
- Яка оптимальна timeout для `artifact wait`? Поточна 1800s (30 хв) достатня для всіх?
- Чи потрібна retry-логіка після `artifact wait timeout`?

## Reminders

- **NbLM async polling архітектура готова** — `generate --no-wait --json` + `artifact wait <task_id>` асинхронно. Це правильний шлях.
- **Article dataclass розширено** — TopicFormat.task_id поле вже в моделі.
- **Pi5 sam-сервіс активний** — готовий до тестування щоразу.
- **Dead-code очистка** — Patch 3c (`_generate_fmt_via_cli`) потребує видалення.