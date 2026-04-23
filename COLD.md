---
project: sam
started: 2026-04-19
---

# COLD — Sam

Історія проекту. Append-only. Не редагувати старі записи.

---

## 2026-04-19: Ініціалізація триярусної пам'яті

Перехід з одного `SESSION.md` на `HOT.md` + `WARM.md` + `COLD.md`. Раніше весь контекст жив у SESSION.md — і поточний крок, і архітектура, і історія. Читалось 500+ рядків на старті кожної сесії, 70% нерелевантно. Новий підхід: HOT (переписується), WARM (інкрементально), COLD (append-only, читається за запитом).

Команда чекпоінту: `chkp2 sam ...` (окрема від старої `chkp`, поки експеримент тільки на Sam).

---

## Sam v1 архітектура (до Phase 0 маніфесту)

```yaml
archived_at: 2026-04-19
reason: v2 рефакторинг завершив data-model і engine-free перехід
tags: [legacy, architecture]
```

Старий Sam мав:
- Monolithic `shared/curriculum_engine.py` з класом `SamCurriculum`, `_instance_cache`, shim-делегаціями.
- Activity tracking + artifact consumed tracking змішано у `data/learning_state.json.topics` — один файл на все.
- `modules/curriculum.py` мав декілька команд курікулома з прямими викликами engine.
- `main.py` імпортував `DATA_DIR` через engine (обхідний шлях).

Причини переходу на v2:
- Curriculum data і activity data мали різні життєві цикли, але лежали разом → конфлікти і складні міграції.
- Engine розрісся, shim-делегації робили код нечитабельним.
- Sam і Garcia обидва тягнули engine, але з різними потребами → Garcia зробилась тягарем для Sam.

## Міграція: Sam engine-free

```yaml
archived_at: 2026-04-19
reason: завершено у Phase 1
tags: [migration, refactor]
```

Видалено `shared/curriculum_engine.py` (бекап `.bak-phase29` залишено у shared/ на всяк випадок — можна прибрати пізніше). `modules/curriculum.py` скорочено до двох команд. `main.py` отримує `DATA_DIR` напряму з `modules/base.py`. Sam більше не імпортує engine.

## Garcia як deprecated у контексті Sam

```yaml
archived_at: 2026-04-19
reason: Garcia пішла в свій рефакторинг (beauty assistant для Ксю), більше не ділить код з Sam
tags: [garcia, separation]
```

`shared/curriculum_engine.py` і `hub_renderer.py` існували частково заради Garcia. Після рішення що Garcia — окремий проект з власним piece of Sam architecture (форк), ці файли стали непотрібні для Sam. `notebooklm_module.py` і `podcast_module.py` лишились — Sam-only, без Garcia-залежностей.

---

## Формат записів

Новий запис у COLD:
- Дата заголовком (`## YYYY-MM-DD: Назва`).
- YAML з `archived_at`, `reason`, `tags`.
- Опис ~3-10 рядків: що було, чому змінилось.
- Якщо блок переноситься з WARM — вставити його як є, додати frontmatter з `archived_at`.

---

## 2026-04-23: chkp3 yaml-registry міграція

```yaml
archivereason: завершено, готово до масштабування на інші проекти
tags: [infrastructure, chkp3, tools]
archived_at: 2026-04-23
```

Міграція chkp3 скрипта з хардкоду на `kit/projects.yaml` реєстр. Причина: підготовка до масштабування на Meggy, Ed, Garcia, Abby-v2 — замість дублювання логіки в кожному проекті. Додана команда `--init` для ініціалізації триярусної пам'яті нових проектів (scaffold HOT.md, WARM.md, COLD.md з базовим template). Тестування на Sam успішне, готова до развертування на 4+ проектах.
