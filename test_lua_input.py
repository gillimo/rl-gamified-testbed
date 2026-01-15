import json
import time
import uuid
from pathlib import Path

INPUT_PATH = Path(r"C:\Users\gilli\OneDrive\Desktop\projects\pokemon_yellow_agent\data\input_command.json")
INPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

def send_button(button: str, frames: int = 8):
    """Send a button press to BizHawk via the Lua bridge."""
    cmd = {
        "id": str(uuid.uuid4())[:8],
        "button": button,
        "frames": frames
    }
    INPUT_PATH.write_text(json.dumps(cmd))
    print(f"Sent: {button} for {frames} frames")
    time.sleep(frames / 60.0 + 0.1)  # Wait for execution

print("Testing Lua bridge input - watch BizHawk!")
time.sleep(1)

send_button("DOWN", 8)
send_button("DOWN", 8)
send_button("A", 8)
send_button("START", 8)

print("Done! Check if menu responded.")
