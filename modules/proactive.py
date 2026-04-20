"""
sam/modules/proactive.py — проактивні повідомлення на основі curriculum v2.
Викликається з job_daily_digest scheduler.
"""
import logging
from pathlib import Path
from modules.base import DATA_DIR
from curriculum import load

logger = logging.getLogger("sam")

def generate_proactive_message() -> str | None:
    """
    Перевіряє стан курікулома і генерує проактивне повідомлення.
    Повертає None якщо нема приводу.
    """
    try:
        cur_path = DATA_DIR / "curriculum.json"
        state = load(cur_path)
    except Exception as e:
        logger.warning(f"Proactive: load curriculum failed: {e}")
        return None

    active = state.topics_by_state("active")
    if not active:
        return None

    # 1. Є теми з ready форматами які не consumed
    for t in active:
        ready_not_consumed = [
            k for k, f in t.formats.items()
            if f.status == "ready" and not f.consumed
        ]
        if ready_not_consumed:
            fmt_list = ", ".join(ready_not_consumed)
            return (
                f"📚 По темі <b>{t.title}</b> є непереглянутий контент:\n"
                f"  {fmt_list}\n"
                f"Відкрий /cur щоб подивитись."
            )

    # 2. Всі формати consumed у якоїсь теми — пропозиція екзамену
    for t in active:
        if not t.formats:
            continue
        all_consumed = all(
            f.consumed for f in t.formats.values()
            if f.status == "ready"
        )
        ready_count = sum(1 for f in t.formats.values() if f.status == "ready")
        if all_consumed and ready_count >= 3:
            return (
                f"🎉 Весь контент по <b>{t.title}</b> переглянуто!\n"
                f"Готовий до екзамену? Натисни 🧠 Exam у /cur"
            )

    # 3. Є теми без жодного ready формату — може pipeline впав
    for t in active:
        has_ready = any(f.status == "ready" for f in t.formats.values())
        has_failed = any(f.status == "failed" for f in t.formats.values())
        if not has_ready and has_failed:
            return (
                f"⚠️ Тема <b>{t.title}</b> має failed формати.\n"
                f"Спробуй /regen щоб перезапустити генерацію."
            )

    return None
