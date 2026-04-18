"""
Run Pass 2 of curriculum migration — applies the draft.

Creates curriculum_v2.json, backs up legacy files, remaps NBLM keys.
NO LLM calls — just file operations.

Run: ./venv/bin/python scripts/run_apply_migration.py
"""
import sys
import logging
from pathlib import Path

SAM_V2_ROOT = Path(__file__).parent.parent
WORKSPACE = SAM_V2_ROOT.parent
sys.path.insert(0, str(WORKSPACE))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from shared.curriculum.migration import load_draft, apply_migration

def main():
    data_dir = SAM_V2_ROOT / "data"
    draft_path = data_dir / "migration_draft.json"

    print(f"▶ data_dir: {data_dir}")
    print(f"▶ draft: {draft_path}")
    print()

    draft = load_draft(draft_path)
    print(f"Draft has {len(draft.topics)} topics, {len(draft.islands)} islands")
    print(f"Mappings: {len(draft.legacy_to_new_id)}")
    print(f"Orphan NBLM keys to drop: {draft.unmapped_nblm_keys}")
    print()
    print("Applying...")
    print()

    result = apply_migration(draft, data_dir)
    print()
    print("=" * 70)
    print(result.summary())
    print("=" * 70)
    print()
    print("Backup files:")
    for b in result.backups:
        print(f"  - {b.name}")
    if result.dropped_nblm_keys:
        print(f"\nDropped NBLM keys: {result.dropped_nblm_keys}")

if __name__ == "__main__":
    main()
