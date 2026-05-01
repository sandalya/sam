Проект: sam

**Стан**: Фаза А NBLM deep-dive рефакторингу завершена (01.05). Звучить краще: проброс `--format deep-dive --length default` у pipeline успішний, тестовано на agent_architecture-1 (~9.5 хв). Готово до Фази Б: create core/content_gen/brief.py (Haiku pre-analysis) + backends/ дерево для instruction-driven генерації.

**Наступні кроки**:
1. Фаза Б: brief.py (Haiku розбір Topic/Article контексту → instruction set для audio/visual/quiz)
2. Міграція article + topic pipeline на brief-driven instructability
3. Smoke-test 2-3 тем, article dispatcher fix, article_del BotCommand

**Блокери**: немає. RSS pipeline stable, lazy re-attach верифікована.

Перш за все — скинь мені HOT.md + WARM.md. Почнемо з brief.py архітектури.