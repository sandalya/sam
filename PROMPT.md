Проект: sam

Стан: Bug fix (premature 'mark generating' у nblm.py) end-to-end verified & deployed 02.05. 5 подкастів ready, 8 pending (rate-limit retry-loop до ~03.05 19:26). Фаза Б (brief.py + backend-agnostic) merged, укрсенізація brief.py + presets.py на диску (pending merge). AntennaPod feed: 14 items working.

Наступні кроки:
1. Активувати укр-переклад brief.py + presets.py (merge у основний код).
2. Reset production_reliability-5 (retry до 03.05 19:26) + `/regen --only podcast_nblm` для 8 pending тем (або чекати автоматичного retry).
3. Розглянути RETRY_DELAYS скорочення (72h → 24h) для швидшого retry.
4. Паралельно: Фаза В (article dispatcher у pinned.py + додавання BotCommand для articles).

Блокери: NBLM rate-limit loop, укр-переклад на диску не активований.

Задача: Поділись HOT.md + WARM.md, підтверди наступні кроки.