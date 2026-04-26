Проект: sam

Поточний стан: Phase 6.2 (Article pipeline) виявив критичний баг — NBLM CLI `--wait` таймаут 300s недостатній для slides (займають 5-10 хвилин). При фейлі через годину ретрай створює дублікати артефактів на Google Drive. Дефинітивне рішення готове: замінити синхронний `--wait` на асинхронне `--no-wait --json` + `artifact wait <task_id> --timeout 1800`.

Что робити: NBLM async polling refactor у генераторі articles (slides, podcast_nblm, infographic, video). Розширити Article dataclass для task_ids, telemetry для status-переходів, artifact dedup перед retry. Потім smoke test всіх 5 форматів.

Блокери: async polling критична для production article pipeline.

Преді почати — прочитай HOT.md та WARM.md (в `/workspace/sam/`).