"""Game Interface - Fast Lua bridge communication"""
import json
import time
import uuid
from pathlib import Path
from typing import Dict, Optional

STATE_PATH = Path("C:/Users/gilli/OneDrive/Desktop/projects/pokemon_yellow_agent/data/emulator_state.json")
INPUT_PATH = Path("C:/Users/gilli/OneDrive/Desktop/projects/pokemon_yellow_agent/data/input_command.json")
RESET_PATH = Path("C:/Users/gilli/OneDrive/Desktop/projects/pokemon_yellow_agent/data/reset_command.json")

ACTIONS = ["UP", "DOWN", "LEFT", "RIGHT", "A", "B", "START", "SELECT"]


class GameInterface:
    """Fast interface to BizHawk emulator via JSON files."""

    def __init__(self, frames_per_action=4, save_slot=1):
        self.frames_per_action = frames_per_action
        self.save_slot = save_slot  # BizHawk save state slot to use
        self.last_state: Optional[Dict] = None

    def get_state(self) -> Dict:
        """Read current game state from Lua bridge."""
        try:
            with open(STATE_PATH, 'r') as f:
                state = json.load(f)
            self.last_state = state
            return state
        except (FileNotFoundError, json.JSONDecodeError):
            return self.last_state or {}

    def send_action(self, action_idx: int):
        """Send action to emulator (0-7 -> button)."""
        if not (0 <= action_idx < 8):
            return

        button = ACTIONS[action_idx]
        cmd = {
            "id": str(uuid.uuid4())[:8],
            "button": button,
            "frames": self.frames_per_action
        }

        with open(INPUT_PATH, 'w') as f:
            json.dump(cmd, f)

        # Wait for action to complete (~frames/60 seconds + buffer)
        time.sleep(self.frames_per_action / 60.0 + 0.05)

    def reset(self):
        """Reset game by loading save state. Retries if state looks wrong."""
        MAX_RETRIES = 3

        for attempt in range(MAX_RETRIES):
            self.last_state = None

            # Send load state command to Lua
            cmd = {
                "id": str(uuid.uuid4())[:8],
                "action": "load_state",
                "slot": self.save_slot
            }

            with open(RESET_PATH, 'w') as f:
                json.dump(cmd, f)

            print(f"  [RESET] Loading save state slot {self.save_slot} (attempt {attempt + 1}/{MAX_RETRIES})...")
            time.sleep(1.5)  # Give Lua time to process

            # Wait for FRESH GAME state: 0-1 pokemon (0 if intro), 0 badges, 0-2 pokedex
            for check in range(50):
                state = self.get_state()
                party_count = state.get('party_count', 0)
                badges = state.get('badges', 0)
                pokedex = state.get('pokedex_owned', 0)

                # Fresh game = 0 (Intro - ignore garbage) OR 1 pokemon (Started - strict check)
                if party_count == 0 or (party_count == 1 and badges == 0 and pokedex <= 2):
                    print(f"  [READY] Fresh game: {party_count} pokemon, {badges} badges, {pokedex} pokedex")
                    return

                if check % 10 == 0:
                    print(f"  [WAIT] State: party={party_count}, badges={badges}, pokedex={pokedex}...")

                time.sleep(0.2)

        print(f"  [ERROR] Save state not loading! Check BizHawk slot 1 is saved correctly.")
        print(f"  [ERROR] In BizHawk: Shift+F1 to save, F1 to load. Make sure Lua script is running.")
