"""Pokemon Yellow Agent - Using agent_core's Spotter + Executor"""
import json
import time
import uuid
from pathlib import Path

from agent_core import Agent, agent_core as _core
from src.goal_manager import GoalManager
from src.perception import find_window

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

def extract_game_text(bounds):
    """Extract text from game window using Tesseract OCR.

    Args:
        bounds: (left, top, right, bottom) tuple

    Returns:
        Extracted text string
    """
    left, top, right, bottom = bounds
    width, height = right - left, bottom - top

    try:
        # Capture game window
        img_data = _core.capture_region(left, top, width, height)

        # OCR bottom region (dialogue box)
        bottom_h = height // 4
        text_bottom = _core.ocr_region(
            img_data, width, height,
            0, height - bottom_h, width, bottom_h
        )

        # OCR top region (menus, battle text)
        top_h = height // 3
        text_top = _core.ocr_region(
            img_data, width, height,
            0, 0, width, top_h
        )

        # Combine and clean
        combined = f"{text_top.strip()}\n{text_bottom.strip()}".strip()
        return combined if combined else "(no text detected)"
    except Exception as e:
        return f"(OCR error: {e})"

def main():
    log("=" * 40)
    log("POKEMON YELLOW AGENT")
    log("Moondream + Phi3 + Tesseract OCR")
    log("=" * 40)

    # Create agent + goal manager
    agent = Agent(
        spotter_model="moondream",
        executor_model="phi3",
        spotter_timeout=120.0,
        executor_timeout=60.0
    )

    goal_manager = GoalManager(executor_model="phi3", timeout=30.0)

    # Find game window (BizHawk)
    window = find_window("BizHawk")
    if not window:
        log("ERROR: BizHawk window not found")
        log("Make sure BizHawk is running with Pokemon Yellow loaded")
        return

    log(f"Found window: {window.title}")
    log(f"Window bounds: {window.bounds}")

    step = 0
    last_action = None

    while True:
        step += 1
        log(f"--- Step {step} ---")

        # 1. Read game state from Lua bridge
        state = read_game_state()
        context = {}
        if state:
            context = {
                "map": state.get("map_id"),
                "pos": f"({state.get('player_x')},{state.get('player_y')})",
                "battle": state.get("in_battle", False)
            }
            log(f"Game: {context}")

        # 2. Extract text with OCR
        ocr_text = extract_game_text(window.bounds)
        log(f"OCR Text: {ocr_text[:100]}...")

        # 3. Vision with OCR context
        log("[1] Spotter seeing...")
        see_prompt = f"""This is Pokemon Yellow for Game Boy.

TEXT ON SCREEN (from OCR):
{ocr_text}

Based on the text and visuals, describe:
- What type of screen? (dialogue, overworld, battle, menu, title)
- What's the player supposed to do? (press A to continue, select option, move, etc.)"""

        visual_obs = agent.spotter.see(prompt=see_prompt, bounds=window.bounds)
        log(f"Saw: {visual_obs[:150]}...")

        # 4. Update goals based on progress (every N steps)
        goal_manager.update_goals(context, ocr_text, visual_obs, last_action)
        log(f"Goals:\n{goal_manager.get_goal_context()}")

        # 5. Check if stuck
        if goal_manager.is_stuck():
            log("STUCK DETECTED - Using unstuck action")
            action = goal_manager.get_unstuck_action()
        else:
            # 6. Executor decides with full context
            log("[2] Executor deciding...")
            full_context = f"""GAME STATE: {context}

TEXT ON SCREEN:
{ocr_text}

VISUAL OBSERVATION:
{visual_obs}

{goal_manager.get_goal_context()}"""

            options = ["UP", "DOWN", "LEFT", "RIGHT", "A", "B", "START", "SELECT"]
            decision = agent.executor.decide(
                context=full_context,
                options=options,
                goal="Execute the short-term goal to progress medium-term goal"
            )
            action = agent.executor.parse_action(decision, options)

        log(f"-> {action}")

        # 7. Execute via Lua bridge
        send_lua_input(action)
        last_action = action

        time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Stopped")
