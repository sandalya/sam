# Екосистема агентів Сашка — Pi5

> Цей файл — довідник по всіх проектах. Читай коли треба контекст.

---

## 🐱 Кіт (Kit)
**Роль:** Engineering-агент Сашка. Дев, дебаг, інфраструктура, git.  
**Де живе:** `~/.openclaw/workspace/kit/` → сервіс `openclaw-gateway` (systemctl --user)  
**Канал:** Telegram (той самий чат що і ти, але інший бот)  
**Що вміє:** Моніторинг Pi5, перезапуск сервісів, аналіз логів, git commits, документація  
**Стек:** OpenClaw + Claude Sonnet  

---

## 💎 InSilver v3
**Роль:** Telegram-бот консультант для ювелірної майстерні Влада (клієнти — українці)  
**Де живе:** `~/.openclaw/workspace/insilver-v3/` → сервіс `insilver-v3`  
**Що вміє:**
- Відповідає на питання клієнтів про ювелірні вироби
- 36 Q&A записів в `training.json` — ціни, плетіння, маси, лом, доставка
- Системний промпт ~10K символів, context-aware відповіді
- 7-рівневий autotester (31 реальний клієнтський сценарій)
- Health monitor + auto-restart  

**Стек:** Python 3.11, python-telegram-bot, OpenAI GPT-4, systemd  
**Статус:** Production, ~10-20 повідомлень/день від клієнтів  

---

## 🎨 Еббі (Abby)
**Роль:** AI-асистент для дизайнера Ксюші (дружини Сашка)  
**Де живе:** `~/.openclaw/workspace/abby/` → сервіс `abby`  
**Що вміє:**
- Генерує HTML макети → PNG через wkhtmltoimage
- Генерує зображення через Gemini (прямий Google API)
- Бачить кілька фото одночасно (media_group), нумерує [Фото 1]/[Фото 2]
- /learn режим — Ксюша завантажила ~30 банерів, style_knowledge.md = 63KB
- Rolling context (auto-summary після 1год паузи)
- Характер: Abby Sciuto з NCIS — тепла, енергійна, впевнена

**Стек:** Python, python-telegram-bot, Claude Sonnet + Gemini Flash, wkhtmltoimage  
**Статус:** Активна, постійно використовується Ксюшею  

---

## 🏠 Меггі (Maggy)
**Роль:** Домашній асистент сім'ї  
**Де живе:** `~/.openclaw/workspace/household_agent/` → сервіс `household_agent`  
**Що вміє:**
- Шоп-ліст: додати / видалити / переглянути
- Інвентар: є / мало / нема
- Морозилка і пентрі: трекінг по локаціях з датою
- Рецепти: зберегти по посиланню або фото, масштабування
- Голосові повідомлення (faster-whisper)
- Metro агент: пошук товарів → автододавання в кошик
- Multi-акаунт Metro (Сашко + Ксюша)
- Аналіз 254 замовлень — 1168 унікальних товарів
- Розумні пропозиції "що забули" при /metro

**Стек:** Python 3.11, python-telegram-bot, Claude Sonnet, Pillow, faster-whisper  
**Статус:** Активна, щоденне використання сім'єю  

---

## 🎓 Сем (Sam) — ти
**Роль:** Особистий агент Сашка для навчання AI  
**Де живе:** `~/.openclaw/workspace/sam/` → сервіс `sam`  
**Модулі:** digest, catchup, science, curriculum, jobs, onboarding  
**Стек:** Python, python-telegram-bot, Claude  
**Статус:** Новий, в активній розробці  

---

## Інфраструктура

**Сервер:** Raspberry Pi 5, Linux arm64  
**Всі сервіси:** systemd (крім Кота — `systemctl --user`)  
**Аліаси в терміналі:** `agents` — довідка по командах  
**Git:** два репо — `insilver-v3/` окремо, `workspace/` окремо  

---

*Файл підтримує Кіт. Питання по екосистемі → Кіт.*
