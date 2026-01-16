"""Set starter Pokemon via memory editing"""
import json
from pathlib import Path
from config import STARTER_SPECIES, STARTER_LEVEL

EDIT_PATH = Path("C:/Users/gilli/OneDrive/Desktop/projects/pokemon_yellow_agent/data/memory_edit.json")


def set_starter(species=STARTER_SPECIES, level=STARTER_LEVEL):
    """Send command to Lua bridge to set starter Pokemon."""
    cmd = {
        "cmd": "set_starter",
        "species": species,
        "level": level
    }

    with open(EDIT_PATH, 'w') as f:
        json.dump(cmd, f)

    print(f"SET STARTER: Species {species} (Gastly), Level {level}")
    print("Command sent to Lua bridge. Check BizHawk console for confirmation.")


if __name__ == "__main__":
    set_starter()
