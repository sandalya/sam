Проект: sam
Стан: Фаза Б core/content_gen/ архітектури 100% реалізована і протестована на agent_architecture-3. Brief-генерація через Haiku, backend-agnostic backends/ дерево, schema migration на version=2. Merge у main успішна, lazy re-attach дозволяє повну backward-compat.
Зробити далі: 1) bulk-регенерація 17 подкастів (послідовна, одна тема за раз щоб не перевантажити API); 2) article deep-link dispatcher у pinned.py для /article_<id> (PRIORITY); 3) BotCommand додати article/article_del.
Блокери: stale task_id fallback можна паралелити (не критичний).
Передай HOT.md + WARM.md з workspace/sam/.