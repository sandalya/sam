"""
shared/errors.py — Уніфікована обробка помилок для всіх агентів.

Використання:
    from shared.errors import handle_error, BotError, safe_reply

Підключення в bot/client.py:
    import sys, os; sys.path.insert(0, os.path.expanduser("~/.openclaw/workspace"))
    from shared.errors import handle_error, safe_reply
"""

import logging
import traceback
from enum import Enum
from typing import Optional

log = logging.getLogger("shared.errors")


class ErrorKind(str, Enum):
    AI_API       = "ai_api"        # Anthropic / OpenAI / Gemini API помилка
    TELEGRAM     = "telegram"      # Telegram API помилка
    METRO        = "metro"         # Metro/zakaz.ua API помилка
    RENDER       = "render"        # HTML→PNG рендер
    FILE_IO      = "file_io"       # Читання/запис файлів
    USER_INPUT   = "user_input"    # Некоректний ввід користувача
    UNKNOWN      = "unknown"       # Все інше


class BotError(Exception):
    """Базовий клас для помилок агентів."""
    def __init__(self, message: str, kind: ErrorKind = ErrorKind.UNKNOWN, original: Optional[Exception] = None):
        super().__init__(message)
        self.kind = kind
        self.original = original


# ── Повідомлення користувачу по типу помилки ─────────────────────────────────

USER_MESSAGES = {
    ErrorKind.AI_API:     "⚠️ AI тимчасово недоступний. Спробуй за хвилину.",
    ErrorKind.TELEGRAM:   "⚠️ Помилка відправки. Спробуй ще раз.",
    ErrorKind.METRO:      "⚠️ Metro API недоступний. Спробуй пізніше.",
    ErrorKind.RENDER:     "⚠️ Не вдалося згенерувати зображення.",
    ErrorKind.FILE_IO:    "⚠️ Помилка збереження даних.",
    ErrorKind.USER_INPUT: "⚠️ Не зрозумів запит. Спробуй інакше.",
    ErrorKind.UNKNOWN:    "⚠️ Щось пішло не так. Спробуй ще раз.",
}


def handle_error(
    exc: Exception,
    context: str = "",
    kind: ErrorKind = ErrorKind.UNKNOWN,
    agent: str = "agent",
) -> str:
    """
    Логує помилку і повертає user-friendly повідомлення.

    Args:
        exc:     виняток
        context: де сталося (напр. "handle_photo", "call_claude")
        kind:    тип помилки (ErrorKind)
        agent:   ім'я агента для логів ("abby", "maggy", "insilver")

    Returns:
        Рядок для відповіді користувачу.
    """
    label = f"[{agent}] {context}" if context else f"[{agent}]"

    if isinstance(exc, BotError):
        kind = exc.kind
        log.error(f"{label} {kind.value}: {exc} | original: {exc.original}")
    else:
        log.error(f"{label} {kind.value}: {exc}\n{traceback.format_exc()}")

    return USER_MESSAGES.get(kind, USER_MESSAGES[ErrorKind.UNKNOWN])


async def safe_reply(update, text: str) -> None:
    """Відправляє повідомлення користувачу, ковтає помилки Telegram."""
    try:
        await update.message.reply_text(text)
    except Exception as e:
        log.warning(f"safe_reply failed: {e}")


# ── Декоратор для хендлерів ───────────────────────────────────────────────────

def catch_errors(agent: str = "agent", kind: ErrorKind = ErrorKind.UNKNOWN):
    """
    Декоратор для Telegram хендлерів. Ловить всі помилки і відповідає користувачу.

    Використання:
        @catch_errors(agent="abby", kind=ErrorKind.AI_API)
        async def handle_message(update, ctx):
            ...
    """
    import functools

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(update, ctx, *args, **kwargs):
            try:
                return await func(update, ctx, *args, **kwargs)
            except Exception as exc:
                msg = handle_error(exc, context=func.__name__, kind=kind, agent=agent)
                await safe_reply(update, msg)
        return wrapper
    return decorator
