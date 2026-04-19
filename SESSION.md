# SESSION — 2026-04-19 18:14

## Проект
sam

## Що зробили
Phase 2.1: shared/curriculum/ mutations.py + __init__.py, 6/6 smoke-tests PASS

## Наступний крок
Phase 2.2: переписати cur_add + done + cmd_curriculum на v2 через shared.curriculum API

## Контекст
mutations.py має add_island/add_topic/set_topic_state/update_topic_fields/remove_topic/set_format_status/set_format_url/mark_format_consumed. __init__.py експонує публічне API. Острови в v2: tool_use_integration, agent_architecture, production_reliability, multi_model_orchestration, system_operations, rag_retrieval, evaluation_testing, llm_foundations (gap). 16 тем у 8 островах. Наступна задача — переписати shared/curriculum_engine.py::cmd_cur_add/cmd_done або Sam-специфічні обгортки щоб писали в curriculum_v2.json через mutations. Legacy curriculum_dynamic.json + learning_state.json залишаються до 2.5 cleanup.
