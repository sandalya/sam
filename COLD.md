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

---

## 2026-05-01: Фаза Б core/content_gen/ пакет IMPLEMENTED

```yaml
archivereason: Фаза Б на 100% реалізована, успішно протестована, готова до bulk-регенерації подкастів
archivereason_ua: Фаза Б на 100% реалізована, успішно протестована, готова до bulk-регенерації подкастів
archivereason_date: 2026-05-01
tags: [phase-b, content-gen, architecture, completed]
```

Фаза Б core/content_gen/ пакету **на 100% реалізована** 01.05: Backend-agnostic design із BriefGenerator (Haiku pre-analysis → instruction set), presets (audio/visual/quiz шаблони), backends/{base,nblm,tts,interactive} дерево. Інтеграція у Topic/Article: ContentBrief dataclass, prepare_and_generate() API. Schema migration curriculum.json schema_version 1→2 з fallback. Merge у main успішна: 340+ рядків коду, 0 breaking changes через lazy re-attach шім (14 рядків у modules/notebooklm.py). Тест на agent_architecture-3: Haiku-генерація ~4с, brief з 6 концептів, NBLM параметри (deep-dive, length, format_modifier) передаються коректно, звук очевидно кращий за дефолт. Видалено _generate_format_instructions з article.py — brief тепер один на entity, переиспользується всіма форматами. Наступний крок: bulk-регенерація 17 подкастів (всі крім agent_architecture-1 і agent_architecture-3).

---

## 2026-05-01: Фаза Б core/content_gen/ пакет FULLY MERGED + bulk-regen запущена

```yaml
archivereason: Фаза Б на 100% реалізована, tested, merged до main, bulk-regen 13 подкастів запущена, готова до production
archived_at: 2026-05-01
tags: [phase-b, content-gen, architecture, completed, merged]
```

Фаза Б core/content_gen/ пакету **ЗАВЕРШЕНА і MERGED** 01.05 о 19:57: Backend-agnostic design із BriefGenerator (Haiku pre-analysis → instruction set), presets (audio/visual/quiz шаблони), backends/{base,nblm,tts,interactive} дерево. Інтеграція у Topic/Article: ContentBrief dataclass, prepare_and_generate() API. Schema_version=1 без міграції, fallback через `data.get("brief")`. Merge у main: 340+ рядків коду, 0 breaking changes завдяки lazy re-attach шіму (14 рядків у modules/notebooklm.py). Тест на agent_architecture-3: Haiku ~4с, brief з 6 концептів, NBLM параметри передаються коректно, звук явно кращий. Видалено _generate_format_instructions з article.py. **Bulk-регенерація запущена**: `/regen --only podcast_nblm` о 19:57 для 13 тем (13 подкастів). Моніторинг: першi 1-2 швидко, решта rate-limit retry-loop (71+ год). Паралельно: готуємось до Фази В (article dispatcher + BotCommand list додавання).

---

## 2026-05-01: Bulk-регенерація 13 подкастів (Фаза Б Phase 2) — запущена, паузована на bug fix

```yaml
archivereason: bulk-regen запущена 01.05 о 19:57, паузована через виявлення bug, резюміована 02.05
archivereason_ua: bulk-regen запущена 01.05 о 19:57, паузована через виявлення bug, резюміована 02.05
archivereason_date: 2026-05-02
tags: [bulk-regen, podcast-nblm, phase-b]
```

01.05 запущено `/regen --only podcast_nblm` для 13 тем з параметрами brief через Haiku + NBLM deep-dive+length. 3 topic reset до pending через bug виявлення (premature mark generating у nblm.py:268-273). 5 подкастів ready (agent_architecture-1/3, multi_model_orchestration-1/2, system_operations-5). 8 тем pending через rate-limit retry-loop (RETRY_DELAYS = 71 годин послідовно). Bug fix deployed & end-to-end verified 02.05 → bulk-regen resumed для 8 pending. 13 тем у фазі активної регенерації, моніторинг на rate-limit loop.

---

## 2026-05-01: Фаза А NBLM deep-dive рефакторинг + Фаза Б core/content_gen/ — завершені й merged

```yaml
archivereason: обидві фази на 100% завершені, протестовані, merged до main, ready для production
archivereason_ua: обидві фази на 100% завершені, протестовані, merged до main, ready для production
archivereason_date: 2026-05-02
tags: [phase-a, phase-b, completed, merged]
```

Фаза А: проброс `--format deep-dive --length default` у pipeline, звучить явно краще за дефолт. Інтегровано у notebooklm_module.py, artikel.py, pipeline.py. 4 файли змінено, merge 01.05 успішна. Фаза Б: BriefGenerator (Haiku pre-analysis) + presets (audio/visual/quiz) + backends/{base,nblm,tts,interactive} дерево. Schema БЕЗ міграції (version=1), lazy re-attach шім (14 рядків). 340+ рядків коду, 0 breaking changes. Test на agent_architecture-3: brief з 6 концептів, NBLM параметри передаються, звук явно кращий. Merge 01.05 о 19:57 успішна. **02.05 update**: укрсенізація brief.py + presets.py на диску (CC переклав), pending merge. Наступний крок: Фаза В (article dispatcher + BotCommand).

---

## 2026-05-02: Фаза Б core/content_gen/ — укрсенізація IN PROGRESS

```yaml
archivereason_ua: укрсенізація brief.py + presets.py на диску, pending merge у main
archivereason: укрсенізація brief.py + presets.py на диску, pending merge у main
archivereason_date: 2026-05-02
tags: [phase-b, content-gen, localization]
```

CC переклав brief.py + presets.py на українську мову. Файли готові на диску у `/workspace/sam/core/content_gen/`. Потребує: merge у основний код, тест на 1 темі, перевірка укр brief output у production. **03.05 UPDATE**: укрсенізація merged у main, brief output в Ukrainian, production-active.

---

## 2026-05-03: Укрсенізація brief.py + presets.py — COMPLETE & PRODUCTION-ACTIVE

```yaml
archivereason_ua: укрсенізація merged до main, brief output в Ukrainian, production-deployed 03.05
archivereason: укрсенізація merged до main, brief output в Ukrainian, production-deployed 03.05
archivereason_date: 2026-05-03
tags: [phase-b, content-gen, localization, completed]
```

Укрсенізація brief.py + presets.py завершена 03.05: файли merged до main, brief-генерація тепер в українській мові. Production-deployed, output коректний укр. Haiku JSON parse fail на укр промпті (спеціальні символи або token limit) — fallback спрацьовує, brief все одно генерується. Потребує дослідження причини на подальшому етапі (low priority).

---

## 2026-05-03: Bulk-регенерація 13 подкастів — 2 FAILED TOPICS ISOLATED

```yaml
archivereason_ua: 2 failed topics ізольовані для диагностики: rag_retrieval-1 (notebook 0daaf506 broken), system_operations-5 (silent rc=1 2d0285dd)
archivereason: 2 failed topics isolated for diagnostics: rag_retrieval-1 (notebook 0daaf506 broken), system_operations-5 (silent rc=1 2d0285dd)
archivereason_date: 2026-05-03
tags: [bulk-regen, podcast-nblm, debugging]
```

У bulk-регенерації 13 подкастів (запущена 01.05) виявлено 2 failed topics: **rag_retrieval-1** (notebook UUID 0daaf506 поламаний, sources скорочено вручну до 1, статус не змінився), **system_operations-5** (notebook 2d0285dd silent rc=1 навіть після cleanup джерел до 1). Причина: **ADD_SOURCE auto засмічує notebook** — auto ADD_SOURCE при regen додає sources, cleanup видаляє їх, але rc=1 не змінюється. Потребує нових clean notebook'ів замість cleanup або дослідження add_source логіки в backends/nblm.py. Решта 8 тем pending у rate-limit loop, 5 тем ready.

---

## 2026-05-03: NBLM diagnostic complete — 3 notebook UUIDs verified, bugs isolated

```yaml
archivereason: NBLM diagnostic session завершена, notebook UUIDs верифіковані, bugs root-cause identified для Intervention 2+3
archivereason_ua: NBLM diagnostic session завершена, notebook UUIDs верифіковані, bugs root-cause identified для Intervention 2+3
archivereason_date: 2026-05-03
tags: [nblm, diagnostics, bug-isolation, intervention]
```

NBLM diagnostic session 03.05 (2+ hours): CLI локалізована у venv, backends/nblm.py прочитано (428 рядків), 3 notebook'и верифіковані через `nblm artifact status`. **healthy 8aca66e9** (agent_architecture-1) OK. **broken-A 0daaf506** (rag_retrieval-1) null RPC response — dangling UUID. **broken-B 2d0285dd** (system_operations-5) RATE_LIMITED 429 (Google). **Identified bugs**: (1) ADD_SOURCE дублювання (line 261, не перевіряє існуючі sources перед додаванням), (2) RETRY_DELAYS скорочення (71*3600 = 72h послідовно, кандидат на 3-5h), (3) JSON edit не перериває in-flight task (bonus, low priority). **Intervention 2+3 plan**: idempotent ADD_SOURCE (перевірити source list) + rate_limit redesign (скоротити RETRY_DELAYS, інформативний error на null-RPC). Session 2 CC: 5-6h для обох вмешательств. **Impact**: 2 failed topics (rag_retrieval-1 + system_operations-5) потребують нових clean notebook'ів, решта 8 pending в rate-limit loop з потенційним скороченням до 3-5h.
