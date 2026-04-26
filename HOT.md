---
project: sam
updated: 2026-04-26
---

# HOT — Sam

## Now

**Phase 6.2 prep — NBLM async polling fix.** Article pipeline live з мульти-чекбоксами, інтерактивною чергою, рендером у pinned. Smoke test виявив критичний баг: NbLM CLI `--wait` має 300s таймаут, slides беруть довше, CLI рапортує failed. Ретрай через годину створює дублікати артефактів на стороні Google (3 slide deck для article_6a578102). Рішення: `--no-wait` + `artifact wait <task_id> --timeout 1800` (асинхронне опитування замість синхронного блокування).

## Last done

**Сесія 26.04 — Article pipeline + NBLM async discovery**

- **Article URL pipeline завершено** — `/article <URL>` → fetch → Claude аналіз → 5 форматів (slides, podcast_nblm, infographic, flashcards, video) з чекбоксами ✨recommended/🚀Згенерувати. Стан у `state.articles` dataclass, mutations: `add_article`/`remove_article`/`set_article_format_status`/`set_article_nblm_notebook_id`.
- **Sequential queue** — článи генеруються послідовно по форматах (не паралельно), видимість у pinned '📑 Статті (N)' після mastered.
- **Повна команда-набір** — `/article <URL>` додає стаття, `/article_del <shortid>` видаляє, чекбокси для formato-вибору + кнопка генерування.
- **Smoke test → критичний баг** — NbLM CLI `--wait` таймаут 300s недостатній для slides (займають 5-10 хв). При фейлі ретрай через годину не перевіряє чи слайди вже існують → дублікати на стороні Google.
- **Root cause діагностика** — NbLM CLI має `generate <type> --no-wait --json` (повертає task_id миттєво) + окремо `artifact wait <task_id> --timeout 1800` (асинхронне опитування). Це правильний архітектурний шлях,현재 код використовує синхронний `--wait`.
- **Ручний救援** — article_6a578102 вручну виправлено (slides=ready з URL у curriculum.json), дублікати залишились у Google Drive.

## Next

1. **NBLM async polling refactor** — замінити синхронний `--wait` на `--no-wait` + асинхронне `artifact wait <task_id> --timeout 1800`. Мішень: генератор artikelів (slides, podcast_nblm, infographic, video) + телеметрія (лог коли task перейшла в ready).  
2. **Artifact dedup** — перед retry перевіряти чи артефакт вже існує на стороні Google за notebook_id, уникаючи дублікатів.
3. **Smoke test article pipeline** — перекинути всі 5 форматів для тестової статті (розташування вибрати сам Claude), перевірити що слайди не зависают і немає дублікатів.

## Blockers

- **NBLM async polling** — критичний для article pipeline. Блокує production-розгортання статей без ручного вторгнення.
- **Artifact dedup** — вторинний, але важливий для гігієни Google Drive.

## Active branches

- **sam-репо (`main`)** — чистий, готів до комітів.
- **ed-репо (`main`)** — синхронізований, MessageEdited listener для FSM (eb0c26e від 24.04).

## Open questions

- Яка оптимальна timeout для `artifact wait`? 1800s (30 хв) достатня для всіх форматів (podcast_nblm, infographic, video)?
- Чи потрібна retry-логіка після `artifact wait timeout`? (e.g., якщо задача виконується дуже довго)
- Як впахати дату/version артефактів на Google щоб детектувати дублікати?

## Reminders

- **Статі у pinned** — виглядають як '📑 Статті (3)' глибокий лінк, розширюються в список з чекбоксами.
- **NbLM CLI правильний шлях** — `--no-wait --json` + `artifact wait` асинхронно. НЕ використовувати `--wait` у майбутніх генераторах.
- **Article smoke test** — скористатися реальною статтею з інтернету (наприклад, про AI архітектуру, щоб рендер мав для чого генерувати).
