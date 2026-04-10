# SESSION — 2026-04-10

## Стан проекту
Сем активний як `sam.service` (systemd), запущений о 18:43.

## Що зроблено сьогодні
- Створено `ECOSYSTEM.md` — опис всіх агентів Сашка (Кіт, InSilver, Еббі, Меггі, Сем)
- `modules/base.py` — `SAM_PERSONA` тепер автоматично підвантажує `ECOSYSTEM.md`
- Сем знає про всю екосистему без /start або /new

## Архітектура
```
main.py → modules/
  base.py        — SAM_PERSONA + Claude client + _load_ecosystem()
  curriculum.py  — /curriculum, /done, /start_topic
  digest.py      — /digest (AI новини)
  catchup.py     — /catchup
  science.py     — /science
  jobs.py        — /jobs (аналіз ринку праці AI)
  onboarding.py  — інтерактивне меню 5 тем
data/
  onboarding_*.txt  — кеш онбордингу (30 днів TTL)
  curriculum.json   — стан плану навчання
ECOSYSTEM.md      — опис екосистеми всіх агентів
SESSION.md        — цей файл
```

## Модулі і команди
- `/curriculum` — персональний план навчання AI (10+ тем)
- `/done N` — позначити тему виконаною
- `/start_topic N` — почати тему з матеріалами
- `/digest` — AI новини дня
- `/catchup` — що пропустив
- `/science` — наукові статті
- `/jobs` — аналіз ринку праці AI, щонеділі автоматично
- Онбординг — 5 тем: Tools, Agents, MCP, Models, Jobs

## Наступні кроки
- Розвиток модуля jobs.py — глибший аналіз ринку
- Можливо: модуль для трекінгу прогресу навчання
- Інтеграція з рештою екосистеми (якщо Сашко захоче)

## Логи
Тільки systemd journal: `journalctl -u sam -f --no-pager`
Файлових логів немає.
