# SESSION — 2026-04-19 20:41

## Проект
sam

## Що зробили
Phase 2.7: state_manager мігрований на shared.curriculum v2; видалено _cur_state і мертвий mark_artifact_consumed; ARTIFACT_ICONS розширено v2-ключами; proactive.py не чіпали — dict-контракт збережено; smoke PASS, sam.service restart clean

## Наступний крок
Phase 2.8: дерефакторити modules/curriculum.py — прибрати legacy CurriculumEngine import (перевірити спершу grep чи живий); розглянути winddown legacy-іконок з ARTIFACT_ICONS після аудиту learning_state.json

## Контекст
Бекапи phase27 у modules/; одна помилка API знайдена і виправлена — load() хоче файл а не директорію, тому DATA_DIR/curriculum.json; 17 active + 1 mastered тем на момент міграції; тест 'є що переглянути' відпрацював на реальних flashcards+podcast_tts першої active теми
