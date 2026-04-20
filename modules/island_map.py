"""
modules/island_map.py — Phase 5: візуалізація островів курікулома.

Текстова карта з прогресом по кожному острову,
per-topic status bars, і виявлення прогалин.

Публічне API:
    render_island_map(data_dir) -> str (HTML)
"""
import logging
from pathlib import Path

from curriculum import load

log = logging.getLogger("sam.island_map")

# Прогалини — острови які мають бути в AI-ландшафті
# але поки порожні або відсутні
REFERENCE_ISLANDS = {
    "foundations":     "LLM Foundations",
    "prompting":       "Prompting & Context Engineering",
    "tool_use":        "Tool Use & Function Calling",
    "agents":          "AI Agents",
    "multi_agent":     "Multi-Agent Systems",
    "rag":             "RAG & Retrieval",
    "evals":           "Evaluations & Testing",
    "production":      "Production AI Systems",
    "safety":          "AI Safety & Alignment",
    "interpretability":"Interpretability",
    "fine_tuning":     "Fine-tuning & Customization",
    "privacy":         "Privacy & Security",
}


def _progress_bar(ready: int, total: int, width: int = 7) -> str:
    """Генерує progress bar з emoji: ▓▓▓░░░░"""
    if total == 0:
        return "░" * width
    filled = min(round(ready / total * width), width)
    return "▓" * filled + "░" * (width - filled)


def _topic_line(t) -> str:
    """Рядок теми з compact progress."""
    ready = t.formats_ready_count()
    consumed = t.formats_consumed_count()
    total = len(t.formats) if t.formats else 0

    if t.state == "mastered":
        return f"    ✅ {t.title}"

    if total == 0:
        return f"    ○ {t.title} <i>(немає контенту)</i>"

    bar = _progress_bar(consumed, ready if ready > 0 else total)
    return f"    {bar} {t.title} ({consumed}/{ready})"


def render_island_map(data_dir: Path) -> str:
    """Рендерить повну карту островів з прогресом."""
    cur_path = data_dir / "curriculum.json"
    state = load(cur_path)

    counts = state.counts()
    lines = [
        f"🗺 <b>Карта островів</b>",
        f"",
        f"📊 {counts['total']} тем · {counts['active']} active · "
        f"{counts['mastered']} mastered · {counts['pending']} pending",
        "",
    ]

    ordered = sorted(state.islands, key=lambda i: i.order)

    for island in ordered:
        topics = [t for t in state.topics if t.island_id == island.id]
        mastered = sum(1 for t in topics if t.state == "mastered")
        total = len(topics)

        if total == 0:
            lines.append(f"🏝 <b>{island.title}</b> — <i>порожньо</i>")
            lines.append("")
            continue

        # Island progress
        pct = round(mastered / total * 100) if total > 0 else 0
        bar = _progress_bar(mastered, total, 10)
        lines.append(f"🏝 <b>{island.title}</b> [{mastered}/{total}] {bar} {pct}%")

        for t in topics:
            lines.append(_topic_line(t))
        lines.append("")

    # Прогалини — референс-острови без покриття
    # Збираємо всі слова з існуючих островів і тем для матчингу
    covered_words = set()
    for island in state.islands:
        topics_here = [t for t in state.topics if t.island_id == island.id]
        if topics_here:
            for word in island.title.lower().split():
                if len(word) > 3:
                    covered_words.add(word)
            for t in topics_here:
                for word in t.title.lower().split():
                    if len(word) > 3:
                        covered_words.add(word)

    # Також виключаємо ті що вже є як острів (навіть порожній)
    existing_island_words = set()
    for island in state.islands:
        for word in island.title.lower().split():
            if len(word) > 3:
                existing_island_words.add(word)

    gaps = []
    for ref_id, ref_title in REFERENCE_ISLANDS.items():
        ref_words = {w.lower() for w in ref_title.split() if len(w) > 3}
        if not ref_words & (covered_words | existing_island_words):
            gaps.append(ref_title)

    if gaps:
        lines.append("⚠️ <b>Прогалини в AI-ландшафті:</b>")
        for g in gaps:
            lines.append(f"    · {g}")
        lines.append("")

    lines.append("<i>Додати тему: /cur_add назва</i>")

    return "\n".join(lines)
