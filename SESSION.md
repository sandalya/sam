# SESSION — 2026-04-19 22:01

## Проект
sam

## Що зробили
Phase 2.8: видалено легасі з modules/curriculum.py — CURRICULUM seed, SamCurriculum, _get/load_state, import CurriculumEngine, FORMAT_NAMES re-export, 4 orphan команди; main.py: 4 callsites _get_cur().data_dir замінено на base.DATA_DIR, dead import CURRICULUM прибрано; -101 рядок у curriculum.py; sam тепер не імпортує shared/curriculum_engine.py взагалі; restart clean

## Наступний крок
Phase 2.9: закрити legacy in shared — grep використання curriculum_engine / notebooklm_module.load_nb_state / CURRICULUM_FILENAME; перевірити що Garcia — єдиний живий споживач; розглянути перенесення Garcia на shared.curriculum v2 або виділення engine як garcia-only

## Контекст
Бекапи phase28 у modules/curriculum.py.bak-phase28-20260419-204515 та main.py.bak-phase28-20260419-204515; одна помилка — пропустив dead import 'CURRICULUM' у main.py на розвідці, викликала 1h даунтайму; виправлено за 1 sed; pre-flight тепер має бути 'python3 -c import main' а не тільки py_compile
