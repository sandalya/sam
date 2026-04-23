# Наступна сесія — Створення meta-репо

## Контекст попередньої сесії (23.04.2026)

У попередній сесії (commit `e3257a6` у sam-репо) завершено **велику міграцію всіх ботів на триярусну пам'ять** через `chkp3`. Мігровано: `sam`, `insilver-v3`, `household_agent` (Meggy), `ed`, `garcia`, `abby-v2` — всі мають `HOT.md` + `WARM.md` + `COLD.md` + `MEMORY.md`. Реєстр проектів — у `kit/projects.yaml`. Скрипт `chkp3.py` з командою `--init`, шаблони у `kit/templates/`.

## Архітектурне питання, яке вирішуємо цією сесією

У workspace накопичилися файли, які **не належать жодному боту**:
- `kit/chkp3.py`, `kit/templates/`, `kit/projects.yaml` — адмін-інфраструктура чекпоінтів
- `workspace/BACKLOG.md` — спільний беклог усіх проектів
- Майбутні: `ROADMAP.md`, `IDEAS.md`, `DECISIONS.md`, адмін-скрипти (backup, moniторинг)

**Проблема:** зараз ці файли або лежать у `kit/` (dev-агент Кіт), або в корені workspace. Це неправильно:
- Кіт — це dev-асистент, а не контейнер для адмін-утиліт. Змішувати в ньому "мій код як агента" і "утиліти для всієї екосистеми" — нечистий дизайн.
- Корінь workspace як проект — **непрофесійно**. Корінь має залишатись коренем.

**Рішення, прийняте сашою:** винести все це в окремий репо `meta/` з власним `.git` і своєю архітектурою.

## Репо готове

Саша створив порожній GitHub-репо: **https://github.com/sandalya/workspace-meta**

## Цільова структура
workspace/
├── sam/                    # проект (власний .git)
├── insilver-v3/            # проект (власний .git)
├── household_agent/        # проект
├── ed/                     # проект
├── garcia/                 # проект
├── abby-v2/                # проект
├── kit/                    # dev-агент Кіт (власний .git) — ЗАЛИШАЄТЬСЯ, але чистіший
├── shared/                 # shared-код ботів (уже є)
└── meta/                   # ← НОВЕ: workspace-meta репо
├── chkp/               # лінійка чекпоінтів
│   ├── chkp3.py
│   ├── projects.yaml
│   └── templates/
│       ├── MEMORY.md
│       ├── HOT.md
│       ├── WARM.md
│       ├── COLD.md
│       ├── PROMPT.md
│       └── gitignore.template
├── notes/              # воркспейс-нотатки
│   ├── BACKLOG.md
│   ├── ROADMAP.md      # на майбутнє
│   └── IDEAS.md        # на майбутнє
├── scripts/            # адмін-скрипти (пусто для старту)
├── README.md           # що таке meta, як працює
└── .git/

## План дій (по кроках)

### 1. Створити локальний клон meta-репо
```bash
cd /home/sashok/.openclaw/workspace
git clone https://github.com/sandalya/workspace-meta.git meta
cd meta
mkdir -p chkp notes scripts
```

### 2. Перенести файли з kit/ у meta/chkp/
```bash
cp /home/sashok/.openclaw/workspace/kit/chkp3.py meta/chkp/
cp /home/sashok/.openclaw/workspace/kit/chkp3.py.bak meta/chkp/
cp /home/sashok/.openclaw/workspace/kit/projects.yaml meta/chkp/
cp -r /home/sashok/.openclaw/workspace/kit/templates meta/chkp/
```

### 3. Перенести BACKLOG.md
```bash
cp /home/sashok/.openclaw/workspace/BACKLOG.md meta/notes/
```

### 4. Оновити шляхи у meta/chkp/chkp3.py
Замінити константи:
- `KIT_DIR = os.path.join(WORKSPACE, "kit")` → `META_DIR = os.path.join(WORKSPACE, "meta")` + `CHKP_DIR = os.path.join(META_DIR, "chkp")`
- `TEMPLATES_DIR = os.path.join(KIT_DIR, "templates")` → `TEMPLATES_DIR = os.path.join(CHKP_DIR, "templates")`
- `PROJECTS_YAML = os.path.join(KIT_DIR, "projects.yaml")` → `PROJECTS_YAML = os.path.join(CHKP_DIR, "projects.yaml")`

### 5. Оновити shell-alias `chkp3`
Знайти у `~/.bashrc` або `~/.bash_aliases` чинний alias і переспрямувати на `meta/chkp/chkp3.py`.

### 6. Тест міграції
Прогнати смок-чекпоінт на будь-якому проекті (наприклад Sam) — переконатись що все працює з нових шляхів:
```bash
chkp3 sam "тест міграції chkp3 у meta-репо" "продовжити" "міграція meta"
```

### 7. Оновити HOT.md всіх 6 проектів
У reminders замінити згадки `kit/projects.yaml` → `meta/chkp/projects.yaml`. Можна зробити швидко через sed по всіх HOT.md.

### 8. Створити README.md у meta/
Пояснити: що таке meta, які категорії утиліт, як додавати нові. Коротко — щоб майбутня Claude-сесія одразу розуміла.

### 9. Видалити старі файли з kit/
Після успішного тесту:
```bash
cd kit/
rm chkp3.py chkp3.py.bak projects.yaml
rm -rf templates/
git add -A && git commit -m "Moved chkp3 infrastructure to workspace-meta repo"
git push
```
Також видалити `workspace/BACKLOG.md` (тепер у meta/notes/).

### 10. Перший коміт meta-репо
```bash
cd meta/
git add -A
git commit -m "Initial commit — workspace meta infrastructure"
git push -u origin main
```

## Корові (ключові) принципи — зафіксувати в WARM meta-репо

Сесія міграції виявила кілька важливих архітектурних правил. Їх треба занести у `meta/notes/` або у `meta/README.md` щоб не забути:

**1. Кожен шар має свою відповідальність:**
- `<project>/` — код конкретного бота
- `kit/` — dev-агент Кіт (допомагає писати код, тримає свої власні файли)
- `shared/` — shared Python-модулі для ботів (agent_base, logger, token_tracker тощо)
- `meta/` — адмін-інфраструктура (чекпоінти, нотатки, скрипти) що не належить жодному боту
- `workspace/` (корінь) — НЕ проект, просто контейнер

**2. Кожен проект — окремий репо з власним `.git`.** Всередині `meta/` — теж `.git`. Кіт — теж `.git`. Workspace — **не git-репо** (або якщо є — то лише для випадкових корневих файлів, не як проект).

**3. Триярусна пам'ять (HOT/WARM/COLD/MEMORY) — стандарт для всіх проектів.** Правила:
   - HOT.md — що зараз, 60 рядків, переписується щосесії
   - WARM.md — архітектура і рішення, 400 рядків, інкрементальні оновлення
   - COLD.md — архів, append-only
   - MEMORY.md — Rule Zero (при згадці проекту → першим ділом читати HOT+WARM)

**4. Rule Zero у Claude-сесії:** при старті роботи з будь-яким проектом — першим ділом `cat <project>/HOT.md <project>/WARM.md`. Не відповідати з пам'яті моделі — у Claude memory може бути застарілою.

**5. chkp3 — робочий патерн:**
   - Нові проекти: `chkp3 --init <name>` створює всі 5 файлів із шаблонів і реєструє у `projects.yaml`
   - Чекпоінт: `chkp3 <project> "зроблено" "далі" "контекст"` (Haiku default, Sonnet fallback)
   - `projects.yaml` — єдина точка істини про список проектів

**6. Шлях до Кота чистіший:** після міграції Кіт не буде контейнером для чужих утиліт. Це дозволить у майбутньому розвинути Кіт як повноцінного dev-агента з власною пам'яттю, інструментами, SKILL.md тощо — без плутанини.

**7. Філософія "не тестити руками" (з Ed-контексту):** будь-який функціональний тест бота — через Ed. Написання справжньої документації Ed — пріоритетна задача найближчих сесій.

## Блокери / відкриті питання

- **Abby-v2**: не працює кнопка платного генерування (Image 4). Не критично, треба діагностувати.
- **Sam**: 2 відкладені баги — TTS не викликається з пінної меседжа; одна тема не відкриває NBLM посилання.
- **InSilver-v3**: блок `10_order_funnel` має баги в Ed (intent cache, кнопка "Інше").
- **InSilver-v4**: перед стартом — оновити implementation guide v003 → v004.

## Порядок дій наступної сесії

1. **Перше** — скинути Claude ці файли: `cat sam/HOT.md sam/WARM.md` + цей `NEXT_SESSION.md`
2. Обговорити чи архітектурна структура ок, чи щось змінити перед початком
3. Виконати план дій по кроках 1-10 (вище)
4. По завершенню — `chkp3 sam "meta-репо створено, chkp3 перенесено, шляхи оновлено" "..." "..."`
5. Опціонально — розібратись з багом Abby-v2 (Image 4 button) якщо лишиться час
