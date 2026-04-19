"""
sam/modules/proactive.py — проактивні повідомлення на основі стану учня.
Викликається з auto-digest scheduler перед digest.
"""
import logging
from modules.state_manager import get_current_progress, _load as load_state

logger = logging.getLogger("sam")

def generate_proactive_message() -> str | None:
    """
    Перевіряє стан учня і генерує проактивне повідомлення якщо доречно.
    Повертає None якщо нема приводу для повідомлення.
    """
    try:
        progress = get_current_progress()
    except Exception as e:
        logger.warning(f"Proactive: get_current_progress failed: {e}")
        return None

    tid = progress.get("current_topic_id")
    days_inactive = progress.get("days_inactive", 0)
    remaining = progress.get("artifacts_remaining", [])
    consumed = progress.get("artifacts_consumed", [])
    streak = progress.get("streak_days", 0)

    # 1. Давно не працював
    if days_inactive >= 3:
        return (
            f"👋 Привіт! Ти вже {days_inactive} дні не заходив до навчання.\n"
            f"Хочеш коротке повторення поточної теми чи продовжуємо далі?\n"
            f"Напиши /hub щоб побачити де зупинився."
        )

    # 2. Є непереглянуті артефакти
    if remaining and tid:
        from modules.state_manager import ARTIFACT_ICONS
        consumed_str = " ".join(ARTIFACT_ICONS.get(a, "✅") for a in consumed) or "—"
        remaining_str = " ".join(ARTIFACT_ICONS.get(a, "⬜") for a in remaining)
        return (
            f"📚 По поточній темі є що переглянути:\n"
            f"  ✅ Переглянуто: {consumed_str}\n"
            f"  ⬜ Залишилось: {remaining_str}\n"
            f"Напиши /hub щоб відкрити."
        )

    # 3. Всі артефакти переглянуті — пропозиція наступної теми
    if not remaining and tid and consumed:
        return (
            f"🎉 Поточну тему закрито! Всі матеріали переглянуто.\n"
            f"Готовий до наступної? Напиши /hub."
        )

    return None
