# CC Prompt — Intervention 2 + 3 + bonus (Sam NBLM tech debt)

## Контекст

Після diagnostic-сесії 03.05 (chkp 2394ede) ізольовано 3 баги в `core/content_gen/backends/nblm.py`. Цей prompt — для трьох пов'язаних інтервенцій разом, бо всі вони у функції `generate_and_notify` + `_start_generation`.

Прочитай повний звіт у sam/HOT.md (підтверджені знахідки direct CLI-тестами на 3 notebook'ах: healthy 8aca66e9, broken-A 0daaf506 dangling UUID, broken-B 2d0285dd RATE_LIMITED).

## Файли

- **Основний:** `core/content_gen/backends/nblm.py` (428 рядків)
- **Тести:** новий suite у `ed/suites/sam_nblm_*.json` (узгодити з існуючою структурою інших Sam Ed-suites)
- **БЕЗ змін:** `curriculum/`, `core/content_gen/brief.py`, `core/content_gen/presets.py`, `modules/notebooklm.py`, `main.py`

## Інтервенція 2 — idempotent ADD_SOURCE

**Місце:** `generate_and_notify`, Step 2, рядок ~261:
```python
if not skip_source and source_url:
    rc, stdout, stderr = await _run(["source", "add", "-n", notebook_id, source_url])
    if rc != 0:
        log.warning(f"Add source warning (ignored) for {topic_id}: {stderr}")
```

**Проблема:** `source add` викликається безумовно. Доказ — direct test на healthy notebook 8aca66e9 (agent_architecture-1) показав 4+ дублів URL `https://www.anthropic.com/research/building-effective-agents` доданих в різні дати при кожному /regen.

**Фікс:** перед `source add` виклик `source list -n <id> --json`, парсити sources, перевіряти чи `source_url` вже є серед `sources[].url`. Якщо так — skip + log.info. Якщо ні — додати.

**Edge cases:**
- `source list` rc != 0 → не блокувати, fallback до старої поведінки (log.warning + add as before)
- `source list` JSON malformed → теж fallback
- URL match — exact match по полю `url` (без normalization, без trim — sources від Sam всі через один шлях, формат стабільний)

**Не зачіпати:** flag `skip_source` (для article re-attach), порожні `source_url` теж пропускати як раніше.

## Інтервенція 3 — rate_limit retry redesign

### 3a. Скоротити RETRY_DELAYS

**Місце:** `generate_and_notify`, рядок ~256:
```python
RETRY_DELAYS = [0] + [3600] * 71  # hourly retry up to 72h on rate_limit at start
```

**Проблема:** для broken-B `2d0285dd` Google rate-limit на specific notebook очевидно довший за 72h або вічний (на 03.05 retry йшов 5+ годин без зміни поведінки). 72h марно витрачає API-час і логи.

**Фікс:** `RETRY_DELAYS = [0] + [3600] * 4`  (5 спроб total: миттєва + 4 ретраї з годинною паузою → ~4h cap).

Після вичерпання → `set_format_status('failed', error="rate_limit_exhausted")` з конкретним error message.

### 3b. Інформативний error для null-RPC

**Місце:** `_start_generation`, рядки ~166-170:
```python
if rc != 0:
    log.error(f"Start {fmt} failed rc={rc}: stdout={stdout[:300]} stderr={stderr[:300]}")
    return "", "error"
```

**Проблема:** для broken-A `0daaf506` (dangling UUID) NBLM повертає structured JSON:
```json
{"error": true, "code": "ERROR", "message": "RPC rLM1Ne returned null result data (possible server error or parameter mismatch)"}
```
Sam ставить `error="error"` що неінформативно. Треба парсити stdout і витягати code/message якщо JSON.

**Фікс:** перед `return "", "error"` спробувати:
```python
try:
    data = json.loads(stdout)
    code = data.get("code", "")
    msg = data.get("message", "")
    if code:
        return "", f"nblm_{code.lower()}"  # e.g. "nblm_error", "nblm_rate_limited"
except json.JSONDecodeError:
    pass
return "", "error"
```

Це дасть в `error` поле curriculum.json значення типу `"nblm_error"` (для null-RPC) — потім /notebooks може показати що це specific NBLM-side issue.

**Не плутати з substring detect:** rate_limit substring detection на рядку ~165 ЗАЛИШИТИ як є (це окремий early-return, до rc-check). Коди можуть бути `RATE_LIMITED` або текстове `"rate limited"` — обидва шляхи мають детектити rate-limit.

## Bonus — external stop detection

### B1. Re-load state у retry loop

**Місце:** `generate_and_notify`, Phase 1 retry loop, рядки ~272-281:
```python
for delay in RETRY_DELAYS:
    if delay:
        log.info(f"Retry start {fmt} for {topic_id} after {delay}s")
        await asyncio.sleep(delay)
    task_id, start_err = await _start_generation(...)
    if task_id or start_err != "rate_limit":
        break
```

**Проблема:** якщо Sasha вручну редагує curriculum.json `formats[fmt].status="failed"` під час retry — task продовжує дзвонити NBLM кожну годину, бо не читає JSON. Підтверджено 03.05: status=failed у JSON, але журнал показав retry 5+ годин підряд.

**Фікс:** після `await asyncio.sleep(delay)` (тобто перед наступним `_start_generation`) — re-load state і перевірити чи status все ще `generating`. Якщо ні — log.info + return (без mutation).

```python
for delay in RETRY_DELAYS:
    if delay:
        log.info(f"Retry start {fmt} for {topic_id} after {delay}s")
        await asyncio.sleep(delay)
        # External stop detection
        state = load(cur_path)
        entity = (state.get_article(topic_id) if kind == "article"
                  else state.get_topic(topic_id))
        if entity and entity.formats.get(fmt) and entity.formats[fmt].status != "generating":
            log.info(f"External stop detected for {topic_id}/{fmt} (status={entity.formats[fmt].status}), exiting retry loop")
            return
    task_id, start_err = await _start_generation(...)
    if task_id or start_err != "rate_limit":
        break
```

### B2. Re-load state у wait loop

**Місце:** `_wait_for_artifact`, рядки ~184-200:
```python
while True:
    args = ["artifact", "wait", task_id, "-n", notebook_id, ...]
    rc, stdout, stderr = await _run(args, ...)
    ...
```

**Проблема:** stale task_id (`19826355`, `7af67aad`) приречений на нескінченний `status=timeout, continuing` поки sam.service не рестартує. Підтверджено 03.05.

**Фікс:** додати параметри `topic_id, kind, fmt, cur_path` у сигнатуру `_wait_for_artifact` (або створити wrapper). Перед кожним `_run` — re-load state, перевіряти status. Якщо != "generating" — exit з `(False, "external_stop")`.

**УВАГА — сигнатура зміниться:** `_wait_for_artifact` зараз приймає `(task_id, notebook_id, timeout=1800)`. Додати потрібні параметри як kwargs з default'ами щоб НЕ зламати re-attach у `main.py` (lazy re-attach викликає `generate_and_notify`, не `_wait_for_artifact` напряму, але перевір).

```python
async def _wait_for_artifact(
    task_id: str,
    notebook_id: str,
    timeout: int = 1800,
    topic_id: str | None = None,
    kind: str = "topic",
    cur_path: Path | None = None,
    fmt: str | None = None,
) -> tuple[bool, str]:
    while True:
        # External stop detection
        if cur_path and topic_id and fmt:
            state = load(cur_path)
            entity = (state.get_article(topic_id) if kind == "article"
                      else state.get_topic(topic_id))
            if entity and entity.formats.get(fmt) and entity.formats[fmt].status != "generating":
                log.info(f"External stop detected in wait loop for {topic_id}/{fmt}")
                return False, "external_stop"
        args = ["artifact", "wait", task_id, "-n", notebook_id, "--timeout", str(timeout), "--json"]
        ...
```

І в `generate_and_notify` Phase 2 виклик:
```python
ok, err = await _wait_for_artifact(
    task_id, notebook_id,
    topic_id=topic_id, kind=kind, cur_path=cur_path, fmt=fmt,
)
```

Step 5 (persist outcome) — обробити err == "external_stop" окремо: НЕ міняти status (бо він уже зовні встановлений), тільки log.info і return без bot.send_message (юзер сам зробив stop, не треба йому повідомляти про "помилку").

## Ed-suite (новий)

Створити `ed/suites/sam_nblm_intervention_2_3.json` з блоками:

**Block: idempotent_add_source** — створити mock-NBLM stub через monkey-patch або новий notebook з 1 source → /regen → перевірити що source list повернув 1 (не 2).

**Block: rate_limit_cap** — mock NBLM завжди повертає RATE_LIMITED → запустити /regen → assert що через ~5 ітерацій (не 72) status=failed з error="rate_limit_exhausted".

**Block: nblm_error_propagation** — mock NBLM повертає structured null-RPC → assert error="nblm_error" (не "error").

**Block: external_stop_retry** — почати /regen → перевірити status=generating → manually edit curriculum.json status=failed → дочекатись наступного retry → assert що Sam не зробив новий start (зі stop в логах).

**Block: external_stop_wait** — те саме для wait-loop (mock task_id stale → external edit → assert exit).

**Якщо повноцінний mock-NBLM не реалістичний за 30 хв** — натомість додати unit-test'и через pytest у `tests/test_nblm_backend.py` з мокнутим `_run`. CC має оцінити що швидше.

## Послідовність роботи

1. Прочитай `core/content_gen/backends/nblm.py` цілком + `curriculum/mutations.py` (щоб зрозуміти `set_format_status` API).
2. Покажи **plan з 4-х кроків** (Inter 2 → 3a → 3b → bonus B1+B2 → Ed/tests). Не патч код одразу.
3. Чекай мого "ок, патч" перед edit.
4. Зроби diff і покажи. **БЕЗ commit.**
5. Я перевірю diff, скажу "commit" або корекції.
6. Після commit запусти Ed-suite (або pytest якщо вибрав unit). Я перед запуском перейду в Sam і зроблю restart.

## Чого НЕ робити

- НЕ міняти `get_or_create_notebook` — Intervention 1 (dangling UUID detect) окрема сесія.
- НЕ зачіпати `NblmBackend.generate` — wrapper навколо `generate_and_notify`, повна сумісність.
- НЕ міняти `RETRY_DELAYS` структуру (залишити як list of ints щоб логіка `for delay in` працювала).
- НЕ робити schema migration у curriculum — error string просто розширюється новими значеннями, parser їх вже толерує.
- НЕ робити commit без explicit "ок".
- НЕ запускати на проді (sam.service зараз active після restart 17:43; зміни тестувати локально через Ed або pytest).
- НЕ рестартити sam.service самостійно — це я зроблю.

## Notebook UUIDs для довідки

- healthy: `8aca66e9-b637-478f-be90-ab19bb6d2a72` (agent_architecture-1)
- broken-A dangling: `0daaf506-53db-4e78-b08a-1016082af708` (rag_retrieval-1)
- broken-B rate-limited: `2d0285dd-2a79-4326-939e-14e5bb4c0ab1` (system_operations-5)
- stale task_id (НЕ торкати): video `19826355-cc1b-4889-ab3b-9122a69d1583`, video `7af67aad-e17f-4c0e-bce2-1411025fd779`

## Direct CLI-команди для перевірки (якщо знадобиться)

```
NB=/home/sashok/.openclaw/workspace/sam/venv/bin/notebooklm
$NB source list -n <UUID> --json
$NB artifact list -n <UUID> --json
$NB generate audio -n <UUID> --no-wait --json --format deep-dive --length default "instructions"
```

Перед direct CLI на проблемних notebook'ах — `sudo systemctl stop sam.service` щоб уникнути гонки. Після — `sudo systemctl start sam.service`.