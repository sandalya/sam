# ECOSYSTEM.md — Екосистема Pi5

> Кіт — engineering-агент для ВСІЄЇ екосистеми. Цей файл = твій "периферійний зір".
> При фіксі в одному боті → завжди думай чи не потрібен аналогічний фікс в інших.

---

## Карта проектів

### 🏪 InSilver — `insilver-v3/`

- **Клієнт:** Влад (ювелірна майстерня)
- **Користувачі:** клієнти ювелірки
- **Стек:** Python 3.11, python-telegram-bot, OpenAI GPT-4
- **Точка входу:** `main.py`
- **AI:** `core/ai.py` + `core/prompt.py`
- **Дані:** `data/knowledge/training.json` (15 Q&A)
- **Ключові файли:**
  - `bot/admin.py` — 88KB, обережно
  - `bot/client.py`
  - `core/catalog.py`
- **Сервіс:** `insilver-v3.service` (sudo systemctl)
- **Логи:** `logs/bot.log`
- **Git:** `sandalya/insilver-v3`
- **Окремий API ключ:** `insilver-v3` (не Kit)

### 🎨 Abby v2 — `abby-v2/`

- **Клієнт:** Ксюша (дружина)
- **Призначення:** генерація дизайн-зображень
- **Стек:** Python, python-telegram-bot, Google Gemini
- **AI:** `core/image_gen.py` — `gemini-3.1-flash-image-preview`
  - **⚠️ НЕ підтримує inpainting** — завжди генерує з нуля
  - Reference images через reply mechanism
- **Humanize pipeline (ВАЖЛИВО):**
  - `core/humanize.py` — sensor noise, chromatic aberration, vignette, double JPEG, micro-rotation, fake EXIF
  - `core/ai_score.py` — Sightengine API, модель `genai`
  - env: `SIGHTENGINE_USER`, `SIGHTENGINE_SECRET`
  - Викликається в `bot/client.py` після генерації
  - UX: два фото (original + humanized) + скор `🤖 99%→57% AI` у caption
  - Кнопка `🎨 Regen` → callback `imagen_regen`
- **Doublecheck:** `core/prompt.py` — "даблчек" feature
- **Сервіс:** `abby-v2.service` (sudo systemctl)
- **Логи:** `logs/bot.log`
- **Git:** `sandalya/abby-v1` (стара назва репо, код — v2)

### 🧠 Sam — `sam/`

- **Клієнт:** Сашко (власний AI-асистент)
- **Призначення:** навчання + щоденний AI-дайджест
- **Стек:** Python, python-telegram-bot, Claude Sonnet
- **Модель:** `claude-sonnet-4-20250514` (треба оновити на 4-6)
- **Persona:** Samwise UA
- **Архітектура v2 (в процесі рефакторингу):**
  - `main.py` + `modules/{base,digest,catchup,curriculum,onboarding,science,hub}.py`
  - Token logging з правильною формулою Anthropic:
    `input*$3 + cache_read*$0.30 + cache_write*$3.75 + output*$15`
  - `learning_state.json` + `state_manager.py`
  - `/hub` dashboard
  - Smart router з keyword pre-routing
  - Proactive engine + tool-use agentic loop
  - Opus = архітектор, Sonnet = імплементатор
- **Команди:** `/digest /science /catchup /cur /onboarding /hub`
- **Auto-digest:** 9:00 Київ
- **Feedback:** 🔥 / 👎 + free-text notes
- **Дані:** `data/`, `profile.json`
- **Cache:** `data/onboarding_{key}.txt` TTL 30d
- **Сервіс:** `sam.service` (sudo systemctl)
- **Логи:** тільки journalctl (файлових немає)
- **Git:** `sandalya/sam`

### 💄 Garcia — `garcia/`

- **Клієнт:** Ксюша (дружина)
- **Призначення:** beauty/makeup асистент (НЕ пакувальний дизайн — то старий Garcia)
- **Persona:** Penelope Garcia (звертатись до Ксюші "Ксю")
- **Стек:** fork of Sam → Anthropic Claude
- **Архітектура (агентний loop):**
  - `brain.py` — think→act→observe→respond, `MAX_STEPS=8`
  - Tools: `search_products`, `search_tutorials`, `analyze_photo`, `read_profile`, `update_profile`, `search_trends`, `read_pinterest`
  - Quality logging per message
- **Profile schema:** color analysis, skin type, makeup level, owned products
- **Дані:**
  - `data/pinterest_analysis.json` — 840 pins проаналізовано
  - `data/references/` — auto-saved фото (claude-haiku оцінює чи варто зберігати)
- **Photo handling:**
  - Photo + document handlers
  - Media_group buffering 1.5s flush
  - Millisecond-timestamped filenames (anti-overwrite)
- **Команди:** `/analyze /onboarding /cur /digest`
- **Auto-digest:** 9:00 для ADMIN_IDS
- **Сервіс:** `garcia.service`
- **Логи:** journalctl
- **Git:** `sandalya/garcia`
- **⚠️ Старі модулі видалено:** curriculum, digest, onboarding, science, podcast, notebooklm

### 🏠 Meggy — `household_agent/`

- **Клієнт:** Сашко (домашні справи)
- **Сервіс:** `household_agent.service`
- **⚠️ Відома проблема:** SyntaxError від `\n` в string literals при file-patching через base64. Використовувати `cat > /tmp/patch.py << 'EOF'` з одинарними лапками навколо EOF.

### 🔬 Ed — `ed/` (QA-агент)

- **Призначення:** автоматизоване тестування ботів без ручного входу в чат
- **Архітектура:**
  - `judge/rubrics/{insilver,abby}.py` — рубрики оцінки
  - `suites/data/abby/blocks/*.json` — тест-кейси
  - `transports/{direct,telegram}.py` — спосіб доставки
- **Транспорти:**
  - `direct` — API без Telegram
  - `telegram` — Telethon від імені Сашка (видно в чаті)
- **Telethon session:** `data/telethon_session/ed_session.session`
- **Цілі ботів:** `abby = @abby_ksu_bot`
- **Запуск:**
```bash
cd ed && source venv/bin/activate && \
python3 main.py run --bot abby --block image_gen --transport telegram --judge haiku
```
- **Коли використовувати:** перевірка конкретних патчів без ручного тесту
- **Сервіс:** не systemd, запускається вручну
- **Git:** (уточнити у Сашка)

### 🐱 Kit — workspace root (це я)

- **Призначення:** dev-агент для всієї екосистеми
- **Розташування:** `~/.openclaw/workspace/`
- **Сервіс:** `openclaw-gateway` (systemctl --user)
- **Утиліти:** `health_monitor.py`, `cost_dashboard.py`, `ai_tracker.py`, `consult.py`, `chkp.sh`
- **Git:** `sandalya/openclaw-kit` (мої файли) + окремі репо по ботах

---

## Спільні патерни

При фіксі в одному боті → перевір чи не потрібен аналогічний в інших.

| Патерн                              | Де використовується                 |
| ----------------------------------- | ----------------------------------- |
| BaseModule                          | Sam, Garcia                         |
| `call_claude` / `call_claude_with_search` | Sam, Garcia                  |
| Persona prompts                     | Sam (Samwise), Garcia (Penelope)    |
| python-telegram-bot                 | InSilver, Abby-v2, Sam, Garcia, Meggy |
| systemd service                     | Всі крім Ed                         |
| Inline keyboard buttons             | Sam (/cur), InSilver, Abby-v2 (Regen) |
| Media_group buffering               | Abby-v2, Garcia                     |
| Token logging                       | Sam v2 (планується для всіх)        |

---

## AI провайдери

| Бот      | Провайдер | Модель                               | Для чого                     |
| -------- | --------- | ------------------------------------ | ---------------------------- |
| InSilver | OpenAI    | GPT-4                                | Клієнтські консультації      |
| Abby-v2  | Google    | `gemini-3.1-flash-image-preview`     | Генерація зображень          |
| Abby-v2  | Sightengine | `genai` model                      | AI-detection scoring         |
| Sam      | Anthropic | Claude Sonnet 4.x                    | Основний LLM                 |
| Garcia   | Anthropic | Claude Sonnet + Haiku (auto-save)    | Agentic loop + image scoring |
| Kit      | Anthropic | Claude (configurable)                | OpenClaw gateway             |
| Ed       | Anthropic | Claude Haiku (judge)                 | Рубрикова оцінка             |

---

## Інфраструктура Pi5

- Все на одному Raspberry Pi 5 (dev + prod)
- Сервіси ізольовані через systemd
- Git-based backup (кожен проект — окреме repo)
- JSON замість БД
- Health monitoring: `health_monitor.py`
  - CPU >80% alert
  - RAM >85% критично
- **RAM constraint:** Pi5 натягнутий 4-5 агентами → розглядається перехід на M4 Mac Mini 24GB

---

## Git репо

| Репо                      | Що містить                         |
| ------------------------- | ---------------------------------- |
| `sandalya/openclaw-kit`   | Мої файли (workspace root)         |
| `sandalya/insilver-v3`    | InSilver                           |
| `sandalya/abby-v1`        | Abby v2 (стара назва репо)         |
| `sandalya/sam`            | Sam                                |
| `sandalya/garcia`         | Garcia                             |

---

## Debug-пайплайни

### Будь-який systemd бот
```bash
sudo systemctl status [сервіс]
tail -20 [шлях_до_логів] | grep -E "(ERROR|CRITICAL|Exception)" || echo "Clean"
ps aux | grep main.py | grep -v grep
# restart — ТІЛЬКИ з дозволу Сашка для продакшн
sudo systemctl restart [сервіс]
```

### Sam / Garcia (журнал замість файлів)
```bash
journalctl -u [sam|garcia] -n 30 --no-pager
```

### Логи по ботах

| Бот      | Команда                                                  |
| -------- | -------------------------------------------------------- |
| InSilver | `tail -f ~/.openclaw/workspace/insilver-v3/logs/bot.log` |
| Abby-v2  | `tail -f ~/.openclaw/workspace/abby-v2/logs/bot.log`     |
| Sam      | `journalctl -u sam -f --no-pager`                        |
| Garcia   | `journalctl -u garcia -f --no-pager`                     |
| Meggy    | `tail -f ~/.openclaw/workspace/household_agent/logs/bot.log` |
| Kit      | `journalctl --user -u openclaw-gateway -f --no-pager`    |
