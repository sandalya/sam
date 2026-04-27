---
project: sam
updated: 2026-04-27
---

# HOT — Sam

## Now

**Phase 6.2 NBLM async polling — повністю закрита. Lazy re-attach верифіковано, видалено дві memory drifts, знайдено stale task_id баг.**

Осиротілий video task `7af67aad` для `article_6a578102` був успішно підхоплений `post_init` при рестарті 18:54, Phase 1 пропустилась, Phase 2 wait loop активний. Article workflow end-to-end робочий: `/article <URL>` → картка з 5 чекбоксами → юзер тисне 🚀 → черга → 4 формати у NBLM → 3/4 ready, video у `generating` але с невідпов stale task_id у NBLM CLI (видно по 5+ `timeout` поспіль).

## Last done

**Сесія 27.04 — реальний lazy re-attach + два HOT drift очищені + stale task_id найдено**

- **Lazy re-attach верифіковано на проді** (commit `b39bfaf`): рестарт 18:54 → `Lazy re-attach: scheduling 1 orphaned task(s)` → `Re-attach video for article_6a578102: task_id=7af67aad-...` → Phase 2 wait цикл запущено. Циклить `artifact wait` 5 разів за 2.5 год — все коректно.
- **HOT drift №1 очищено**: «article pipeline critical bug» — вигадана проблема. Workflow працює як задумано (opt-in через 🚀, не auto-pipeline).
- **HOT drift №2 очищено**: «lazy re-attach вбудована» — цього тижня справді вбудовано (до того тільки теорія).
- **Stale task_id баг знайдено (новий)**: video дотік у NBLM ~21h тому (ОК по UI), але CLI `artifact wait <task_id>` повертає `timeout` замість `completed`. Task_id розпадається через ~24h навіть якщо артефакт готовий. Видно по 5+ поспіль `timeout` без `completed` між ними.

## Next

1. **Stale task_id recovery** (PRIORITY) — реалізувати fallback: `_wait_for_artifact` при N timeout-ів поспіль → `artifact list -n <notebook_id>` → match формату → URL → patch JSON. Варіант: timeout × 5 → list → ready.
2. **Закрити поточний video** — або fallback у п.1, або руками (`artifact list` → URL → JSON patch).
3. **Three-tier migration** — Meg, Ed, Garcia, Abby-v2 на HOT/WARM/COLD (Sam, InSilver-v3 вже готові).
4. **`/nbstatus` break down** — формати, не просто кеш за notebook_id.
5. **Article.url cleanup** — уніфікувати source_url / url поле.

## Blockers

Немає.

## Active branches

- **sam-репо (`main`)** — `b39bfaf` запушено, готовий до наступного `chkp`.
- **ed-репо (`main`)** — синхронізовано.

## Open questions

- Скільки timeout-ів поспіль вважати stale? 5 (~2.5 год) чи 10 (~5 год)?
- Universal fallback (автоматичний) чи окрема команда `/recover_stale`?
- `Article.url` vs `source_url` — уніфікування на `url` або обидва?

## Reminders

- **Lazy re-attach тільки для in-flight tasks** (status=generating + task_id). Рестарт між Article creation і генерацією — нема що re-attach.
- **`set_format_status()` без task_id не зітре існуючий** — безпечно для re-attach.
- **Stale task_id видно по логах**: 5+ підряд `timeout`, жодного `completed/failed` між ними.
- **Pi5 active**, повний рестарт 18:54.
- **Article auto-pipeline НЕ існує** — opt-in by design (🚀 кнопка).
- **Phase 6.3 відкладена** — після 1-2 тижнів реального використання articles.