"""Detect game viewport within emulator window."""
from typing import Tuple, Optional
import agent_core as _core


def log(msg):
    """Simple logging function."""
    print(f"[VIEWPORT] {msg}", flush=True)


def detect_game_viewport(window_bounds: Tuple[int, int, int, int]) -> Optional[Tuple[int, int, int, int]]:
    """Detect the actual game screen within the emulator window.

    Args:
        window_bounds: (left, top, right, bottom) of entire window

    Returns:
        (left, top, right, bottom) of game viewport, or None if not found
    """
    left, top, right, bottom = window_bounds
    width = right - left
    height = bottom - top

    if width <= 0 or height <= 0:
        return None

    try:
        # Capture entire window
        img_data = _core.capture_region(left, top, width, height)

        # Expected size check
        expected_size = width * height * 4  # RGBA
        if len(img_data) != expected_size:
            return None

        # Strategy: Find the region with highest color variance
        # Window chrome (borders, title bar) will be uniform gray/white
        # Game content will have varied colors

        # Convert to bytes for processing
        pixels = bytes(img_data)

        # Scan for largest rectangular region with high variance
        # Start by checking edges to find uniform borders

        # Check top edge for uniform color (title bar)
        top_offset = _find_uniform_edge(pixels, width, height, 'top')
        log(f"Top border offset: {top_offset}px")

        # Check left edge for uniform color (border)
        left_offset = _find_uniform_edge(pixels, width, height, 'left')
        log(f"Left border offset: {left_offset}px")

        # Check right edge
        right_offset = _find_uniform_edge(pixels, width, height, 'right')
        log(f"Right border offset: {right_offset}px")

        # Check bottom edge
        bottom_offset = _find_uniform_edge(pixels, width, height, 'bottom')
        log(f"Bottom border offset: {bottom_offset}px")

        # Calculate game viewport
        game_left = left + left_offset
        game_top = top + top_offset
        game_right = right - right_offset
        game_bottom = bottom - bottom_offset

        # Validate detected viewport
        game_width = game_right - game_left
        game_height = game_bottom - game_top

        log(f"Detected viewport size: {game_width}x{game_height}")

        if game_width <= 100 or game_height <= 100:
            # Viewport too small, probably failed detection
            log(f"ERROR: Viewport too small ({game_width}x{game_height}), rejecting")
            return None

        log(f"SUCCESS: Viewport detected at ({game_left}, {game_top}, {game_right}, {game_bottom})")
        return (game_left, game_top, game_right, game_bottom)

    except Exception as e:
        print(f"Viewport detection error: {e}")
        return None


def _find_uniform_edge(pixels: bytes, width: int, height: int, edge: str) -> int:
    """Find how many pixels from edge are uniform color (border/chrome)."""

    # Sample pixels from the edge
    sample_size = 10  # Sample 10 pixels
    threshold = 20  # Color variance threshold

    if edge == 'top':
        # Check rows from top
        for row in range(min(100, height // 4)):  # Check up to 25% of height
            if _row_has_variance(pixels, width, height, row, threshold):
                return row  # Found content, border ends here
        return 30  # Default top border (title bar typically ~30px)

    elif edge == 'left':
        # Check columns from left
        for col in range(min(100, width // 4)):
            if _col_has_variance(pixels, width, height, col, threshold):
                return col
        return 8  # Default left border

    elif edge == 'right':
        # Check columns from right
        for offset in range(min(100, width // 4)):
            col = width - 1 - offset
            if _col_has_variance(pixels, width, height, col, threshold):
                return offset
        return 8  # Default right border

    elif edge == 'bottom':
        # Check rows from bottom
        for offset in range(min(100, height // 4)):
            row = height - 1 - offset
            if _row_has_variance(pixels, width, height, row, threshold):
                return offset
        return 8  # Default bottom border

    return 0


def _row_has_variance(pixels: bytes, width: int, height: int, row: int, threshold: int) -> bool:
    """Check if a row of pixels has color variance (likely game content)."""
    if row >= height:
        return False

    # Sample a few pixels from the row
    samples = []
    for x in range(0, width, max(1, width // 10)):  # Sample ~10 points
        idx = (row * width + x) * 4
        if idx + 3 < len(pixels):
            r, g, b = pixels[idx], pixels[idx + 1], pixels[idx + 2]
            samples.append((r, g, b))

    if len(samples) < 2:
        return False

    # Calculate variance
    return _color_variance(samples) > threshold


def _col_has_variance(pixels: bytes, width: int, height: int, col: int, threshold: int) -> bool:
    """Check if a column of pixels has color variance."""
    if col >= width:
        return False

    samples = []
    for y in range(0, height, max(1, height // 10)):  # Sample ~10 points
        idx = (y * width + col) * 4
        if idx + 3 < len(pixels):
            r, g, b = pixels[idx], pixels[idx + 1], pixels[idx + 2]
            samples.append((r, g, b))

    if len(samples) < 2:
        return False

    return _color_variance(samples) > threshold


def _color_variance(colors: list) -> float:
    """Calculate variance in a list of RGB colors."""
    if len(colors) < 2:
        return 0

    # Calculate variance in R, G, B separately
    r_vals = [c[0] for c in colors]
    g_vals = [c[1] for c in colors]
    b_vals = [c[2] for c in colors]

    r_var = max(r_vals) - min(r_vals)
    g_var = max(g_vals) - min(g_vals)
    b_var = max(b_vals) - min(b_vals)

    return (r_var + g_var + b_var) / 3
