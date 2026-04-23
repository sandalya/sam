---
project: sam
updated: 2026-04-23
---

# HOT — Sam

## Now

Token audit 2026-04-22 частково реалізовано. Sam (S1+S2+S3) і Abby-v2 (A1+A2) задеплоєні та запущені. `chkp3` вилетів з `JSONDecodeError` через переповнення `max_tokens=8000` у Haiku при великому WARM — HOT/WARM оновлюємо вручну цю сесію.

## Last done

**Сесія 23.04 (вечір) — Token Audit, реалізація Sam + Abby частини**

Джерело: `token_audit_2026-04-22.md`. Економія очікувана: Sam $2.35→$1.20-1.40/день, Abby $1.78→$1.30-1.40/день.

**Sam (`shared/agent_base.py`):**
- **S1** — додано метод `_build_system_blocks()` (рядок 181) що повертає `list[dict]`: блок 1 static (persona+anti-hallucination, cached), блок 2 memory (cached), блок 3 volatile snapshot (без кешу). Три методи (`call_claude_with_search`, `call_claude`, `call_claude_chat`) переведено на нього. Старий `_build_system()` залишено бо викликається з `sam/main.py:191`.
- **S2.1** — `_extract_and_save_memory` переведено з `smart=True` (Sonnet) на `smart=False` (Haiku) — 4× дешевше на витягуванні фактів.
- **S2.2** — додано early return `if len(user_message) < 50: return` — не витягуємо факти з "ок/дякую/так".
- **S3.1** — розширено `_is_personal_question` keywords: додано small talk (дякую/ок/привіт/як справи), уточнення (детальніше/поясни/ще раз/уточни). Small talk більше не йде в web_search.

**Abby-v2 (`abby-v2/core/ai.py`):**
- **A1** — додано `default_headers={"anthropic-beta": "extended-cache-ttl-2025-04-11"}` в клієнт + `"ttl": "1h"` на обидва cached блоки (system_prompt, style knowledge). Реальне підтвердження в логах після рестарту: `cache_read=7311` на двох послідовних запитах, `cache_created=0`.
- **A2** — диференційовані max_tokens: параметр `max_tokens` доданий в `ask_ai()`, дефолт 8000. У `ask_ai_with_image_gen` встановлюється на базі intent: CHAT → 8000 (покриває HTML-артефакти, в історії max 5090), GENERATE/TOOL → 2000 (text завжди короткий). Хардкод 16000 прибрано.

**BACKLOG оновлено** — в `meta/notes/BACKLOG.md` додано 2 пункти в секцію Abby-v2: A3 rolling summary (з деталями і застереженнями про ризик) та моніторинг token_audit фіксів через 2-3 дні.

## Next

1. **Моніторинг через 2-3 дні роботи** — перевірити `shared/token_log.jsonl` (Sam): `cache_read` на `call_claude` має перестати бути нулем (S1 effect). Перевірити `abby-v2/memory/token_log.jsonl`: `cache_created` має впасти (1h TTL замість 5хв перезаписів). Якщо Abby почала платити 2× за запис кешу без зниження перезаписів — відкотити A1.
2. **Полагодити `chkp3`** — Haiku вперся в `max_tokens=8000`, JSON обрізався на char 19208. Sonnet-fallback падає по `timeout=120`. Потрібно або підняти max_tokens в `meta/chkp/chkp.py` (~12K як безпечний дефолт), або зробити streaming відповідь, або прокинути `--max-tokens` аргумент.
3. **A3 (Abby rolling summary)** — в BACKLOG, окрема сесія. Треба моделювання на штучній довгій історії перед деплоєм бо ризик втрати контексту для Ксю.
4. **Garcia** — прочитати `brain.py` щоб підтвердити гіпотези доку (MAX_STEPS=8, agentic loop), потім G1-G3.
5. **Sam Phase 6 (Depth Mode)** — далі відкладена на 1-2 тижні реального використання.

## Blockers

- **`chkp3` не працює на великих WARM** — обхід: оновлюємо HOT/WARM вручну, git commit тільки sam-репо вручну. Див. Next#2.
- **Abby-v2 image-gen баг**: кнопка Image 4 платного генерування не працює. Блокує повне тестування Abby (не блокує token_audit — він на рівні API).
- **Sam**: Google NBLM rate limit ~6/день. Regen ретраїть щогодини, 16 тем у фоні, retry 72h. Моніторимо.

## Active branches

- **sam-репо** (`main`): Phase 3-5 done, Phase 6 відкладена. Потребує commit по S1-S3 (`shared/agent_base.py`).
- **workspace-репо** (`main`): потрібен commit по Abby змінах (`abby-v2/core/ai.py`) + BACKLOG (`meta/notes/BACKLOG.md`).

## Open questions

- Чи з'явиться реальний виграш від 1h TTL у Abby? Залежить від паттерну Ксі (бурсти з паузами 30-60 хв — економимо; бурсти >1 год або <5 хв — не економимо).
- Чи варто підняти S3 до рівня 2 (Haiku router) після моніторингу? У доці позначено як опціональне.

## Reminders

- Перед тестуванням Sam/Abby — запустити `journalctl -u <service> -f` **до** надсилання повідомлення боту.
- API keys маскувати до останніх 4 символів.
- **chkp2/chkp3 НЕ оновлюють 3 яруси самі** — це робота Claude ПЕРЕД викликом chkp.
- Workspace-репо комітиться вручну (не через chkp).
- **Не робити git commit перед chkp** — chkp сам комітить (коли працює).
- Після оновлення `projects.yaml` — перевірити `chkp --list`.
