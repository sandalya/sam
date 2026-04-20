# Sam Agentic Loop — Case Study

Розбір архітектури agentic loop у Sam: від текстового повідомлення до виконання tool і запуску pipeline.

## 1. Загальний потік

```
User message → handle_text() → Router → handle_chat_with_tools()
                                           ↓
                                    Claude API (+ SAM_TOOLS)
                                           ↓
                                    Tool call? ──yes──→ execute_tool()
                                       │                    ↓
                                       no              Handler (_h_*)
                                       ↓                    ↓
                                  Text response        Tool result
                                                         ↓
                                                  Back to Claude API
                                                  (up to 3 iterations)
```

Ключовий принцип: Claude сам вирішує коли використати tool. Розробник не пише if/else для кожного інтенту — LLM отримує список tools і вибирає відповідний.

## 2. Точка входу — handle_text()

`main.py::handle_text()` — єдиний entry point для текстових повідомлень.

Перед роутером стоїть **exam intercept**: якщо активний екзамен, всі повідомлення йдуть у `handle_exam_answer()`, мінаючи agentic loop.

Далі — keyword router (`modules/router.py`) для "важких" генерацій (digest, science, catchup, jobs, cost) з confidence threshold 0.5. Все інше — fallback у `handle_chat_with_tools()`.

Router існує для економії: digest/science потребують специфічних промптів і pipeline, не tools. Agentic loop для них — зайва витрата токенів.

## 3. Agentic Loop — handle_chat_with_tools()

Цикл до 3 ітерацій:

```python
for iteration in range(3):
    response = client.messages.create(
        model=MODEL_SMART,
        system=system_prompt,      # з пам'яттю, без conversation history
        messages=messages,
        tools=SAM_TOOLS,           # 6 tools
    )
    
    tool_calls = [b for b in response.content if b.type == "tool_use"]
    
    if not tool_calls:
        return final_text_response
    
    # Execute tools, append results, continue loop
```

Важливі деталі:

- **Stateless**: кожен виклик — новий messages list. Conversation history не передається (інакше prompt роздувається).
- **System prompt**: включає memory (MEMORY.md зміст), але не conversation store. Це design decision — Sam відповідає в контексті "хто я і що знаю", але не пам'ятає 5 повідомлень тому.
- **3 ітерації**: достатньо для get_state → analyze → update. Якщо loop не завершився — fallback на звичайний chat без tools.
- **Tool results як user messages**: стандартний Anthropic pattern — tool_result блоки йдуть у наступному user turn.

## 4. Tool Definitions — SAM_TOOLS

6 tools, кожен з JSON Schema input:

| Tool | Що робить | Input |
|------|-----------|-------|
| `get_learning_state` | Counts + активні теми з прогресом | — |
| `update_progress` | Mark format consumed | topic_id, format_key |
| `search_notebooks` | Пошук по title/id серед NBLM notebooks | query |
| `advance_topic` | Наступна тема для вивчення | — |
| `get_hub` | Dashboard: острови, прогрес, активні теми | — |
| `add_topic` | Додає тему через LLM enrich | title |

Tools описані мовою яку розуміє Claude: descriptions українською, enum для format_key, приклади в description.

Ключовий момент — descriptions мають бути **trigger-oriented**: не "Updates the progress field in the database" а "Позначає формат як спожитий ('я послухав/подивився')". Claude має розуміти *навіщо* викликати tool, не *як* він працює всередині.

## 5. Tool Dispatch — execute_tool()

Простий if/elif dispatcher:

```python
def execute_tool(name, input_data, data_dir, *, bot=None, chat_id=0):
    state = _load_state(data_dir)
    
    if name == "get_learning_state":
        return _h_get_learning_state(state)
    elif name == "add_topic":
        result = _h_add_topic(state, data_dir, input_data)
        # Side effect: auto-pipeline
        if bot and chat_id and "Додано тему" in result:
            asyncio.create_task(run_pipeline(bot, chat_id, tid, data_dir))
        return result
    ...
```

Патерни:

- **State reload**: `_load_state()` читає curriculum.json при кожному виклику. Не кешується — pipeline може змінити стан між ітераціями loop.
- **String return**: всі handlers повертають str. Claude отримує текстовий результат і формулює відповідь для користувача.
- **Side effects**: `add_topic` запускає auto-pipeline через `asyncio.create_task`. Bot і chat_id прокидаються з `handle_chat_with_tools` → `execute_tool` → handler.
- **Error handling**: try/except на верхньому рівні, помилка повертається як string — Claude може пояснити помилку користувачу.

## 6. Pipeline Integration

`add_topic` — приклад tool з side effect:

1. User: "додай тему Context Engineering"
2. Claude викликає `add_topic(title="Context Engineering")`
3. Handler: `_enrich_topic_via_llm()` → Claude визначає острів, why, read, do, content_style
4. `mutations.add_topic()` → зберігає в curriculum.json
5. Side effect: `asyncio.create_task(run_pipeline(...))` — генерація slides, podcasts, video у фоні
6. Handler повертає "Додано тему: Context Engineering [context-1]"
7. Claude формулює відповідь користувачу
8. Pipeline працює у фоні: NBLM CLI → slides → podcast → video → ...

Pipeline не блокує agentic loop — `create_task` повертається одразу. Користувач бачить відповідь, а через кілька хвилин приходять нотифікації про готові формати.

## 7. Архітектурні рішення

### Чому не function calling routing (без LLM)?

Можна було зробити keyword routing: "покажи прогрес" → `get_learning_state`, "додай тему X" → `add_topic`. Але:

- Fragile: "як у мене справи з навчанням?" не матчить жоден keyword
- Не composable: "додай тему X і покажи що ще лишилось" потребує 2 tools
- Claude краще розуміє intent ніж regex

### Чому 3 ітерації, а не більше?

- 90% запитів вирішуються за 1-2 ітерації
- 3 — достатньо для get → analyze → update pattern
- Більше ітерацій = більше токенів = більше latency
- Fallback на звичайний chat — graceful degradation

### Чому stateless (без conversation history)?

- Prompt budget: system prompt + tools + memory вже ~2K tokens
- Conversation context додав би ще 1-5K tokens per turn
- Sam не потребує multi-turn reasoning — кожне повідомлення self-contained
- Trade-off: "ти казав" не працює, але відповіді швидші і дешевші

### Чому string return, а не structured?

- Claude потребує текст щоб сформулювати human-readable відповідь
- Structured JSON потребував би ще один парсинг крок
- Простіше дебажити: `logger.info(f"Tool {name} -> {result[:80]}")`

## 8. Lessons Learned

1. **Tool descriptions > implementation quality**: якщо Claude не розуміє навіщо tool — він не викличе його, незалежно від якості коду. Інвестуй час у descriptions.

2. **Side effects через create_task**: не блокуй agentic loop довгими операціями. Pipeline, NBLM генерація, TTS — все через `asyncio.create_task`.

3. **State reload при кожному tool call**: curriculum.json може змінитися між ітераціями (pipeline працює паралельно). Кешування стану — потенційний баг.

4. **Fallback gracefully**: якщо loop не завершився за N ітерацій — не кидай помилку, дай звичайну відповідь.

5. **Router для важких операцій**: не всі команди мають йти через agentic loop. Digest потребує специфічного pipeline з 3 API calls і custom промптом — tool для цього overkill.

6. **exam_intercept pattern**: stateful діалоги (exam, onboarding) потребують перехоплення ДО agentic loop. Інакше Claude буде намагатись відповідати через tools замість слідування exam flow.
