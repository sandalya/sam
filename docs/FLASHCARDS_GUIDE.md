# Flashcards Interactive — Implementation Guide

**Phase:** 6.1
**Status:** in progress
**Owner:** Sam
**Last updated:** 2026-04-24

## Мета

Інтерактивний формат закріплення матеріалу з двома режимами презентації одного й того ж контенту:
- **Flashcard mode** — recall: показуємо питання, користувач думає, натискає "показати відповідь", оцінює себе (знаю / не знаю).
- **Quiz mode** — recognition: показуємо питання + 4 варіанти (правильна + 3 distractors), користувач обирає.

Одна LLM-генерація на тему створює `q + a + distractors` — обидва режими працюють з одним deck.

## Scope

**In scope (Phase 6.1):**
- Sonnet генерує 10 карток з distractors за один прохід.
- `Topic.formats.flashcards.cards[]` — inline сховище в curriculum.json.
- Deep-link `fc_{topic}` → режим-picker → FSM сесії.
- Ed тести: `11_flashcards.json` (два блоки: flashcard mode + quiz mode).
- Міграція: reset старих NBLM flashcards → pending для LLM-регенерації.

**Out of scope (backlog):**
- `consumed` прапорець (формат живе поза proactive/pinned галочками).
- SR алгоритм (SM-2 / Leitner).
- Експорт ANKI.
- Depth Mode інтеграція.
- Per-card статистика між сесіями (тільки within-session counters).

## Архітектура

### Data model

Розширюємо `Topic.formats.flashcards` — нове поле `cards[]`, опційне `deck_size`, опційне `last_mode`.

```python
# curriculum/models.py — існуюча модель TopicFormat розширюється
@dataclass
class TopicFormat:
    status: str           # pending | generating | ready | failed | skipped
    url: str | None       # для flashcards — None (немає external URL)
    cards: list[dict] | None = None    # NEW — для flashcards
    deck_size: int | None = None       # NEW — для flashcards (default 10)
    last_mode: str | None = None       # NEW — "flashcard" | "quiz" | None
```

### Card schema

```json
{
  "id": "card_01",
  "q": "Що таке attention у трансформерах?",
  "a": "Механізм зваженого підсумку ключів/значень за query.",
  "distractors": [
    "Тип loss функції для класифікації.",
    "Регуляризація ваг під час backprop.",
    "Метод ініціалізації ваг у feedforward шарі."
  ]
}
```

**Правила:**
- `id` — `card_NN`, zero-padded від 01 до N (deck_size).
- `q` — питання, 1-2 речення, українською.
- `a` — правильна відповідь, 1-2 речення, повна але стисла.
- `distractors` — рівно 3, правдоподібні (звучать реалістично для людини що плутається), але однозначно неправильні.

### Storage

Inline в `data/curriculum.json`:

```json
{
  "topics": [
    {
      "id": "ai-101",
      "formats": {
        "flashcards": {
          "status": "ready",
          "url": null,
          "deck_size": 10,
          "cards": [ {...}, {...}, ... ],
          "last_mode": null
        }
      }
    }
  ]
}
```

**Обґрунтування inline:** 10 карток × ~500 байт = 5KB на тему. 50 тем = 250KB curriculum.json — терпимо. Плюси: один source of truth, атомарні writes через `save()`, простіше Ed assertions.

### Session state (runtime)

Сесія flashcards живе в пам'яті процесу (не персистується між рестартами бота — для Phase 6.1 цього достатньо):

```python
# modules/flashcards.py
FLASHCARD_SESSIONS: dict[int, FlashcardSession] = {}  # chat_id -> session

@dataclass
class FlashcardSession:
    topic_id: str
    mode: str                  # "flashcard" | "quiz"
    cards: list[dict]          # копія з curriculum для сесії
    current_idx: int = 0
    known: list[str] = field(default_factory=list)    # card ids
    unknown: list[str] = field(default_factory=list)
    shown_answer: bool = False  # для flashcard mode: чи перевернули картку
```

SR (Phase 6.2) розширюватиме цю структуру до персистентної історії.

## Sonnet prompt

Модель: `claude-sonnet-4-5` (не Haiku — якість distractors важлива).
Температура: 0.3 (детермінізм + трохи різноманіття).

```python
# curriculum/pipeline.py
FLASHCARDS_PROMPT = """Ти створюєш флеш-картки для закріплення матеріалу.

Тема: {title}
Опис (що треба знати): {read}
Острів: {island_title}

Створи РІВНО {deck_size} карток у форматі JSON. Кожна картка має:
- "q": питання (1-2 речення, українською, конкретне — перевіряє розуміння, не визначення)
- "a": правильна відповідь (1-2 речення, повна але стисла)
- "distractors": масив з РІВНО 3 неправильних варіантів, які:
  * звучать правдоподібно для людини, що плутається в темі
  * мають схожу довжину з правильною відповіддю
  * НЕ є очевидно абсурдними
  * НЕ повторюють правильну відповідь перефразовано

Уникай:
- питань на чисте визначення ("що таке X?") — натомість перевіряй використання, відмінності, наслідки
- питань з відповіддю "так/ні"
- distractors що є частковою правдою (вони мають бути однозначно неправильними)

Поверни ТІЛЬКИ JSON-масив карток, без преамбули, без markdown-блоків:
[
  {{"q": "...", "a": "...", "distractors": ["...", "...", "..."]}},
  ...
]
"""
```

**Output parsing:** `json.loads()` з fallback на regex-екстракцію `\[.*\]` якщо Sonnet раптом додасть преамбулу попри інструкцію.

**Validation після парсингу:**
- рівно `deck_size` карток
- кожна має `q`, `a`, рівно 3 `distractors`
- всі поля непорожні
- якщо валідація фейлить → retry 1 раз з температурою 0.5, потім `status = "failed"`.

## Pipeline integration

### 1. Прибрати з NBLM_FORMATS

```python
# curriculum/pipeline.py (before)
NBLM_FORMATS = ["slides", "podcast_nblm", "video", "infographic", "flashcards"]

# after
NBLM_FORMATS = ["slides", "podcast_nblm", "video", "infographic"]
LLM_FORMATS = ["flashcards"]  # NEW — generated locally by Sonnet
```

### 2. Новий generator

```python
# curriculum/pipeline.py
async def _generate_flashcards_llm(topic: Topic) -> None:
    fmt = topic.formats["flashcards"]
    deck_size = fmt.deck_size or CARDS_PER_TOPIC  # default 10

    set_format_status(topic.id, "flashcards", "generating")

    prompt = FLASHCARDS_PROMPT.format(
        title=topic.title,
        read=topic.read,
        island_title=topic.island_title,
        deck_size=deck_size,
    )

    try:
        response = await anthropic_client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=4000,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        cards = _parse_and_validate_cards(raw, deck_size)

        # Assign IDs
        for i, card in enumerate(cards, start=1):
            card["id"] = f"card_{i:02d}"

        # Persist
        fmt.cards = cards
        fmt.deck_size = deck_size
        set_format_status(topic.id, "flashcards", "ready")
        save()
        logger.info(f"flashcards ready for {topic.id}: {len(cards)} cards")

    except Exception as e:
        logger.error(f"flashcards generation failed for {topic.id}: {e}")
        set_format_status(topic.id, "flashcards", "failed")
        save()
```

### 3. Hook в run_pipeline

```python
# curriculum/pipeline.py::run_pipeline()
for fmt_key in topic.content_style:  # порядок з content_style
    fmt = topic.formats.get(fmt_key)
    if not fmt or fmt.status in ("ready", "generating", "skipped"):
        continue

    if fmt_key in NBLM_FORMATS:
        await _generate_nblm_format(topic, fmt_key)
    elif fmt_key in LLM_FORMATS:
        if fmt_key == "flashcards":
            await _generate_flashcards_llm(topic)
    elif fmt_key == "podcast_tts":
        await _generate_tts_podcast(topic)

    await refresh_pinned(...)
```

### 4. Regen compatibility

`/regen` вже працює через `reset_failed_to_pending()` — автоматично підхопить flashcards якщо статус failed. Для міграції (перший запуск після деплою) потрібен окремий скрипт — див. нижче.

## UI — pinned renderer

```python
# curriculum/renderer.py::_render_topic_line()
def _fc_link(topic: Topic) -> str:
    fmt = topic.formats.get("flashcards")
    if not fmt or fmt.status != "ready":
        return "FC"  # не клікабельно
    return f'<a href="tg://resolve?domain={BOT_USERNAME}&start=fc_{topic.id}">FC</a>'
```

Рядок теми: `NB · TTS · FC · Exam` (замість старого `NB · TTS · Exam`).

**Важливо:** БЕЗ галочок, БЕЗ `◐` — формат не трекає consumed.

## Deep-link dispatch

```python
# modules/pinned.py::_handle_deep_link()
elif payload.startswith("fc_"):
    topic_id = payload[3:]
    await start_flashcards(bot, chat_id, topic_id)
```

## FSM — callback_data формат

```
# Mode picker (після deep-link)
fc_mode_{topic_id}_card       # вибрав flashcard mode
fc_mode_{topic_id}_quiz       # вибрав quiz mode

# Flashcard mode
fc_show_{topic_id}_{card_idx}         # показати відповідь
fc_know_{topic_id}_{card_idx}         # знаю → next
fc_dunno_{topic_id}_{card_idx}        # не знаю → next

# Quiz mode
fc_pick_{topic_id}_{card_idx}_{choice_idx}   # обрав варіант 0-3

# Shared
fc_next_{topic_id}_{card_idx}         # далі (після quiz feedback)
fc_retry_{topic_id}                   # повторити невідомі (з фіналу)
fc_exit_{topic_id}                    # вийти з сесії
```

**Pattern для handler:** `r"^fc_"`.

## FSM — сценарії

### Flashcard mode

```
1. User: /start fc_ai-101  (через deep-link)
2. Bot: "📇 Оберіть режим:"
        [📇 Флешкартки] [🎯 Тест]
3. User: tap [📇 Флешкартки] → callback fc_mode_ai-101_card
4. Bot: "Картка 1/10\n\n❓ Що таке attention?"
        [👀 Показати відповідь] [🚪 Вийти]
5. User: tap [👀 Показати відповідь] → fc_show_ai-101_0
6. Bot: edits message: "Картка 1/10\n\n❓ Що таке attention?\n\n✅ Механізм..."
        [✅ Знаю] [❌ Не знаю]
7. User: tap [❌ Не знаю] → fc_dunno_ai-101_0
   → session.unknown.append("card_01"), current_idx += 1
8. Bot: "Картка 2/10\n\n❓ ..." (next card, loop 4-7)
...
N. Після останньої картки:
   Bot: "🏁 Сесія завершена!\n✅ Знаю: 7\n❌ Не знаю: 3\n\nНевідомі:\n• card_02\n• card_05\n• card_08"
        [🔄 Повторити невідомі] [🎯 Цей deck як тест] [🧠 Exam] [🚪 Вийти]
```

### Quiz mode

```
1. User: /start fc_ai-101
2. Bot: mode picker
3. User: tap [🎯 Тест] → fc_mode_ai-101_quiz
4. Bot: "Картка 1/10\n\n❓ Що таке attention?"
        [1] Механізм зваженого підсумку...
        [2] Тип loss функції...
        [3] Регуляризація ваг...
        [4] Метод ініціалізації...
        [🚪 Вийти]
   (порядок shuffle — правильна відповідь може бути на будь-якій позиції)
5. User: tap [1] → fc_pick_ai-101_0_0
   → session пам'ятає, що [1] = правильна (з shuffle map)
   → session.known.append("card_01"), current_idx += 1
6. Bot: edits: "✅ Правильно!\n\n❓ Питання...\n✅ Відповідь: Механізм..."
        [▶️ Далі]
7. User: tap [▶️ Далі] → fc_next_ai-101_0
8. Bot: наступна картка (loop 4-7)
...
```

**Shuffle detail:** session тримає `shuffle_map: dict[int, list[int]]` — per-card permutation. Наприклад, `shuffle_map[0] = [2, 0, 3, 1]` означає: позиція 0 в UI — це distractor[2], позиція 1 — правильна (a), позиція 2 — distractor[3], позиція 3 — distractor[1]. При виборі — дивимось де в permutation стоїть `0` (індекс правильної).

### Retry unknown

```
User: tap [🔄 Повторити невідомі]  → fc_retry_ai-101
→ session.cards = [c for c in original if c.id in session.unknown]
→ session.current_idx = 0, known/unknown = [], shown_answer = False
→ mode залишається той самий (flashcard або quiz)
→ Bot: "Картка 1/{len(unknown)}..."
```

### Switch mode на тому ж deck

```
User: tap [🎯 Цей deck як тест] (з фіналу flashcard сесії)
→ session перестворюється з mode="quiz", cards = original full deck
```

## Main.py integration

```python
# main.py
from modules.flashcards import (
    start_flashcards,
    handle_flashcards_callback,
    FLASHCARD_SESSIONS,
)

# У post_init або setup_handlers:
application.add_handler(
    CallbackQueryHandler(handle_flashcards_callback, pattern=r"^fc_")
)

# У _handle_deep_link (уже існує в pinned.py, оновлюємо):
elif payload.startswith("fc_"):
    topic_id = payload[3:]
    await start_flashcards(update, context, topic_id)
```

**BotCommand:** не додаємо `/flashcards` в глобальний list — запуск тільки через deep-link з pinned. Команду `/flashcards_cancel` додамо як hidden utility (паралель з `/exam_cancel`).

## Модуль modules/flashcards.py — каркас

```python
# modules/flashcards.py
import random
from dataclasses import dataclass, field
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from curriculum import load, save
from curriculum.mutations import set_format_last_mode  # NEW helper


@dataclass
class FlashcardSession:
    topic_id: str
    mode: str                          # "flashcard" | "quiz"
    cards: list[dict]
    current_idx: int = 0
    known: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    shown_answer: bool = False
    shuffle_map: dict[int, list[int]] = field(default_factory=dict)


FLASHCARD_SESSIONS: dict[int, FlashcardSession] = {}


async def start_flashcards(update, context, topic_id: str) -> None:
    """Entry point from deep-link. Shows mode picker."""
    ...


async def handle_flashcards_callback(update, context) -> None:
    """Main FSM dispatcher. Routes by callback_data prefix."""
    data = update.callback_query.data
    if data.startswith("fc_mode_"):
        await _handle_mode_pick(update, context)
    elif data.startswith("fc_show_"):
        await _handle_show_answer(update, context)
    elif data.startswith("fc_know_") or data.startswith("fc_dunno_"):
        await _handle_self_eval(update, context)
    elif data.startswith("fc_pick_"):
        await _handle_quiz_pick(update, context)
    elif data.startswith("fc_next_"):
        await _handle_next(update, context)
    elif data.startswith("fc_retry_"):
        await _handle_retry(update, context)
    elif data.startswith("fc_exit_"):
        await _handle_exit(update, context)


async def _render_card(session, update, context) -> None:
    """Renders current card based on mode. Edits existing message."""
    ...


async def _render_final_stats(session, update, context) -> None:
    """End-of-session: known/unknown counts, retry buttons."""
    ...
```

Повну реалізацію пишемо в окремому файлі, guide дає контракт.

## Міграційний скрипт

**Проблема:** існуючі теми мають `flashcards.status = "ready"` зі старого NBLM (без `cards[]`). Після деплою нового коду `start_flashcards()` впаде бо `fmt.cards is None`.

**Рішення:** одноразовий скрипт `scripts/migrate_flashcards_to_llm.py`:

```python
# scripts/migrate_flashcards_to_llm.py
"""Reset all flashcards formats to pending so LLM generator can populate cards[]."""
from curriculum import load, save
from curriculum.mutations import set_format_status

state = load()
count = 0
for topic in state.topics:
    fmt = topic.formats.get("flashcards")
    if fmt is None:
        continue
    # Only reset if no cards yet (protects against re-running after partial LLM gen)
    if fmt.cards:
        continue
    set_format_status(topic.id, "flashcards", "pending")
    fmt.url = None  # drop old NBLM URL
    count += 1

save()
print(f"Reset {count} topics to pending flashcards status.")
print("Run /regen to regenerate via Sonnet.")
```

**Запуск:** один раз після деплою, перед `/regen`.

## Ed тести — 11_flashcards.json

Структура тестового файлу (два блоки всередині одного JSON):

```json
{
  "blocks": [
    {
      "id": "11a_flashcard_mode",
      "description": "Flashcard mode: deep-link → pick card mode → show answer → self-eval → complete",
      "steps": [
        {"action": "send_command", "value": "/start fc_ai-101"},
        {"action": "assert_text_contains", "value": "Оберіть режим"},
        {"action": "click_button", "value": "📇 Флешкартки"},
        {"action": "assert_text_contains", "value": "Картка 1/10"},
        {"action": "assert_button_exists", "value": "Показати відповідь"},
        {"action": "click_button", "value": "Показати відповідь"},
        {"action": "assert_button_exists", "value": "Знаю"},
        {"action": "assert_button_exists", "value": "Не знаю"},
        {"action": "click_button", "value": "Знаю"},
        {"action": "assert_text_contains", "value": "Картка 2/10"}
      ]
    },
    {
      "id": "11b_quiz_mode",
      "description": "Quiz mode: deep-link → pick quiz → answer MC → feedback → next",
      "steps": [
        {"action": "send_command", "value": "/start fc_ai-101"},
        {"action": "click_button", "value": "🎯 Тест"},
        {"action": "assert_text_contains", "value": "Картка 1/10"},
        {"action": "assert_button_count", "value": 5},
        {"action": "click_button_by_index", "value": 0},
        {"action": "assert_text_matches_any", "value": ["Правильно", "Неправильно"]},
        {"action": "click_button", "value": "Далі"},
        {"action": "assert_text_contains", "value": "Картка 2/10"}
      ]
    },
    {
      "id": "11c_completion_and_retry",
      "description": "Complete full deck → see stats → retry unknown",
      "steps": [
        "... (прогін усіх 10 карток, потім assert на фінальний екран)"
      ]
    }
  ]
}
```

**Нові assertions що можуть знадобитись (перевірити — можливо вже є):**
- `assert_button_count` — скільки inline кнопок у останньому повідомленні.
- `click_button_by_index` — клік по кнопці за порядком (для quiz де тексти динамічні).
- `assert_text_matches_any` — OR-матч для feedback (правильна/неправильна невідомо заздалегідь).

Якщо немає — додаємо в `ed/runner/assertions.py` (≤30 хв роботи, не блокує guide).

## Checklist реалізації

1. [ ] `curriculum/models.py` — додати поля `cards`, `deck_size`, `last_mode` в `TopicFormat`.
2. [ ] `curriculum/pipeline.py` — винести flashcards з `NBLM_FORMATS` у `LLM_FORMATS`, додати `_generate_flashcards_llm()`, `FLASHCARDS_PROMPT`, `CARDS_PER_TOPIC = 10`.
3. [ ] `curriculum/pipeline.py` — парсер `_parse_and_validate_cards()` + retry-логіка.
4. [ ] `curriculum/mutations.py` — helper `set_format_last_mode(topic_id, key, mode)` якщо плануємо last_mode.
5. [ ] `curriculum/renderer.py` — додати `_fc_link()`, оновити `_render_topic_line` на `NB · TTS · FC · Exam`.
6. [ ] `modules/flashcards.py` — повна реалізація (`start_flashcards`, `handle_flashcards_callback`, всі внутрішні handlers, render helpers).
7. [ ] `modules/pinned.py::_handle_deep_link()` — додати `elif payload.startswith("fc_")`.
8. [ ] `main.py` — `CallbackQueryHandler(handle_flashcards_callback, pattern=r"^fc_")`.
9. [ ] `scripts/migrate_flashcards_to_llm.py` — одноразова міграція.
10. [ ] Деплой: `migrate_flashcards_to_llm.py` → `/regen` → перевірити статуси.
11. [ ] Ed тести: `11_flashcards.json` з трьома блоками (11a, 11b, 11c).
12. [ ] Запустити `11_flashcards` блоки через Ed, прогнати до зеленого.

**Орієнтовний час:**
- Guide (цей документ): готовий.
- Реалізація кроки 1-9: ~2 год.
- Міграція + regen: ~10-15 хв на генерацію всіх 17 тем (Sonnet, ~2 сек на тему).
- Ed тести: ~30 хв на написання + прогін.
- Debug / polish: буфер 30 хв.

**Разом:** ~3 год однієї сесії.

## Відкриті питання (вирішити під час імплементації)

1. **Stale deck при зміні topic.read:** якщо користувач edit-ить `read` через `/cur_add` (можливо?), flashcards залишаються стале. Рішення: не робимо зараз, додаємо в backlog як "invalidate flashcards on topic content change".
2. **Empty deck edge-case:** якщо Sonnet повернув 0 карток після 2 retry → `status = "failed"`, UI показує `FC` неклікабельно. Proactive engine штовхне `/regen`.
3. **Concurrent sessions same user:** якщо користувач відкрив flashcards, потім deep-link на інший topic — перша сесія губиться. Рішення: `FLASHCARD_SESSIONS[chat_id]` перезаписується, старі кнопки в чаті перестають працювати (handler повертає "Сесія закінчена, почніть заново"). Ок для Phase 6.1.
4. **Rate limit Sonnet:** 17 тем × 1 виклик = 17 запитів на regen. Anthropic rate limit — не проблема (набагато вище). Час — ~30 сек загалом.

## Backlog (Phase 6.2+)

- SR алгоритм (SM-2 або Leitner boxes), персистентна історія per-card.
- `consumed` трекінг + інтеграція з proactive engine.
- Експорт ANKI (.apkg).
- Typing mode (третій режим — вводити відповідь текстом, LLM оцінює).
- Matching pairs mode (четвертий — зіставити q↔a для всього deck одразу).
- Per-island deck (картки з кількох тем одного острова).
- `/flashcards` команда для списку decks.
- Invalidate on topic.read change.
