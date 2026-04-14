import json
from datetime import datetime
from pathlib import Path

LOG_PATH = Path.home() / ".openclaw/workspace/shared/token_log.jsonl"

# Ціни claude-sonnet-4 (per million tokens)
PRICES = {
    "claude-sonnet-4-20250514": {
        "input":        3.00,
        "cache_write":  3.75,
        "cache_read":   0.30,
        "output":      15.00,
    },
    "claude-haiku-4-5-20251001": {
        "input":        0.80,
        "cache_write":  1.00,
        "cache_read":   0.08,
        "output":       4.00,
    },
}

def log_usage(response, agent: str = "unknown", call_type: str = "unknown"):
    """Логує usage з response об'єкту Anthropic. Повертає dict з вартістю."""
    try:
        u = response.usage
        model = response.model

        input_tokens       = getattr(u, "input_tokens", 0) or 0
        output_tokens      = getattr(u, "output_tokens", 0) or 0
        cache_write_tokens = getattr(u, "cache_creation_input_tokens", 0) or 0
        cache_read_tokens  = getattr(u, "cache_read_input_tokens", 0) or 0

        p = PRICES.get(model, PRICES["claude-sonnet-4-20250514"])
        M = 1_000_000

        cost_usd = (
            input_tokens       * p["input"]        / M +
            cache_write_tokens * p["cache_write"]   / M +
            cache_read_tokens  * p["cache_read"]    / M +
            output_tokens      * p["output"]        / M
        )

        record = {
            "ts":          datetime.now().isoformat(timespec="seconds"),
            "agent":       agent,
            "call_type":   call_type,
            "model":       model,
            "input":       input_tokens,
            "cache_write": cache_write_tokens,
            "cache_read":  cache_read_tokens,
            "output":      output_tokens,
            "cost_usd":    round(cost_usd, 6),
        }

        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return record
    except Exception as e:
        import logging
        logging.getLogger("shared.token_logger").warning(f"log_usage failed: {e}")
        return {}


def get_stats(agent: str = None, since_days: int = 30) -> dict:
    """Читає лог і повертає агреговану статистику."""
    if not LOG_PATH.exists():
        return {"total_cost_usd": 0, "total_calls": 0, "by_agent": {}}

    from datetime import timedelta
    cutoff = datetime.now() - timedelta(days=since_days)

    by_agent = {}
    total_cost = 0
    total_calls = 0

    with LOG_PATH.open(encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
                ts = datetime.fromisoformat(r["ts"])
                if ts < cutoff:
                    continue
                if agent and r.get("agent") != agent:
                    continue
                a = r.get("agent", "unknown")
                if a not in by_agent:
                    by_agent[a] = {"calls": 0, "cost_usd": 0, "input": 0, "output": 0, "cache_read": 0}
                by_agent[a]["calls"]      += 1
                by_agent[a]["cost_usd"]   += r.get("cost_usd", 0)
                by_agent[a]["input"]      += r.get("input", 0)
                by_agent[a]["output"]     += r.get("output", 0)
                by_agent[a]["cache_read"] += r.get("cache_read", 0)
                total_cost  += r.get("cost_usd", 0)
                total_calls += 1
            except Exception:
                continue

    return {
        "total_cost_usd": round(total_cost, 4),
        "total_calls":    total_calls,
        "by_agent":       {a: {**v, "cost_usd": round(v["cost_usd"], 4)} for a, v in by_agent.items()},
    }
