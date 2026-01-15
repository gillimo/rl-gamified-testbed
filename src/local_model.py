"""Local vision model using Ollama's Moondream for game understanding."""

import base64
import json
import time
import urllib.request
from io import BytesIO
from typing import Optional, Tuple

try:
    import agent_core
except ImportError:
    agent_core = None

try:
    from PIL import Image
except ImportError:
    Image = None

# Rate limiting
_last_request_at = 0.0
_min_interval_s = 0.5

OLLAMA_URL = "http://localhost:11434/api/generate"


def _image_to_base64(img_data: bytes, width: int, height: int) -> str:
    """Convert RGBA bytes to base64 PNG."""
    if Image is None:
        raise RuntimeError("PIL not installed")
    img = Image.frombytes("RGBA", (width, height), img_data)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def see_screen(prompt: str, bounds: Tuple[int, int, int, int] = None, timeout_s: float = 180.0) -> str:
    """
    Capture the screen and ask Moondream about it via Ollama.
    
    Args:
        prompt: Question to ask about the screen
        bounds: Optional (left, top, right, bottom) region
        timeout_s: Max wait time
    
    Returns:
        Moondream's response
    """
    global _last_request_at
    
    if agent_core is None:
        return "Error: agent_core not installed"
    
    # Rate limit
    now = time.time()
    if now - _last_request_at < _min_interval_s:
        time.sleep(_min_interval_s - (now - _last_request_at))
    _last_request_at = time.time()
    
    # Capture screen
    if bounds:
        left, top, right, bottom = bounds
        width, height = right - left, bottom - top
        img_data = agent_core.capture_region(left, top, width, height)
    else:
        width, height, img_data = agent_core.capture_screen()
    
    # Convert to base64
    img_b64 = _image_to_base64(bytes(img_data), width, height)
    
    # Call Ollama
    payload = {
        "model": "moondream",
        "prompt": prompt,
        "images": [img_b64],
        "stream": False
    }
    
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("response", "No response")
    except Exception as e:
        return f"Error: {e}"


def think(prompt: str, timeout_s: float = 180.0) -> str:
    """Ask Moondream to think about something (text only, no image)."""
    payload = {
        "model": "moondream",
        "prompt": prompt,
        "stream": False
    }
    
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("response", "No response")
    except Exception as e:
        return f"Error: {e}"


# Convenience functions for Pokemon Yellow
def what_do_i_see() -> str:
    """Describe what's on screen."""
    return see_screen("Describe what you see in this Pokemon game screenshot. Be brief.")


def where_should_i_go() -> str:
    """Get navigation advice."""
    return see_screen("I'm playing Pokemon Yellow. What direction should I move? Just say up, down, left, or right.")


def what_should_i_press() -> str:
    """Get button press advice."""
    return see_screen("I'm playing Pokemon Yellow. What button should I press next? Say A, B, START, or a direction.")


def is_in_battle() -> bool:
    """Check if we're in a battle."""
    response = see_screen("Is this a Pokemon battle? Answer only yes or no.")
    return "yes" in response.lower()


def is_dialogue() -> bool:
    """Check if there's dialogue on screen."""
    response = see_screen("Is there text dialogue on screen? Answer only yes or no.")
    return "yes" in response.lower()


def read_text() -> str:
    """Read any text visible on screen."""
    return see_screen("Read all the text you can see on this screen. Just output the text.")


def describe_situation() -> str:
    """Get a full situation description for decision making."""
    return see_screen(
        "You are an AI playing Pokemon Yellow. Describe the current game situation: "
        "Where am I? What's happening? What should I do next? Be specific."
    )


# Legacy compatibility
def build_prompt(state, user_message: str) -> str:
    return user_message


def run_local_model(prompt: str, timeout_s: float = 180.0) -> str:
    return see_screen(prompt, timeout_s=timeout_s)
