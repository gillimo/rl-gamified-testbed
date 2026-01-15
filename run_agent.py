"""Pokemon Yellow Agent - Vision + Game State (Moondream sees the screen)"""
import json
import time
import uuid
from pathlib import Path

try:
    import agent_core
except ImportError:
    agent_core = None

from src.local_model import see_screen

STATE_PATH = Path("C:/Users/gilli/OneDrive/Desktop/projects/pokemon_yellow_agent/data/emulator_state.json")
INPUT_PATH = Path("C:/Users/gilli/OneDrive/Desktop/projects/pokemon_yellow_agent/data/input_command.json")

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def send_lua_input(button, frames=12):
    cmd = {"id": str(uuid.uuid4())[:8], "button": button, "frames": frames}
    INPUT_PATH.write_text(json.dumps(cmd))
    log(f">>> {button}")
    time.sleep(frames / 60.0 + 0.15)

def read_game_state():
    try:
        return json.loads(STATE_PATH.read_text())
    except:
        return None

def get_observation(retries=3):
    if agent_core is None:
        return None

    for attempt in range(retries):
        try:
            obs_json = agent_core.get_observation()
            obs = json.loads(obs_json)
            if "error" not in obs and obs.get("width", 0) > 0:
                return obs
        except Exception as e:
            log(f"    Retry {attempt+1}/{retries}: {e}")
        time.sleep(0.2)

    return None

def capture_data():
    """Get observation + game state with retry."""
    for attempt in range(5):
        obs = get_observation()
        state = read_game_state()
        if obs is not None:
            return obs, state
        log(f"    Capture retry {attempt+1}/5...")
        time.sleep(0.5)
    return None, None

def ask_model(observation, game_state):
    """Moondream sees the screen and decides."""
    prompt = f"""You are playing Pokemon Yellow. Look at the screen and decide.

GAME STATE:
- Map: {game_state.get('map_id', '?') if game_state else '?'}
- Position: ({game_state.get('player_x', '?')}, {game_state.get('player_y', '?')}) if game_state else '?'
- In battle: {game_state.get('in_battle', False) if game_state else False}

GOAL: Become Pokemon Champion. Catch Pokemon. Explore.

What button should you press? Reply with ONLY one of:
UP, DOWN, LEFT, RIGHT, A, B, START"""

    log("Thinking...")
    response = see_screen(prompt, timeout_s=180.0)
    log(f"Model: {response[:100] if response else 'None'}...")
    return response

def parse_action(response):
    if not response:
        return "A"

    r = response.upper()
    for btn in ["START", "DOWN", "UP", "LEFT", "RIGHT", "B", "A"]:
        if btn in r:
            return btn
    return "A"

def main():
    log("=" * 40)
    log("POKEMON YELLOW AGENT")
    log("Moondream vision + Game memory")
    log("=" * 40)

    step = 0
    while True:
        step += 1
        log(f"--- Step {step} ---")

        obs, state = capture_data()
        if obs is None:
            log("Capture failed, skipping...")
            time.sleep(1)
            continue

        if state:
            log(f"Map={state.get('map_id')} Pos=({state.get('player_x')},{state.get('player_y')})")

        response = ask_model(obs, state)
        action = parse_action(response)
        log(f"-> {action}")
        send_lua_input(action)

        time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Stopped")
