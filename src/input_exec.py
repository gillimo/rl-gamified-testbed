import sys
import time
import ctypes
from ctypes import wintypes
from typing import Optional, Tuple

try:
    import agent_core
except Exception:
    agent_core = None


if sys.platform != "win32":
    raise RuntimeError("input_exec is only supported on Windows.")


PUL = ctypes.POINTER(ctypes.c_ulong)


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", PUL),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", PUL),
    ]


class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

    _anonymous_ = ("_input",)
    _fields_ = [("type", wintypes.DWORD), ("_input", _INPUT)]


INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_WHEEL = 0x0800

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def _send_input(*inputs):
    n_inputs = len(inputs)
    array_type = INPUT * n_inputs
    input_array = array_type(*inputs)
    ctypes.windll.user32.SendInput(n_inputs, ctypes.byref(input_array), ctypes.sizeof(INPUT))


def _screen_size() -> Tuple[int, int]:
    width = ctypes.windll.user32.GetSystemMetrics(0)
    height = ctypes.windll.user32.GetSystemMetrics(1)
    return width, height


def _agent_core_key_name(name: str) -> Optional[str]:
    key = name.strip().upper()
    if len(key) == 1:
        return key.lower()
    if key.startswith("F") and key[1:].isdigit():
        idx = int(key[1:])
        if 1 <= idx <= 12:
            return f"f{idx}"
        return None
    mapping = {
        "ESC": "esc",
        "ESCAPE": "esc",
        "BACKSPACE": "backspace",
        "BS": "backspace",
        "SPACE": "space",
        "SHIFT": "shift",
        "CTRL": "ctrl",
        "CONTROL": "ctrl",
        "ALT": "alt",
        "UP": "up",
        "DOWN": "down",
        "LEFT": "left",
        "RIGHT": "right",
        "ENTER": "enter",
        "RETURN": "return",
        "START": "return",
        "SELECT": "backspace",
        "TAB": "tab",
        "HOME": "home",
        "END": "end",
        "PAGEUP": "pageup",
        "PAGEDOWN": "pagedown",
        "DELETE": "delete",
        "DEL": "delete",
    }
    return mapping.get(key)


def get_cursor_pos() -> Tuple[int, int]:
    point = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return int(point.x), int(point.y)


def move_mouse(x: int, y: int) -> None:
    if agent_core is not None:
        try:
            agent_core.move_mouse(x, y)
            return
        except Exception:
            pass
    width, height = _screen_size()
    abs_x = int(x * 65535 / max(1, width - 1))
    abs_y = int(y * 65535 / max(1, height - 1))
    inp = INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(abs_x, abs_y, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0, None))
    _send_input(inp)


def move_mouse_path(
    x: int,
    y: int,
    steps: int = 30,
    curve_strength: float = 0.0,  # No curve by default
    jitter_px: float = 0.0,
    step_delay_ms: float = 8.0,
    start_jitter_px: float = 0.0,
    edge_margin_px: float = 4.0,
    speed_ramp_mode: str = "linear",
) -> None:
    """Simple smooth A-to-B mouse movement."""
    start = get_cursor_pos()
    sx, sy = start
    ex, ey = x, y

    width, height = _screen_size()
    margin = max(0.0, float(edge_margin_px))
    max_x = width - 1 - margin
    max_y = height - 1 - margin

    # Simple linear interpolation
    for i in range(steps + 1):
        t = i / steps
        # Linear interpolation
        px = sx + (ex - sx) * t
        py = sy + (ey - sy) * t

        # Clamp to screen
        clamped_x = max(margin, min(max_x, px))
        clamped_y = max(margin, min(max_y, py))

        move_mouse(int(clamped_x), int(clamped_y))
        time.sleep(step_delay_ms / 1000.0)


def click(button: str = "left", dwell_ms: Optional[float] = None, pressure_ms: Optional[float] = None) -> None:
    if agent_core is not None and dwell_ms is None and pressure_ms is None:
        try:
            time.sleep(0.02)
            agent_core.click(button)
            time.sleep(0.02)
            return
        except Exception:
            pass
    if button == "right":
        down = MOUSEEVENTF_RIGHTDOWN
        up = MOUSEEVENTF_RIGHTUP
    else:
        down = MOUSEEVENTF_LEFTDOWN
        up = MOUSEEVENTF_LEFTUP

    # Small delay before click to ensure cursor has settled
    time.sleep(0.02)

    _send_input(INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(0, 0, 0, down, 0, None)))

    # Minimum hold time for click to register (games often need this)
    hold_time = max(0.05, float(pressure_ms or 0) / 1000.0)
    if dwell_ms:
        hold_time = max(hold_time, float(dwell_ms) / 1000.0)
    time.sleep(hold_time)

    _send_input(INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(0, 0, 0, up, 0, None)))

    # Small delay after click
    time.sleep(0.02)


def scroll(amount: int) -> None:
    delta = 120 * amount
    _send_input(INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(0, 0, delta, MOUSEEVENTF_WHEEL, 0, None)))


def type_text(text: str, delay_ms: Optional[int] = None) -> None:
    if agent_core is not None and delay_ms is None:
        try:
            agent_core.type_text(text)
            return
        except Exception:
            pass
    for ch in text:
        scan = ord(ch)
        _send_input(INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(0, scan, KEYEVENTF_UNICODE, 0, None)))
        _send_input(INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(0, scan, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, None)))
        if delay_ms:
            time.sleep(delay_ms / 1000.0)


def press_key(vk_code: int, hold_ms: Optional[float] = None) -> None:
    _send_input(INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(vk_code, 0, 0, 0, None)))
    if hold_ms:
        time.sleep(float(hold_ms) / 1000.0)
    _send_input(INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(vk_code, 0, KEYEVENTF_KEYUP, 0, None)))


def _vk_from_key_name(name: str) -> Optional[int]:
    key = name.strip().upper()
    if len(key) == 1:
        return ord(key)
    if key.startswith("F") and key[1:].isdigit():
        idx = int(key[1:])
        if 1 <= idx <= 24:
            return 0x70 + (idx - 1)
    mapping = {
        "ESC": 0x1B,
        "ESCAPE": 0x1B,
        "BACKSPACE": 0x08,
        "BS": 0x08,
        "SPACE": 0x20,
        "SHIFT": 0x10,
        "CTRL": 0x11,
        "CONTROL": 0x11,
        "ALT": 0x12,
        "UP": 0x26,
        "DOWN": 0x28,
        "LEFT": 0x25,
        "RIGHT": 0x27,
        "ENTER": 0x0D,
        "RETURN": 0x0D,
        "TAB": 0x09,
        "HOME": 0x24,
        "END": 0x23,
        "PAGEUP": 0x21,
        "PAGEDOWN": 0x22,
        "DELETE": 0x2E,
        "DEL": 0x2E,
    }
    return mapping.get(key)


def press_key_combo(combo: str, hold_ms: Optional[float] = None) -> None:
    parts = [part.strip() for part in combo.split("+") if part.strip()]
    if not parts:
        return

    modifiers = []
    keys = []
    for part in parts:
        upper = part.upper()
        if upper in {"CTRL", "CONTROL", "ALT", "SHIFT"}:
            modifiers.append(upper)
        else:
            keys.append(upper)

    def keydown(vk: int) -> None:
        _send_input(INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(vk, 0, 0, 0, None)))

    def keyup(vk: int) -> None:
        _send_input(INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP, 0, None)))

    for mod in modifiers:
        vk = _vk_from_key_name(mod)
        if vk is not None:
            keydown(vk)

    for key in keys:
        vk = _vk_from_key_name(key)
        if vk is None:
            continue
        keydown(vk)
        if hold_ms:
            time.sleep(float(hold_ms) / 1000.0)
        keyup(vk)

    for mod in reversed(modifiers):
        vk = _vk_from_key_name(mod)
        if vk is not None:
            keyup(vk)


def _window_key_lparam(vk_code: int, keyup: bool = False) -> int:
    scan = ctypes.windll.user32.MapVirtualKeyW(vk_code, 0)
    lparam = 1 | (scan << 16)
    if keyup:
        lparam |= 0xC0000000
    return lparam


def press_key_window(handle: int, vk_code: int, hold_ms: Optional[float] = None) -> bool:
    """Send a key press directly to a window without requiring focus."""
    if handle <= 0:
        return False
    if not ctypes.windll.user32.PostMessageW(handle, WM_KEYDOWN, vk_code, _window_key_lparam(vk_code, False)):
        return False
    if hold_ms:
        time.sleep(float(hold_ms) / 1000.0)
    ctypes.windll.user32.PostMessageW(handle, WM_KEYUP, vk_code, _window_key_lparam(vk_code, True))
    return True


def press_key_name(name: str, hold_ms: Optional[float] = None) -> None:
    core_key = _agent_core_key_name(name)
    if agent_core is not None and core_key is not None:
        try:
            agent_core.press_key(core_key)
            if hold_ms:
                time.sleep(float(hold_ms) / 1000.0)
            return
        except Exception:
            pass
    key = name.strip().upper()
    if key.startswith("F") and key[1:].isdigit():
        idx = int(key[1:])
        if 1 <= idx <= 24:
            press_key(0x70 + (idx - 1), hold_ms=hold_ms)
            return
    if key == "ESC" or key == "ESCAPE":
        press_key(0x1B, hold_ms=hold_ms)
        return
    if key == "BACKSPACE" or key == "BS":
        press_key(0x08, hold_ms=hold_ms)
        return
    if key == "SPACE":
        press_key(0x20, hold_ms=hold_ms)
        return
    if key == "SHIFT":
        press_key(0x10, hold_ms=hold_ms)
        return
    if key == "CTRL" or key == "CONTROL":
        press_key(0x11, hold_ms=hold_ms)
        return
    if key == "ALT":
        press_key(0x12, hold_ms=hold_ms)
        return
    if key == "UP":
        press_key(0x26, hold_ms=hold_ms)
        return
    if key == "DOWN":
        press_key(0x28, hold_ms=hold_ms)
        return
    if key == "LEFT":
        press_key(0x25, hold_ms=hold_ms)
        return
    if key == "RIGHT":
        press_key(0x27, hold_ms=hold_ms)
        return
    if key == "ENTER":
        press_key(0x0D, hold_ms=hold_ms)
        return
    if key == "START":
        press_key(0x0D, hold_ms=hold_ms)
        return
    if key == "SELECT":
        press_key(0x08, hold_ms=hold_ms)
        return
    if len(key) == 1:
        press_key(ord(key), hold_ms=hold_ms)


def press_key_name_window(handle: int, name: str, hold_ms: Optional[float] = None) -> bool:
    key = name.strip().upper()
    if key.startswith("F") and key[1:].isdigit():
        idx = int(key[1:])
        if 1 <= idx <= 24:
            return press_key_window(handle, 0x70 + (idx - 1), hold_ms=hold_ms)
    if key == "ESC" or key == "ESCAPE":
        return press_key_window(handle, 0x1B, hold_ms=hold_ms)
    if key == "BACKSPACE" or key == "BS":
        return press_key_window(handle, 0x08, hold_ms=hold_ms)
    if key == "SPACE":
        return press_key_window(handle, 0x20, hold_ms=hold_ms)
    if key == "SHIFT":
        return press_key_window(handle, 0x10, hold_ms=hold_ms)
    if key == "CTRL" or key == "CONTROL":
        return press_key_window(handle, 0x11, hold_ms=hold_ms)
    if key == "ALT":
        return press_key_window(handle, 0x12, hold_ms=hold_ms)
    if key == "UP":
        return press_key_window(handle, 0x26, hold_ms=hold_ms)
    if key == "DOWN":
        return press_key_window(handle, 0x28, hold_ms=hold_ms)
    if key == "LEFT":
        return press_key_window(handle, 0x25, hold_ms=hold_ms)
    if key == "RIGHT":
        return press_key_window(handle, 0x27, hold_ms=hold_ms)
    if key == "ENTER":
        return press_key_window(handle, 0x0D, hold_ms=hold_ms)
    if key == "START":
        return press_key_window(handle, 0x0D, hold_ms=hold_ms)
    if key == "SELECT":
        return press_key_window(handle, 0x08, hold_ms=hold_ms)
    if len(key) == 1:
        return press_key_window(handle, ord(key), hold_ms=hold_ms)
    return False


def drag(start: Tuple[int, int], end: Tuple[int, int], hold_ms: Optional[int] = None) -> None:
    move_mouse(start[0], start[1])
    _send_input(INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, None)))
    if hold_ms:
        time.sleep(hold_ms / 1000.0)
    move_mouse(end[0], end[1])
    _send_input(INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, None)))
