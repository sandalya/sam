# MEMORY.md — Довгострокова пам'ять Кота

> Курована. Оновлювати кожні кілька днів.
> Сирі логи → `memory/YYYY-MM-DD.md`. Тут — тільки патерни і уроки.

## Проблеми які вже були — RUNBOOK

### Дублікати процесів ✅
- **Симптом:** Бот не відповідає, помилки токенів
- **Діагноз:** `ps aux | grep main.py | grep -v grep` → більше 1
- **Фікс:** kill всі → systemctl restart
- **Профілактика:** завжди перевіряти перед запуском

### Конфлікт Telegram токенів ✅
- **Симптом:** дивна поведінка, "не мій чат"
- **Причина:** однакові токени в різних `.env`
- **Правило:** `.env` файли не чіпати. InSilver: `TELEGRAM_TOKEN`, OpenClaw: `TELEGRAM_BOT_TOKEN`

### Pi5 падіння під навантаженням ✅
- **Фікс:** systemd ліміти ресурсів + health monitoring
- **Моніторинг:** `health_monitor.py`
- **Контекст:** 4-5 агентів одночасно натягують RAM — можливий перехід на M4 Mac Mini 24GB

### Meggy SyntaxError ✅
- **Причина:** `\n` в string literals при file-patching через base64
- **Правило:** base64 pipeline заборонений. Використовувати `cat > /tmp/patch.py << 'EOF'` (одинарні лапки!) + `python3`

### InSilver API key swap (березень) ✅
- **Симптом:** InSilver почав використовувати Kit API key
- **Фікс:** створено нові ключі `insilver-v3` і `kit3`, оновлено `.env`, перезапущено сервіси
- **Урок:** у кожного бота — свій іменований ключ

### Abby → Abby v2 ✅
- Стара `abby/` (service `abby.service`) — legacy
- Нова `abby-v2/` (service `abby-v2.service`) — production
- **Правило:** завжди патчити і рестартити `abby-v2` крім прямого вказання

### Humanize pipeline в Abby v2 ✅
- Sightengine API, модель `genai`
- Env: `SIGHTENGINE_USER`, `SIGHTENGINE_SECRET`
- Пайплайн: humanize → score → показати original + humanized + AI%

## Архітектурні рішення

| Рішення                | Причина                             |
| ---------------------- | ----------------------------------- |
| JSON замість БД        | Простота, достатньо для масштабу    |
| Single Pi5             | Зручність, економія                 |
| systemd                | Автозапуск, ізоляція                |
| Git backup             | Версійність + backup                |
| Окремі репо по ботах   | Ізоляція змін, чіткий історія       |

## Cost уроки
- OpenClaw ~$150/рік до оптимізації
- `contextPruning` TTL 5min → 2h — значна економія
- Heartbeat оптимізація: `lightContext: true`
- **$400** загальних витрат на навчання Кота → рахуй кожен токен
- Sam v2 формула токенів Anthropic:
  `input*$3 + cache_read*$0.30 + cache_write*$3.75 + output*$15`

*Останнє оновлення: 17 квітня 2026*
