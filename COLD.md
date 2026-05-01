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

## 2026-04-23: chkp yaml-registry міграція

```yaml
archivereason: завершено, готово до масштабування на інші проекти
tags: [infrastructure, chkp, tools]
archived_at: 2026-04-23
```

Міграція chkp скрипта з хардкоду на `meta/chkp/projects.yaml` реєстр. Причина: підготовка до масштабування на Meggy, Ed, Garcia, Abby-v2 — замість дублювання логіки в кожному проекті. Додана команда `--init` для ініціалізації триярусної пам'яті нових проектів (scaffold HOT.md, WARM.md, COLD.md з базовим template). Тестування на Sam успішне, готова до развертування на 4+ проектах.

---

## 2026-04-27: Lazy re-attach верифікація + stale task_id баг

```yaml
archivereason: завершено lazy re-attach верифікацію; виявлено nblm async polling issue
archived_at: 2026-04-27
tags: [nblm, async, lazy-reattach, bug]
```

**Lazy re-attach верифіковано на проді** (commit b39bfaf): рестарт 18:54 з active task 7af67aad (video для article_6a578102) → `post_init` скан curriculum.json → `Lazy re-attach: scheduling 1 orphaned task(s)` → Phase 2 wait loop запущено. Task re-attach та phase-skip логіка працюють коректно.

**HOT memory drifts очищені**:
1. «article pipeline critical bug» (вигадана проблема) — workflow працює як задумано (opt-in via 🚀, не auto-pipeline).
2. «lazy re-attach вбудована» — до сьогодні була тільки теорія; тепер справді вбудовано з `post_init` scan.

**Stale task_id баг виявлено (новий, критичний)**: video артефакт готовий у NBLM UI (~21h тому), але CLI `artifact wait <task_id>` повертає `status=timeout` замість `completed`. Task_id видається розпадається через ~24h в NBLM API, навіть коли артефакт реально готовий. Симптом: 5+ поспіль `Wait <task_id>: status=timeout` без жодного `completed/failed` між ними. Fallback-рішення: при N timeout-ів поспіль → `artifact list -n <notebook_id>` → match по формату → витягнути URL → patch JSON. Потребує реалізації в `_wait_for_artifact()` або окремому recovery механізмі.

---

## 2026-04-30: RSS Feed pipeline COMPLETE + Pocket Casts + orphan sync

```yaml
archivereason: завершено фазу RSS + podcast distribution, stable в production
archived_at: 2026-04-30
tags: [rss, podcast, feed, phase-complete]
```

РСС pipeline завершено і активно. 8 items у feed: 5 curriculum (4 topics + 1 article) + 3 bonus orphan (Bash Mastery for Pi5, Software Engineering Horizons, INFRA Pi5 vs Mac Mini). Сервер на `100.86.239.46:8765` з systemd `sam-rss.service` (bind, Accept-Ranges, /healthz, /feed.xml, /audio/{file}). Orphan sync через `nblm_orphan_sync.py` (dedup по title, keep newest). Hook у `notebooklm_module.py` після `save()` — регенерує feed при готових podcast_nblm. Pocket Casts готовий до додавання по URL `http://100.86.239.46:8765/feed.xml`. Ed: `skip_judge: true` детерміністичні кейси, блоки 20/21/22 PASS ($0 cost). Priority: Phase 4 ручний тест Pocket Casts + stale task_id recovery fallback.

---

## 2026-05-01: Фаза А NBLM deep-dive рефакторинг ЗАВЕРШЕНА

```yaml
archivereason: фаза 100% завершена, тестована на проді, готова до наступної фази
archived_at: 2026-05-01
tags: [nblm, phase-a, quality, refactor]
```

Фаза А NBLM рефакторингу **успішно завершена** 01.05. Проброс `--format deep-dive --length default` у pipeline через notebooklm_module — тестована на `agent_architecture-1` теми (~9.5 хв регенерація). Результат явно кращий за попередній дефолт: звучить деталізовано, глибоко, близько до результатів преміум-сервісів. Інтеграція у код проста: додано two-line параметри у notebooklm_module.py, Topic.content_style = Literal["audio", "visual"] визначена як тег (не місце для інструкцій). Pipeline, modules/ (article.py, nblm.py), backend-інтеграція успішні. Подальше: Фаза Б (brief.py + Haiku pre-analysis для реальних інструкцій, backend-agnostic architecture).
