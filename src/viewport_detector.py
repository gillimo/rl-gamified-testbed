"""Detect game viewport within emulator window."""
from typing import Tuple, Optional
import agent_core as _core


def log(msg):
    """Simple logging function."""
    print(f"[VIEWPORT] {msg}", flush=True)


def detect_game_viewport(window_bounds: Tuple[int, int, int, int]) -> Optional[Tuple[int, int, int, int]]:
    """Detect the actual game screen within the emulator window.

    Strategy: Scan the captured image for regions with Game Boy colors.
    Window chrome is typically white/gray/black. Game Boy has distinctive
    yellows, greens, blues. Find the largest rectangle with game colors.

    Args:
        window_bounds: (left, top, right, bottom) of entire window

    Returns:
        (left, top, right, bottom) of game viewport, or None if not found
    """
    left, top, right, bottom = window_bounds

    # Clamp negative coordinates (window borders/shadows can be off-screen)
    capture_left = max(left, 0)
    capture_top = max(top, 0)
    width = right - capture_left
    height = bottom - capture_top

    if width <= 0 or height <= 0:
        log(f"Invalid window bounds: {width}x{height}")
        return None

    try:
        # Capture entire window (clamped to screen)
        log(f"Capturing window from ({capture_left}, {capture_top}): {width}x{height}")
        img_data = _core.capture_region(capture_left, capture_top, width, height)

        # Expected size check
        expected_size = width * height * 4  # RGBA
        if len(img_data) != expected_size:
            log(f"Capture size mismatch: got {len(img_data)}, expected {expected_size}")
            return None

        pixels = bytes(img_data)

        # Strategy: Find bounding box of non-gray pixels
        # Game Boy screen has colors, borders are white/gray
        min_x, max_x = width, 0
        min_y, max_y = height, 0

        # Scan every 10th pixel to find game colors (not gray/white)
        stride = 10
        found_pixels = 0

        for y in range(0, height, stride):
            for x in range(0, width, stride):
                idx = (y * width + x) * 4
                if idx + 3 < len(pixels):
                    r, g, b = pixels[idx], pixels[idx + 1], pixels[idx + 2]

                    # Check if this is a "game" color (not gray/white/black chrome)
                    if _is_game_color(r, g, b):
                        found_pixels += 1
                        min_x = min(min_x, x)
                        max_x = max(max_x, x)
                        min_y = min(min_y, y)
                        max_y = max(max_y, y)

        log(f"Found {found_pixels} game-colored pixels")

        if found_pixels < 100:  # Need at least 100 colored pixels
            log("Not enough game pixels found")
            return None

        # Add padding to bounds (we sampled every 10px)
        # Convert from capture coordinates back to screen coordinates
        padding = 20
        game_left = max(capture_left, capture_left + min_x - padding)
        game_top = max(capture_top, capture_top + min_y - padding)
        game_right = min(right, capture_left + max_x + padding)
        game_bottom = min(bottom, capture_top + max_y + padding)

        game_width = game_right - game_left
        game_height = game_bottom - game_top

        log(f"Detected game region: {min_x},{min_y} -> {max_x},{max_y}")
        log(f"Game viewport: ({game_left}, {game_top}, {game_right}, {game_bottom})")
        log(f"Viewport size: {game_width}x{game_height}")

        if game_width < 100 or game_height < 100:
            log(f"Viewport too small: {game_width}x{game_height}")
            return None

        return (game_left, game_top, game_right, game_bottom)

    except Exception as e:
        log(f"Detection error: {e}")
        import traceback
        traceback.print_exc()
        return None


def _is_game_color(r: int, g: int, b: int) -> bool:
    """Check if RGB is likely a game color (not window chrome).

    Window chrome is typically:
    - White/light gray: R,G,B all > 200
    - Dark gray/black: R,G,B all < 50
    - Similar values: abs(R-G) < 20 and abs(G-B) < 20

    Game Boy colors are more varied and saturated.
    """
    # Skip very light (white borders)
    if r > 220 and g > 220 and b > 220:
        return False

    # Skip very dark (black borders)
    if r < 30 and g < 30 and b < 30:
        return False

    # Skip gray (similar R,G,B values = achromatic)
    if abs(r - g) < 30 and abs(g - b) < 30 and abs(r - b) < 30:
        return False

    # This has some color variation - likely game content
    return True
