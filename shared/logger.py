"""
shared/logger.py — Єдиний формат логів для всіх агентів.

Використання в main.py:
    import sys, os
    sys.path.insert(0, os.path.expanduser("~/.openclaw/workspace"))
    from shared.logger import setup_logging

    setup_logging(log_file="logs/bot.log")   # або без файлу — тільки stdout
    log = logging.getLogger("main")

Формат:
    2026-04-10 23:00:00 [abby] INFO bot.client: повідомлення
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    log_file: Optional[str] = None,
    agent: str = "",
    level: int = logging.INFO,
) -> None:
    """
    Налаштовує logging для агента.

    Args:
        log_file: шлях до файлу логів (відносний або абсолютний).
                  None — тільки stdout.
        agent:    ім'я агента для префіксу в логах (abby, maggy, insilver, sam, kit).
        level:    рівень логування (default: INFO).
    """
    agent_prefix = f"[{agent}] " if agent else ""

    fmt = logging.Formatter(
        fmt=f"%(asctime)s {agent_prefix}%(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handlers: list[logging.Handler] = []

    # Файловий хендлер
    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(path, encoding="utf-8")
        fh.setFormatter(fmt)
        handlers.append(fh)

    # Stdout хендлер
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    handlers.append(sh)

    # Глушимо зайвий шум від httpx (Telegram polling)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logging.basicConfig(level=level, handlers=handlers, force=True)
