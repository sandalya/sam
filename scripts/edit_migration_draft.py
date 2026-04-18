"""
Apply curator edits to migration_draft.json.

Edits applied:
1. Rename island slugs to short names (tools, agents, knowledge, production, evals, security, foundations)
2. Dissolve "system_architecture" island — its 2 topics move to "production"
3. Move "Multi-Model Strategy" from tools → production
4. Renumber all topic IDs (agents-1, agents-2...) because slugs changed
5. Update legacy_to_new_id mapping accordingly

Safe: reads migration_draft.json, writes back in place.
Backs up the original to migration_draft.json.pre_edit.bak first.

Run: ./venv/bin/python scripts/edit_migration_draft.py
"""
import json
import shutil
import sys
from pathlib import Path

SAM_V2_ROOT = Path(__file__).parent.parent
DRAFT_PATH = SAM_V2_ROOT / "data" / "migration_draft.json"

# ─── Правки ──────────────────────────────────────────────────────────────────

# Слаг-ренейми (старий -> новий). Системна архітектура — стає None (розпускається).
SLUG_RENAME: dict[str, str | None] = {
    "tool_use_integration": "tools",
    "agent_architecture": "agents",
    "knowledge_retrieval": "knowledge",
    "production_reliability": "production",
    "system_architecture": None,     # розпускаємо
    "testing_evaluation": "evals",
    "security_privacy": "security",
    "foundations": "foundations",    # прогалина — як була
}

# Окремі правила для перенесення тем за назвою.
# Якщо title містить цей фрагмент — переносимо в інший острів.
# Спрацьовує ПІСЛЯ slug-rename. Key — фрагмент назви (case-insensitive substring).
TOPIC_MOVES: dict[str, str] = {
    "Multi-Model Strategy": "production",
    "State Management Architecture": "production",
    "Configuration Management": "production",
}

# Порядок островів (order) у новій моделі
ISLAND_ORDER = [
    "agents",
    "tools",
    "knowledge",
    "production",
    "evals",
    "security",
    "foundations",
]


def main():
    if not DRAFT_PATH.exists():
        print(f"ERROR: {DRAFT_PATH} not found. Run plan_migration first.")
        sys.exit(1)

    # Backup
    backup = DRAFT_PATH.with_suffix(".json.pre_edit.bak")
    shutil.copy2(DRAFT_PATH, backup)
    print(f"▶ Backup: {backup.name}")

    data = json.loads(DRAFT_PATH.read_text(encoding="utf-8"))

    # 1. Знайти всі теми які треба перемістити (до ренейму slug-ів)
    for topic in data["topics"]:
        for title_fragment, target_slug in TOPIC_MOVES.items():
            if title_fragment.lower() in topic["title"].lower():
                old_island = topic["island_id"]
                topic["island_id"] = target_slug
                print(f"  moved: {topic['title']!r}  {old_island} → {target_slug}")

    # 2. Перейменувати slug-и островів
    # Зробимо це обережно: спершу тимчасовий map, потім застосуємо
    alias_map: dict[str, str | None] = {}
    for island in data["islands"]:
        old_slug = island["id"]
        if old_slug not in SLUG_RENAME:
            print(f"  WARN: island slug {old_slug!r} not in SLUG_RENAME, keeping as is")
            alias_map[old_slug] = old_slug
            continue
        alias_map[old_slug] = SLUG_RENAME[old_slug]

    # 3. Застосувати ренейм до islands та topics
    new_islands = []
    for island in data["islands"]:
        new_slug = alias_map[island["id"]]
        if new_slug is None:
            print(f"  dissolved island: {island['title']} (topics already moved)")
            continue
        island["id"] = new_slug
        new_islands.append(island)
    data["islands"] = new_islands

    for topic in data["topics"]:
        old_island = topic["island_id"]
        new_island = alias_map.get(old_island)
        if new_island is None:
            # Ця тема вже була перенесена (State Management / Configuration), але island_id 
            # у топика поки що старий. Перенесемо за TOPIC_MOVES (повторимо).
            for title_fragment, target_slug in TOPIC_MOVES.items():
                if title_fragment.lower() in topic["title"].lower():
                    topic["island_id"] = target_slug
                    break
            else:
                print(f"  WARN: topic {topic['title']!r} has island that was dissolved. Moving to production.")
                topic["island_id"] = "production"
        else:
            topic["island_id"] = new_island

    # 4. Відсортувати острови за заданим ORDER
    def island_sort_key(i):
        try:
            return ISLAND_ORDER.index(i["id"])
        except ValueError:
            return 999  # невідомі в кінець
    data["islands"].sort(key=island_sort_key)
    for idx, island in enumerate(data["islands"]):
        island["order"] = idx

    # 5. Перенумерувати всі нові ID тем по новим slug островів
    # Логіка як у migration._generate_new_ids: сортуємо legacy_id по зростанню в кожному острові
    by_island: dict[str, list] = {}
    for topic in data["topics"]:
        by_island.setdefault(topic["island_id"], []).append(topic)

    new_legacy_map: dict[str, str] = {}
    for island_id, topics_in_island in by_island.items():
        topics_in_island.sort(key=lambda t: t["legacy_id"])
        for n, topic in enumerate(topics_in_island, start=1):
            old_new_id = topic["new_id"]
            new_new_id = f"{island_id}-{n}"
            topic["new_id"] = new_new_id
            new_legacy_map[str(topic["legacy_id"])] = new_new_id
            if old_new_id != new_new_id:
                pass  # тихо

    data["legacy_to_new_id"] = new_legacy_map

    # 6. Записуємо назад
    DRAFT_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 7. Підсумок
    print()
    print("=" * 60)
    print("Результат правок:")
    print("=" * 60)
    for island in data["islands"]:
        topics_here = [t for t in data["topics"] if t["island_id"] == island["id"]]
        label = " (GAP)" if island.get("is_gap") else ""
        print(f"🏝 {island['title']}{label} ({island['id']}) — {len(topics_here)} тем")
        for t in sorted(topics_here, key=lambda x: x["legacy_id"]):
            print(f"    {t['new_id']}: {t['title']}")

    print()
    print(f"✅ Draft updated: {DRAFT_PATH}")
    print(f"   Backup: {backup}")
    print(f"   legacy_to_new_id: {len(data['legacy_to_new_id'])} mappings")


if __name__ == "__main__":
    main()
