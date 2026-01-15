"""Lua Bridge Input - Send inputs to BizHawk via file-based Lua bridge."""
import json
import uuid
from pathlib import Path

INPUT_PATH = Path(r"C:\Users\gilli\OneDrive\Desktop\projects\pokemon_yellow_agent\data\input_command.json")
INPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

def send_input(button: str, frames: int = 8) -> str:
    """
    Send a single button press to BizHawk.
    
    Args:
        button: Button name - A, B, UP, DOWN, LEFT, RIGHT, START, SELECT
        frames: How many frames to hold (8 frames ≈ 133ms at 60fps)
    
    Returns:
        Command ID for tracking
    """
    cmd_id = str(uuid.uuid4())[:8]
    cmd = {"id": cmd_id, "button": button.upper(), "frames": frames}
    INPUT_PATH.write_text(json.dumps(cmd))
    return cmd_id

# Convenience functions for the agent
def press_a(frames: int = 8) -> str:
    return send_input("A", frames)

def press_b(frames: int = 8) -> str:
    return send_input("B", frames)

def press_start(frames: int = 8) -> str:
    return send_input("START", frames)

def press_select(frames: int = 8) -> str:
    return send_input("SELECT", frames)

def move_up(frames: int = 8) -> str:
    return send_input("UP", frames)

def move_down(frames: int = 8) -> str:
    return send_input("DOWN", frames)

def move_left(frames: int = 8) -> str:
    return send_input("LEFT", frames)

def move_right(frames: int = 8) -> str:
    return send_input("RIGHT", frames)
