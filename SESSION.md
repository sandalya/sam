# SESSION — 2026-04-19 18:40

## Проект
sam

## Що зробили
Phase 2.2: cmd_cur_add + cmd_done переписані на v2 через shared.curriculum, 4/4 тести PASS

## Наступний крок
Phase 2.3: notebooks pipeline на v2 + merge nblm_notebook_id в curriculum_v2.json

## Контекст
cur_add робить LLM-enrich (ai визначає острів з існуючих або створює новий, заповнює why/read/do/estimate/content_style), додає тему одразу active. done приймає str id (agent_architecture-3) або legacy int (через legacy_id). Обидві команди викликають refresh_pinned silent. /cur показує 1/17 mastered, renderer v2 працює. Legacy CURRICULUM константа + _get/load_state shim лишаються — notebooklm.py і podcast.py ще на legacy. handle_curriculum_callback mертвий (не зареєстрований у main.py). Backup: curriculum.py.bak-phase22-20260419-*.
