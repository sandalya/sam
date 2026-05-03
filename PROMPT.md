Проект: sam

Текущий статус: Intervention 4 (EN brief reframe) + Intervention 1+2+3 (dangling UUID probe + idempotent ADD_SOURCE + 4h RETRY_DELAYS) развёрнуты на disk (commits 26cf181, 47efc76, d822a29). 6 brief unit-тестов + 15 nblm unit-тестов PASS. Bulk-регенерация 13 подкастов: 5 ready, 8 pending в 4h retry-loop, 2 recovering (auto-probe + soft fallback).

Что нужно сделать: 
1. Перезагрузить sam.service на Pi5 для загрузки нових коммітов (47efc76 + d822a29 + 26cf181). 
2. Мониторить 24h на 0 ошибок parse: ищем строку 'Expecting ... delimiter' в логах.
3. Проверить system_operations-5 (UUID 2d0285dd) → soft fallback протокол работает на реальном rate-limit 429.
4. Проверить rag_retrieval-1 (UUID 0daaf506 dangling) → auto-probe детектирует null RPC, создаёт новый notebook.
5. Если оба успешны → resume bulk-regen для 17/18 подкастов.

Блокер: без sam.service restart, новый код не загружен в памяти. Запроси HOT.md + WARM.md для контекста.