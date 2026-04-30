---
project: sam
updated: 2026-04-30
---

# HOT — Sam

## Now

**RSS Feed pipeline (Фази 1-3 + bonus orphan) — done. sam-rss.service active.**

8 items у feed: 5 curriculum (4 topics + 1 article) + 3 bonus orphan (Bash Mastery for Pi5, Software Engineering Horizons, INFRA Pi5 vs Mac Mini). Сервер на `100.86.239.46:8765`. Hook у `notebooklm_module.py` авторегенерує feed після кожного ready podcast_nblm. Priority: Phase 4 Pocket Casts ручний тест + stale task_id recovery (з попередньої сесії).

## Last done

**Сесія 30.04 — RSS Feed pipeline**

- `core/audio_downloader.py` — idempotent download через NBLM CLI, `--no-clobber`
- `core/rss_feed.py` — RSS 2.0 + iTunes ns, curriculum items + orphan bonus з `[Bonus]` prefix
- `core/rss_server.py` — aiohttp на `100.86.239.46:8765`: /healthz, /feed.xml, /audio/{file} з Accept-Ranges
- `core/nblm_orphan_sync.py` — list → dedup by title → filter curriculum → artifact list → download → `orphan_meta.json`
- `sam-rss.service` — systemd, active + enabled
- Hook у `notebooklm_module.py` (5 рядків після save()) — non-fatal `asyncio.create_task(regenerate_feed_async())`
- Ed: `skip_judge: true` в `engine.py`; блоки 20/21/22 — 5 cases, всі PASS, $0.00

## Next

1. **Phase 4 Pocket Casts** — Add by URL → `http://100.86.239.46:8765/feed.xml` (Tailscale активний)
2. **Stale task_id recovery** (PRIORITY, з 27.04) — `_wait_for_artifact` fallback: N timeout → `artifact list` → match → patch JSON
3. **Закрити поточний video** `article_6a578102` — або fallback п.2, або руками
4. **`/dbg_nblm_sync`** при появі нових notebooks у NBLM — ре-синк orphan
5. **Three-tier migration** — Meg, Ed, Garcia, Abby-v2 на HOT/WARM/COLD

## Blockers

Немає.

## Active branches

- **sam-репо (`main`)** — `f29c0a8` запушено.
- **ed-репо (`main`)** — `skip_judge` додано в `engine.py`.

## Open questions

- Скільки timeout-ів поспіль вважати stale? 5 (~2.5 год) чи 10 (~5 год)?
- Universal fallback (автоматичний) чи окрема команда `/recover_stale`?

## Reminders

- **Lazy re-attach тільки для in-flight tasks** (status=generating + task_id).
- **`set_format_status()` без task_id не зітре існуючий** — безпечно для re-attach.
- **Stale task_id видно по логах**: 5+ підряд `timeout`, жодного `completed/failed` між ними.
- **Article auto-pipeline НЕ існує** — opt-in by design (🚀 кнопка).
- **RSS сервер окремий від Sam** — рестарт Sam не зупиняє sam-rss.service.
- **Orphan sync не автоматичний** — запускати `/dbg_nblm_sync` вручну після появи нових notebooks.
