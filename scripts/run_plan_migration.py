"""
Run Pass 1 of curriculum migration — creates migration_draft.json.

Reads legacy data from sam-v2/data/, calls LLM (costs ~$0.05).
Does NOT touch production. Just writes a draft for inspection.

Run: ./venv/bin/python scripts/run_plan_migration.py
"""
import sys
import logging
from pathlib import Path

# Setup paths
SAM_V2_ROOT = Path(__file__).parent.parent
WORKSPACE = SAM_V2_ROOT.parent
sys.path.insert(0, str(WORKSPACE))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Import Sam's seed curriculum
sys.path.insert(0, str(SAM_V2_ROOT))
from modules.curriculum import CURRICULUM as SEED

from shared.curriculum.migration import plan_migration

LEARNING_VECTOR = (
    "Python-розробник будує AI-агенти та Telegram-ботів з Anthropic API. "
    "Фокус: агентна архітектура, продакшн-надійність, мульти-модельні стратегії. "
    "Мета: глибоке розуміння LLM-систем та впевнений вхід в AI-індустрію."
)

def main():
    data_dir = SAM_V2_ROOT / "data"
    print(f"▶ data_dir: {data_dir}")
    print(f"▶ seed topics: {len(SEED)}")
    print(f"▶ learning_vector: {LEARNING_VECTOR[:80]}...")
    print()
    print("Calling plan_migration (2 LLM calls, ~$0.05)...")
    print()

    draft = plan_migration(
        seed_topics=SEED,
        data_dir=data_dir,
        learning_vector=LEARNING_VECTOR,
    )

    print()
    print("=" * 70)
    print(draft.summary())
    print("=" * 70)
    print()
    print(f"✅ Draft saved to: {data_dir / 'migration_draft.json'}")
    print(f"   Review it, edit if needed, then run apply step.")

if __name__ == "__main__":
    main()
