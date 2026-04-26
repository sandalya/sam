Проект: Sam. Статус: Article pipeline в розробці. У smoke test виявлено критичний баг NBLM — синхронний --wait таймаутить на слайдах (300s < 5-10 хв), ретрай дублює артефакти на Google. Архітектура: NbLM має `--no-wait --json + artifact wait <task_id> --timeout 1800` (асинхронне опитування). Потребує refactoring генератора (slides, podcast_nblm, infographic, video) щоб перейти на цей шлях.

Читай HOT.md + WARM.md. Наступний крок: NBLM async polling refactor + artifact dedup + smoke test article pipeline.

Блокери: NBLM async polling. Без цього нема production-готовності для article pipeline.