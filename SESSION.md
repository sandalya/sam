# SESSION — 2026-04-19 18:04

## Проект
sam

## Що зробили
Phase 1 міграція завершена: /cur /pin /unpin → v2 UI з островами; видалено /hub /cur2 /pin2 /unpin2 + modules/hub.py + pinned_v2.py; state_manager shim читає v2; shared/formats.py для TRACKED_FORMATS; Ed блок 04_v2_migration 3/3 PASS

## Наступний крок
Phase 2 — gen pipeline на v2 (cur_add, start_topic, done, podcast, notebooks → v2 data model)

## Контекст
Soft drop A1 виконано. Legacy gen pipeline живий і працює на legacy файлах (curriculum.json 53b, learning_state.json, notebooklm_notebooks.json числові ключі). V2 файли: curriculum_v2.json (26KB, 16 тем, 6 островів), notebooklm_notebooks_v2.json, pinned_state_v2.json — зберігаються з суфіксом до Phase 2. Бекапи .bak-a1-20260419-172915. Known issue: /done оновлює legacy curriculum.json, a /cur читає v2 — розходження станів до Phase 2. Ed блоки 01/02/03 застаріли, переписати після Phase 2.
