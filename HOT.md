---
project: sam
updated: 2026-05-03
---

# HOT — Sam

## Now

**Session 03.05: End-to-end podcast regen, 16/18 themes ready, 2 failed isolation in progress**

Укрсенізація brief.py + presets.py активована end-to-end (deepdive angle у NBLM args). Булк-регенерація 13 подкастів розпочата 01.05, 5 тем ready (agent_architecture-1/3, multi_model_orchestration-1/2, system_operations-5), 8 pending через rate-limit. Знайдено: 2 тем із silent rc=1 (rag_retrieval-1 з broken notebook UUID 0daaf506, system_operations-5 з rc=1 навіть після cleanup sources до 1). Хід: прямий виклик на проблемні notebook через NBLM CLI для ізоляції Sam-bug vs NBLM-bug.

## Last done

**Session 03.05 (09:00 UTC) — Укр-переклад activation + bug deep-dive**

- Активовано укр-переклад brief.py + presets.py end-to-end: `cp` англійських бекапів, merge укр вмісту в main-репо, тест на 1 темі (brief output в укр підтверджено).
- Підтверджено 16/18 podcast тем ready or pending (5 ready, 8 pending rate-limit, 1 orphan reset).
- **Root cause isolation для 2 failed тем**:
  - **rag_retrieval-1**: notebook UUID 0daaf506 поламаний (скорочено до 1 source вручну), повинен спробувати рости при retry чи reset.
  - **system_operations-5**: silent rc=1 у notebook 2d0285dd навіть після cleanup sources (видалено усі 6+ sources вручну, залишено 1) — поведінка не змінилась. Потребує прямого вилучення notebook id з NBLM CLI.
- Знайдено: Sam reuse-ить notebook через `nblm_notebook_id` (не notebook_id), auto ADD_SOURCE при regen засмічує notebook, silent rc=1 не пов'язаний з sources count.
- Знайдено: Haiku JSON parse fail на укр промпті (fallback brief спрацьовує), brief output коректний укр.

## Next

1. **Знайти NBLM CLI на Pi5 і прямо виконати з notebook 2d0285dd**
   - Пошук: `which generate`, `which artifact`, або посібник NBLM CLI локально.
   - Команда: `artifact status 2d0285dd` → дивитись чи notebook справді застряг у стані 'generating' чи є інша причина.
   - Альтернатива: перевірити `nblm.py` в проекті на наявність прямого API call для `notebook_id`.

2. **Прочитати add_source логіку в backends/nblm.py**
   - Чому auto ADD_SOURCE при regen засмічує notebook?
   - Куди додаються sources? Чи вони глобальні для notebook чи per-format?
   - Потенційне рішення: skipp ADD_SOURCE якщо notebook вже має > N sources, або видалити old sources перед ADD_SOURCE.

3. **Створити нові clean notebook'и для обох failed тем замість cleanup**
   - rag_retrieval-1: видалити старий 0daaf506, створити новий пустий notebook, reset topic до pending.
   - system_operations-5: видалити старий 2d0285dd, створити новий пустий notebook, reset topic до pending.
   - `/regen --only podcast_nblm` для обох тем.

4. **Полагодити укр-промпт brief.py що ламає Haiku JSON**
   - Чому укр промпт приводить до JSON parse fail? (Можливо special chars, або max-tokens limit).
   - Поточно fallback спрацьовує, але цілі: або скоротити промпт, або збільшити max_tokens, або додати JSON-strict режим для Haiku.

5. **Resume bulk-regen для 8 pending + 2 новостворених тем після fixes**
   - Чекати manual reset обох failed тем і чистих notebook'ів.
   - `/regen --only podcast_nblm` для всіх 10 (або 8 + 2) — rate-limit loop продовжиться, але с чистого аркуша для rag_retrieval-1 & system_operations-5.

## Blockers

- **NBLM CLI не знайдена на Pi5**: потребує локалізації або документації для `nblm.py` backend API.
- **system_operations-5 silent rc=1**: cleanup sources не впливає, потребує прямої перевірки notebook стану або переміщення на новий notebook.
- **Укр-промпт Haiku JSON parse**: fallback працює, але варто дослідити причину (special chars, token limit).

## Active branches

- **sam-репо (`main`)** — bug fix merged (premature mark generating видалено), укр-переклад merged, stable.
- **Production Pi5** — sam.service, sam-rss.service active, 14 items у feed, rate-limit loop для 8 подкастів.

## Open questions

- **Чи NBLM CLI є локально на Pi5, чи через API?** Потребує поиска або документації нблм бекенда.
- **Чому silent rc=1 для system_operations-5 навіть після cleanup?** Це баг в NBLM處理 або неправильне переміщення notebook id?
- **Укр-промпт Haiku JSON fail**: special chars? token limit? потребує профілювання.
- **Add_source auto-засмічення**: це критично або допустимо за новий notebook?

## Reminders

- **5 ready podcasts**: agent_architecture-1/3 (deep-dive, ~9.5 min), multi_model_orchestration-1/2, system_operations-5 (legacy).
- **8 pending podcasts**: production_reliability-5 (retry до ~03.05 19:26 очікувався вчора, можна reset), multi_model_orchestration-1/2, system_operations-2/3/4/5, rag_retrieval-1.
- **2 failed podcasts**: rag_retrieval-1 (UUID 0daaf506 broken), system_operations-5 (silent rc=1 2d0285dd) → потребують нових notebook'ів або прямої диагностики.
- **Укр-переклад активний**: brief.py + presets.py тепер у production, output in Ukrainian.
- **AntennaPod + RSS feed**: 14 items, активно працює.
- **Наступна фаза (В)**: article dispatcher + BotCommand додавання — поки паузована під час rate-limit loop.
