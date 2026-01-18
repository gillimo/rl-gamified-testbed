"""Reset Training Data - Start Fresh at Level 1"""
import json
from pathlib import Path
import shutil

# Paths
BASE_DIR = Path(__file__).parent
STATS_FILE = BASE_DIR / "trainer_stats.json"
MODELS_DIR = BASE_DIR / "models"

def reset_all():
    """Reset all training data to start fresh."""
    print("=" * 50)
    print("  RESETTING TRAINING DATA")
    print("=" * 50)

    # Reset trainer stats
    if STATS_FILE.exists():
        STATS_FILE.unlink()
        print(f"  [DELETED] {STATS_FILE.name}")

    # Create fresh stats file at level 1
    fresh_stats = {
        "total_xp": 0.0,
        "episode_count": 0,
        "best_episode_reward": 0.0,
        "max_badges": 0,
        "max_pokedex": 0,
        "total_pokemon_caught": 0,
        "total_levels_gained": 0
    }
    with open(STATS_FILE, 'w') as f:
        json.dump(fresh_stats, f, indent=2)
    print(f"  [CREATED] Fresh trainer_stats.json (Level 1)")

    # Clear model checkpoints
    if MODELS_DIR.exists():
        model_count = 0
        for model_file in MODELS_DIR.glob("*.pt"):
            model_file.unlink()
            model_count += 1
        print(f"  [DELETED] {model_count} model checkpoint(s)")
    else:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        print(f"  [CREATED] models/ directory")

    print("-" * 50)
    print("  Training data cleared!")
    print("  Trainer Level: 1")
    print("  Total XP: 0")
    print("  Ready for fresh training run.")
    print("=" * 50)


if __name__ == "__main__":
    reset_all()
