---
project: sam
updated: 2026-04-26
---

# HOT — Sam

## Now

**Phase 6.2 — NBLM async polling refactor.** Article pipeline live з мульти-чекбоксами, інтерактивною чергою, рендером у pinned. Smoke test виявив критичний баг: NbLM CLI `--wait` має 300s таймаут, slides беруть 5-10 хвилин, CLI рапортує failed. Ретрай через годину створює дублікати артефактів на стороні Google (3 slide deck для article_6a578102). Архітектурне рішення готове: `generate --no-wait --json` → task_id миттєво, потім окремо `artifact wait <task_id> --timeout 1800` асинхронно.

## Last done

**Сесія 26.04 — Article pipeline smoke test → NBLM async polling diagnosis**

- **Article URL pipeline завершено** — `/article <URL>` → fetch → Claude аналіз → 5 форматів (slides, podcast_nblm, infographic, flashcards, video) з чекбоксами ✨recommended/🚀Згенерувати. Стан у `state.articles` dataclass, мутації: `add_article`/`remove_article`/`set_article_format_status`/`set_article_nblm_notebook_id`.
- **Sequential queue** — статті генеруються послідовно по форматах (не паралельно), видимість у pinned '📑 Статті (N)' після mastered.
- **Повна команда-набір** — `/article <URL>` додає стаття, `/article_del <shortid>` видаляє, чекбокси для формат-вибору + кнопка генерування.
- **Smoke test → критичний баг виявлено** — NbLM CLI `generate --wait` таймаут 300s недостатній для slides (займають 5-10 хвилин). При фейлі ретрай через годину не перевіряє чи слайди вже існують → дублікати на стороні Google (3 slide deck для article_6a578102).
- **NBLM async polling архітектура діагностована** — CLI має `generate <type> --no-wait --json` (повертає task_id миттєво) + окремо `artifact wait <task_id> --timeout 1800` (асинхронне опитування). Це правильний шлях замість синхронного `--wait`.
- **Ручний救援 article_6a578102** — вручну виправлено slides=ready з URL у curriculum.json, дублікати залишились у Google Drive (вимагає cleanup).

## Next

1. **NBLM async polling refactor (PRIORITY)** — замінити синхронний `--wait` на `--no-wait` + асинхронне `artifact wait <task_id> --timeout 1800`. Охоп: генератор артефактів (slides, podcast_nblm, infographic, video) для articles + articles mutations повинні писати task_id у стан. Телеметрія: лог коли task переходить у ready.
2. **Artifact dedup (вторинна)** — перед retry для article-формату перевіряти чи артефакт вже існує на стороні Google за notebook_id, уникаючи дублікатів.
3. **Smoke test article pipeline повторний** — запустити генерацію всіх 5 форматів для реальної статті, перевірити що слайди генеруються без зависання, нема дублікатів, артефакти міцно лежать у Google.

## Blockers

- **NBLM async polling** — критичний для article pipeline. Блокує production-розгортання статей без ручного втручання.

## Active branches

- **sam-репо (`main`)** — чистий, готів до комітів async polling refactor.
- **ed-репо (`main`)** — синхронізований, MessageEdited listener для FSM (eb0c26e від 24.04).

## Open questions

- Яка оптимальна timeout для `artifact wait`? 1800s (30 хв) достатня для всіх форматів (podcast_nblm, infographic, video, slides)?
- Чи потрібна retry-логіка після `artifact wait timeout`? (e.g., якщо задача виконується дуже довго, 30+ хвилин)
- Як тримати task_id у Article dataclass? Нове поле `task_ids: dict[str, str]` = {format: task_id}?
- Чи прибрати дублікати з Google Drive вручну, чи автоматично при cleanup?

## Reminders

- **NbLM async polling правильний архітектурний шлях** — `generate --no-wait --json` + `artifact wait` асинхронно. НЕ використовувати `--wait` у майбутніх генераторах.
- **Article dataclass розширення** — додати поле для task_ids або nested ArticleFormat структури з task_id.
- **Pinned rendering** — слід оновлювати при переході format-статусу з pending→processing→ready (телеметрія важлива для користувача).
- **Дублікати article_6a578102** — на Google Drive залишились 3 slide deck, потрібен cleanup або ignore (не блокує фаз, но гігієна важна).