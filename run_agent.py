"""Pokemon Yellow Agent - Structured JSON I/O via agent_core"""
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
    """Send input via Lua bridge (for BizHawk)."""
    cmd = {"id": str(uuid.uuid4())[:8], "button": button, "frames": frames}
    INPUT_PATH.write_text(json.dumps(cmd))
    log(f">>> INPUT: {button}")
    time.sleep(frames / 60.0 + 0.15)

def read_game_state():
    """Read game memory state from Lua bridge."""
    try:
        return json.loads(STATE_PATH.read_text())
    except:
        return None

def get_observation(retries=3):
    """Get structured observation from agent_core with retry."""
    if agent_core is None:
        return None

    for attempt in range(retries):
        try:
            obs_json = agent_core.get_observation()
            obs = json.loads(obs_json)
            if "error" not in obs and obs.get("width", 0) > 0:
                return obs
        except Exception as e:
            log(f"    Observation retry {attempt+1}/{retries}: {e}")
        time.sleep(0.2)

    return None

def get_ocr_text(retries=3):
    """Get OCR text from the BizHawk window with retry."""
    if agent_core is None:
        return None

    for attempt in range(retries):
        try:
            text = agent_core.ocr_window_full_all(["bizhawk", "yellow"])
            if text and len(text.strip()) > 0:
                return text.strip()
        except Exception as e:
            log(f"    OCR retry {attempt+1}/{retries}: {e}")
        time.sleep(0.2)

    return None

def capture_all_data():
    """Capture all observation data, retry until we have valid data."""
    max_attempts = 5
    
    for attempt in range(max_attempts):
        observation = get_observation()
        ocr_text = get_ocr_text()
        game_state = read_game_state()
        
        # Must have at least observation to proceed
        if observation is not None:
            return observation, ocr_text, game_state
        
        log(f"    Capture failed, retrying ({attempt+1}/{max_attempts})...")
        time.sleep(0.5)
    
    return None, None, None

def ask_model_for_action(observation, ocr_text, game_state):
    """Ask Moondream for a structured action JSON."""
    
    # Build structured prompt
    prompt = f"""You are playing Pokemon Yellow. Analyze and respond with ONLY a JSON action.

OBSERVATION:
- Screen size: {observation.get('width', '?')}x{observation.get('height', '?')}
- Yellow pixels: {observation.get('yellow_count', 0)} (menus, Pikachu)
- Red pixels: {observation.get('red_count', 0)} (HP bars)
- Arrow detected: {observation.get('arrow')}
- Highlight detected: {observation.get('highlight')}

OCR TEXT ON SCREEN:
{ocr_text if ocr_text else '(no text detected)'}

GAME MEMORY:
- Map: {game_state.get('map_id', '?') if game_state else '?'}
- Position: ({game_state.get('player_x', '?')}, {game_state.get('player_y', '?')}) if game_state else '?'
- In battle: {game_state.get('in_battle', False) if game_state else False}

RESPOND WITH ONLY ONE OF THESE JSON ACTIONS:
{{"action": "press_key", "key": "up"}}
{{"action": "press_key", "key": "down"}}
{{"action": "press_key", "key": "left"}}
{{"action": "press_key", "key": "right"}}
{{"action": "press_key", "key": "z"}}     (A button)
{{"action": "press_key", "key": "x"}}     (B button)
{{"action": "press_key", "key": "return"}} (START)

YOUR JSON ACTION:"""

    log("Asking model...")
    response = see_screen(prompt, timeout_s=180.0)
    log(f"Model response: {response[:200] if response else 'None'}...")
    
    return response

def parse_action(response):
    """Parse JSON action from model response."""
    if not response:
        return {"action": "press_key", "key": "z"}
    
    # Try to extract JSON from response
    try:
        start = response.find('{')
        end = response.rfind('}') + 1
        if start >= 0 and end > start:
            json_str = response[start:end]
            action = json.loads(json_str)
            if "action" in action:
                return action
    except:
        pass
    
    # Fallback: parse keywords
    r = response.upper()
    if "UP" in r:
        return {"action": "press_key", "key": "up"}
    elif "DOWN" in r:
        return {"action": "press_key", "key": "down"}
    elif "LEFT" in r:
        return {"action": "press_key", "key": "left"}
    elif "RIGHT" in r:
        return {"action": "press_key", "key": "right"}
    elif "START" in r or "RETURN" in r:
        return {"action": "press_key", "key": "return"}
    elif "B" in r:
        return {"action": "press_key", "key": "x"}
    else:
        return {"action": "press_key", "key": "z"}

def execute_action(action):
    """Execute action via Lua bridge."""
    key = action.get("key", "z")
    
    key_to_button = {
        "up": "UP", "down": "DOWN", "left": "LEFT", "right": "RIGHT",
        "z": "A", "x": "B", "return": "START", "space": "SELECT"
    }
    button = key_to_button.get(key, "A")
    send_lua_input(button)

def main():
    log("=" * 50)
    log("POKEMON YELLOW AGENT - STRUCTURED JSON")
    log("=" * 50)
    log("Using agent_core for observation + OCR")
    log("Retries enabled for capture failures")
    log("")
    
    step = 0
    while True:
        step += 1
        log(f"--- STEP {step} ---")
        
        # 1. Capture all data with retries
        log("[1] Capturing...")
        observation, ocr_text, game_state = capture_all_data()
        
        if observation is None:
            log("    FAILED to capture after all retries. Skipping step.")
            time.sleep(1)
            continue
        
        log(f"    Yellow: {observation.get('yellow_count', 0)}, Red: {observation.get('red_count', 0)}")
        if ocr_text:
            log(f"    OCR: {ocr_text[:80]}...")
        if game_state:
            log(f"    Game: Map={game_state.get('map_id')} Pos=({game_state.get('player_x')},{game_state.get('player_y')})")
        
        # 2. Ask model for action
        log("[2] Model decision...")
        response = ask_model_for_action(observation, ocr_text, game_state)
        
        # 3. Parse action
        action = parse_action(response)
        log(f"    Action: {json.dumps(action)}")
        
        # 4. Validate
        if agent_core:
            validation = agent_core.validate_action_intent(json.dumps(action))
            log(f"    Valid: {validation}")
        
        # 5. Execute
        log("[3] Execute...")
        execute_action(action)
        
        log("")
        time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Stopped by user")
