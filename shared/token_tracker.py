"""
shared/token_tracker.py — Уніфікований трекер токенів для всіх агентів.

Використання:
    import sys, os; sys.path.insert(0, os.path.expanduser("~/.openclaw/workspace"))
    from shared.token_tracker import TokenTracker

    tracker = TokenTracker(log_path="/path/to/token_log.jsonl", agent="insilver")
    tracker.track(response.usage)

Або з явними значеннями:
    tracker.track_raw(input=500, output=100, cache_read=2000)
"""

import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

log = logging.getLogger("shared.token_tracker")

# Ціни claude-sonnet-4-x ($ за токен)
PRICES_SONNET = {
    "input":          3.00 / 1_000_000,
    "output":        15.00 / 1_000_000,
    "cache_read":     0.30 / 1_000_000,
    "cache_creation": 3.75 / 1_000_000,
}

# Ціни claude-haiku-4-x ($ за токен)
PRICES_HAIKU = {
    "input":          0.80 / 1_000_000,
    "output":         4.00 / 1_000_000,
    "cache_read":     0.08 / 1_000_000,
    "cache_creation": 1.00 / 1_000_000,
}

# Ціни OpenAI gpt-4o ($ за токен)
PRICES_GPT4O = {
    "input":          2.50 / 1_000_000,
    "output":        10.00 / 1_000_000,
    "cache_read":     1.25 / 1_000_000,
    "cache_creation": 0.00 / 1_000_000,
}

PRICE_TABLES = {
    "sonnet": PRICES_SONNET,
    "haiku":  PRICES_HAIKU,
    "gpt4o":  PRICES_GPT4O,
}


class TokenTracker:
    def __init__(self, log_path: str, agent: str = "agent", model: str = "sonnet"):
        self.log_path = Path(log_path)
        self.agent = agent
        self.prices = PRICE_TABLES.get(model, PRICES_SONNET)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, entry: dict):
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            log.error(f"[{self.agent}] token_tracker write: {e}")

    def track(self, usage, has_image: bool = False, extra: Optional[dict] = None):
        """Приймає usage об'єкт від Anthropic API."""
        return self.track_raw(
            input=getattr(usage, "input_tokens", 0),
            output=getattr(usage, "output_tokens", 0),
            cache_read=getattr(usage, "cache_read_input_tokens", 0),
            cache_created=getattr(usage, "cache_creation_input_tokens", 0),
            has_image=has_image,
            extra=extra,
        )

    def track_raw(self, input: int = 0, output: int = 0,
                  cache_read: int = 0, cache_created: int = 0,
                  has_image: bool = False, extra: Optional[dict] = None) -> dict:
        """Явні значення токенів."""
        p = self.prices
        cost = (
            input * p["input"] +
            output * p["output"] +
            cache_read * p["cache_read"] +
            cache_created * p["cache_creation"]
        )
        cost_without_cache = (
            (input + cache_read + cache_created) * p["input"] +
            output * p["output"]
        )
        saved = cost_without_cache - cost

        entry = {
            "ts":            datetime.now().isoformat(timespec="seconds"),
            "agent":         self.agent,
            "input":         input,
            "output":        output,
            "cache_read":    cache_read,
            "cache_created": cache_created,
            "has_image":     has_image,
            "cost":          round(cost, 6),
            "saved":         round(saved, 6),
        }
        if extra:
            entry.update(extra)

        threading.Thread(target=self._write, args=(entry,), daemon=True).start()
        log.info(f"[{self.agent}] in={input} out={output} cache_r={cache_read} cost=${cost:.5f}")
        return entry

    def get_stats(self, days: int = 7) -> dict:
        if not self.log_path.exists():
            return {}

        cutoff = datetime.now() - timedelta(days=days)
        entries = []
        with open(self.log_path, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                    if datetime.fromisoformat(e["ts"]) >= cutoff:
                        entries.append(e)
                except Exception:
                    continue

        if not entries:
            return {}

        total = len(entries)
        total_input   = sum(e.get("input", 0) for e in entries)
        total_output  = sum(e.get("output", 0) for e in entries)
        total_cr      = sum(e.get("cache_read", 0) for e in entries)
        total_cc      = sum(e.get("cache_created", 0) for e in entries)
        total_cost    = sum(e.get("cost", 0) for e in entries)
        total_saved   = sum(e.get("saved", 0) for e in entries)
        with_image    = sum(1 for e in entries if e.get("has_image"))
        cache_hit_pct = (total_cr / (total_input + total_cr) * 100) if (total_input + total_cr) > 0 else 0

        return {
            "agent": self.agent, "days": days,
            "total_requests": total, "with_image": with_image,
            "total_input": total_input, "total_output": total_output,
            "total_cache_read": total_cr, "total_cache_created": total_cc,
            "cache_hit_rate": round(cache_hit_pct, 1),
            "total_cost": round(total_cost, 4),
            "total_saved": round(total_saved, 4),
            "avg_cost": round(total_cost / total, 5) if total else 0,
        }

    def format_stats(self, days: int = 7) -> str:
        s = self.get_stats(days)
        if not s:
            return f"📊 [{self.agent}] Даних поки немає."

        return "\n".join([
            f"📊 {self.agent} — статистика за {days} днів",
            f"Запитів: {s['total_requests']} (з фото: {s['with_image']})",
            f"🗃 Кеш: {s['cache_hit_rate']}% | зекономлено: ${s['total_saved']:.4f}",
            f"💰 Всього: ${s['total_cost']:.4f} | середній: ${s['avg_cost']:.5f}",
            f"📈 in={s['total_input']:,} out={s['total_output']:,} cache_r={s['total_cache_read']:,}",
        ])
