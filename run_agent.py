"""Pokemon Yellow Agent - Using agent_core's Spotter + Executor"""
import json
import time
import uuid
from pathlib import Path

from agent_core import Agent, agent_core as _core
from src.goal_manager import GoalManager
from src.perception import find_window, force_focus_window
from src.viewport_detector import detect_game_viewport

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

def extract_game_text(bounds, save_debug_image=False):
    """Extract text from game window using Tesseract OCR.

    Args:
        bounds: (left, top, right, bottom) tuple
        save_debug_image: If True, save captured image for debugging

    Returns:
        Extracted text string
    """
    left, top, right, bottom = bounds

    # Check for invalid bounds (minimized window)
    if left < -10000:
        return "(window minimized or invalid bounds)"

    # Clamp negative coordinates (window borders/shadows can be off-screen)
    capture_left = max(left, 0)
    capture_top = max(top, 0)
    width = right - capture_left
    height = bottom - capture_top

    if width <= 0 or height <= 0:
        return "(invalid capture dimensions)"

    try:
        # Capture game window (clamped to screen)
        img_data = _core.capture_region(capture_left, capture_top, width, height)

        # Validate capture data
        expected_size = width * height * 4  # RGBA = 4 bytes per pixel
        if len(img_data) != expected_size:
            return f"(capture failed: got {len(img_data)} bytes, expected {expected_size})"

        # DEBUG: Save image to see what we're capturing
        if save_debug_image:
            try:
                from PIL import Image
                debug_path = Path("debug_capture.png")
                img = Image.frombytes("RGBA", (width, height), bytes(img_data))
                img.save(debug_path)
                log(f"DEBUG: Saved capture to {debug_path.absolute()}")
            except Exception as e:
                log(f"DEBUG: Could not save image: {e}")

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

    # Find game window (BizHawk) - retry for up to 30 seconds
    log("Waiting for BizHawk window...")
    window = None
    for attempt in range(30):
        window = find_window("BizHawk")
        if window:
            break
        if attempt == 0:
            log("BizHawk window not found yet, waiting...")
        time.sleep(1)

    if not window:
        log("ERROR: BizHawk window not found after 30 seconds")
        log("Make sure BizHawk is running with Pokemon Yellow loaded")
        return

    log(f"Found window: {window.title}")
    log(f"Window bounds: {window.bounds}")

    # Restore and focus window if minimized
    if window.bounds[0] < -10000:  # Minimized windows have very negative coords
        log("Window is minimized, restoring...")
        force_focus_window(window.handle)
        time.sleep(0.5)
        # Re-find window to get updated bounds
        window = find_window("BizHawk")
        if window:
            log(f"Window restored, new bounds: {window.bounds}")

    # Detect actual game viewport within window
    log("Detecting game viewport...")
    game_viewport = detect_game_viewport(window.bounds)
    if game_viewport:
        log(f"Game viewport detected: {game_viewport}")
        log(f"Viewport size: {game_viewport[2] - game_viewport[0]}x{game_viewport[3] - game_viewport[1]}")
        capture_bounds = game_viewport
    else:
        log("WARNING: Could not detect game viewport, using full window")
        capture_bounds = window.bounds

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

        # 2. Check if window got minimized, restore if needed
        if window.bounds[0] < -10000:
            log("Window minimized during loop, restoring...")
            force_focus_window(window.handle)
            time.sleep(0.5)
            window = find_window("BizHawk")
            if not window or window.bounds[0] < -10000:
                log("ERROR: Could not restore window, skipping step")
                continue
            # Re-detect viewport if window was restored
            game_viewport = detect_game_viewport(window.bounds)
            if game_viewport:
                capture_bounds = game_viewport
            else:
                capture_bounds = window.bounds

        # 3. Extract text with OCR (save debug image on first step)
        ocr_text = extract_game_text(capture_bounds, save_debug_image=(step == 1))
        log(f"OCR Text: {ocr_text}")

        # Skip vision if OCR failed (window issues)
        if "(window minimized" in ocr_text or "(capture failed" in ocr_text:
            log("Skipping vision due to capture issue")
            time.sleep(1)
            continue

        # 4. Vision with OCR context
        log("[1] Spotter seeing...")
        see_prompt = f"""This is Pokemon Yellow for Game Boy.

TEXT ON SCREEN (from OCR):
{ocr_text}

Based on the text and visuals, describe:
- What type of screen? (dialogue, overworld, battle, menu, title)
- What's the player supposed to do? (press A to continue, select option, move, etc.)"""

        visual_obs = agent.spotter.see(prompt=see_prompt, bounds=capture_bounds)
        log(f"Saw: {visual_obs}")

        # 5. Update goals based on progress (every N steps)
        goal_manager.update_goals(context, ocr_text, visual_obs, last_action)
        log(f"Goals:\n{goal_manager.get_goal_context()}")

        # 6. Highlight if question mark detected (Phi3 will handle the rest)
        has_question = goal_manager.has_question_mark(ocr_text)
        if has_question:
            log("QUESTION MARK DETECTED in OCR text - Phi3 will analyze")

        # 7. Check if stuck
        if goal_manager.is_stuck():
            log("STUCK DETECTED - Using unstuck action")
            action = goal_manager.get_unstuck_action()
        else:
            # 8. Executor decides with full context
            log("[2] Executor deciding...")

            # Emphasize OCR text in context (especially if question detected)
            ocr_emphasis = "**IMPORTANT** " if has_question else ""

            full_context = f"""GAME STATE: {context}

{ocr_emphasis}TEXT ON SCREEN (from OCR):
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

        # 8. Execute via Lua bridge
        send_lua_input(action)
        last_action = action

        time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Stopped")
