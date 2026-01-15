"""Pokemon Yellow Agent - Using agent_core's Spotter + Executor"""
import json
import time
import uuid
from pathlib import Path

from agent_core import Agent

STATE_PATH = Path("C:/Users/gilli/OneDrive/Desktop/projects/pokemon_yellow_agent/data/emulator_state.json")
INPUT_PATH = Path("C:/Users/gilli/OneDrive/Desktop/projects/pokemon_yellow_agent/data/input_command.json")

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def send_lua_input(button, frames=12):
    """Send input via Lua bridge for BizHawk."""
    cmd = {"id": str(uuid.uuid4())[:8], "button": button, "frames": frames}
    INPUT_PATH.write_text(json.dumps(cmd))
    log(f">>> {button}")
    time.sleep(frames / 60.0 + 0.15)

def read_game_state():
    try:
        return json.loads(STATE_PATH.read_text())
    except:
        return None

def main():
    log("=" * 40)
    log("POKEMON YELLOW AGENT")
    log("Spotter (Moondream) + Executor (Phi3)")
    log("=" * 40)

    # Create agent with both models
    agent = Agent(
        spotter_model="moondream",
        executor_model="phi3",
        spotter_timeout=120.0,
        executor_timeout=60.0
    )

    step = 0
    while True:
        step += 1
        log(f"--- Step {step} ---")

        # Get game state from Lua bridge
        state = read_game_state()
        context = {}
        if state:
            context = {
                "map": state.get("map_id"),
                "pos": f"({state.get('player_x')},{state.get('player_y')})",
                "battle": state.get("in_battle", False)
            }
            log(f"Game: {context}")

        # One step: Spotter sees -> Executor decides
        log("[1] Spotter seeing...")
        log("[2] Executor deciding...")
        
        # Simple, concrete questions for Moondream
        see_prompt = """Look at the Pokemon Yellow game window (the pixelated Game Boy screen).

Answer these questions:
1. Is there a text box with words at the bottom or top of screen? (yes/no)
2. Can you see a small character sprite (the player) that can walk around? (yes/no)
3. Is this a Pokemon battle with health bars? (yes/no)
4. Is this a menu with list items? (yes/no)
5. What colors dominate the screen? (helps identify screen type)

Describe what you see in simple terms."""

        # Specific goal with Pokemon Yellow guidance for Executor
        goal = """Become Pokemon Champion by progressing through Pokemon Yellow:
- On title/menu screens: press START or A to continue
- During dialogue: press A to advance text
- In overworld: explore by moving UP/DOWN/LEFT/RIGHT, talk to NPCs with A
- In battles: select FIGHT options, use moves strategically
- In menus: navigate with directional keys, confirm with A
- Goal: level up Pokemon, win battles, progress story"""

        # Pokemon Yellow button options (Game Boy controls)
        options = ["UP", "DOWN", "LEFT", "RIGHT", "A", "B", "START", "SELECT"]

        action = agent.step(
            goal=goal,
            context=context,
            options=options,
            see_prompt=see_prompt
        )

        # Show full observation for debugging
        if agent.last_observation:
            log(f"Saw:\n{agent.last_observation}")
        else:
            log("Saw: nothing")
        log(f"-> {action}")

        # Execute via Lua bridge (BizHawk needs joypad.set)
        send_lua_input(action)

        time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Stopped")
