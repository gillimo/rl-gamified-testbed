from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
try:
    import agent_core
except Exception:
    agent_core = None

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes


@dataclass(frozen=True)
class WindowInfo:
    handle: int
    title: str
    bounds: Tuple[int, int, int, int]
    focused: bool


def _get_window_bounds(handle: int) -> Tuple[int, int, int, int]:
    rect = wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(handle, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def _get_window_title(handle: int) -> str:
    length = ctypes.windll.user32.GetWindowTextLengthW(handle)
    buffer = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(handle, buffer, length + 1)
    return buffer.value


def is_window_focused(handle: int) -> bool:
    if sys.platform != "win32":
        return False
    foreground = ctypes.windll.user32.GetForegroundWindow()
    return int(foreground) == int(handle)




def focus_window(handle: int, wait_ms: int = 100) -> bool:
    """Bring window to foreground and wait for it to gain focus."""
    if sys.platform != "win32":
        return False
    try:
        SW_RESTORE = 9
        ctypes.windll.user32.ShowWindow(handle, SW_RESTORE)

        target_tid = ctypes.windll.user32.GetWindowThreadProcessId(handle, None)
        current_tid = ctypes.windll.user32.GetCurrentThreadId()
        ctypes.windll.user32.AttachThreadInput(current_tid, target_tid, True)
        ctypes.windll.user32.SetForegroundWindow(handle)
        ctypes.windll.user32.BringWindowToTop(handle)
        ctypes.windll.user32.SetActiveWindow(handle)
        ctypes.windll.user32.AttachThreadInput(current_tid, target_tid, False)
        if wait_ms > 0:
            time.sleep(wait_ms / 1000.0)
        return is_window_focused(handle)
    except Exception:
        return False


def force_focus_window(handle: int, attempts: int = 3, wait_ms: int = 150) -> bool:
    """Retry focus attempts to force the window to foreground."""
    if sys.platform != "win32":
        return False
    for _ in range(max(1, attempts)):
        if is_window_focused(handle):
            return True
        focus_window(handle, wait_ms=wait_ms)
    return is_window_focused(handle)

def find_windows(title_contains: str) -> List[WindowInfo]:
    if sys.platform != "win32":
        return []

    matches: List[WindowInfo] = []
    foreground = ctypes.windll.user32.GetForegroundWindow()

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def enum_proc(handle, _param):
        if not ctypes.windll.user32.IsWindowVisible(handle):
            return True
        title = _get_window_title(handle)
        if title_contains.lower() in title.lower():
            bounds = _get_window_bounds(handle)
            focused = handle == foreground
            matches.append(WindowInfo(handle=int(handle), title=title, bounds=bounds, focused=focused))
        return True

    ctypes.windll.user32.EnumWindows(enum_proc, 0)
    return matches


def find_window(title_contains: str) -> Optional[WindowInfo]:
    matches = find_windows(title_contains)
    return matches[0] if matches else None


def capture_frame(bounds: Tuple[int, int, int, int]) -> Dict[str, Any]:
    left, top, right, bottom = bounds
    width = max(0, right - left)
    height = max(0, bottom - top)
    if width == 0 or height == 0:
        raise ValueError("bounds must be non-zero")

    start = time.perf_counter()
    image = _capture_image(bounds)
    latency_ms = int((time.perf_counter() - start) * 1000)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "bounds": {"x": left, "y": top, "width": width, "height": height},
        "image": image,
        "capture_latency_ms": latency_ms,
    }


def capture_session(
    bounds: Tuple[int, int, int, int],
    fps: float,
    duration_s: float,
    window_handle: Optional[int] = None,
) -> Dict[str, Any]:
    if fps <= 0:
        raise ValueError("fps must be > 0")
    if duration_s <= 0:
        raise ValueError("duration_s must be > 0")

    interval = 1.0 / fps
    start_time = time.perf_counter()
    frames: List[Dict[str, Any]] = []
    dropped = 0
    latency_values: List[int] = []
    focus_samples: List[bool] = []

    while True:
        now = time.perf_counter()
        if now - start_time >= duration_s:
            break

        frame = capture_frame(bounds)
        latency_values.append(frame["capture_latency_ms"])
        if window_handle is not None:
            focus_samples.append(is_window_focused(window_handle))
        frames.append(
            {
                "timestamp": frame["timestamp"],
                "capture_latency_ms": frame["capture_latency_ms"],
            }
        )
        if frame["capture_latency_ms"] > int(interval * 1000):
            dropped += 1

        elapsed = time.perf_counter() - now
        sleep_for = interval - elapsed
        if sleep_for > 0:
            time.sleep(sleep_for)

    if latency_values:
        avg_latency = sum(latency_values) / len(latency_values)
        max_latency = max(latency_values)
    else:
        avg_latency = 0
        max_latency = 0

    if focus_samples:
        focused_count = sum(1 for focused in focus_samples if focused)
    else:
        focused_count = 0

    return {
        "fps_target": fps,
        "duration_s": duration_s,
        "frames_captured": len(frames),
        "dropped_frames": dropped,
        "avg_capture_latency_ms": round(avg_latency, 2),
        "max_capture_latency_ms": max_latency,
        "focused_frames": focused_count,
        "focus_samples": focus_samples,
        "frames": frames,
    }


def _capture_image(bounds: Tuple[int, int, int, int]):
    left, top, right, bottom = bounds
    width = max(0, right - left)
    height = max(0, bottom - top)
    if agent_core is not None and width > 0 and height > 0:
        try:
            from PIL import Image
        except Exception:
            Image = None
        if Image is not None:
            try:
                data = agent_core.capture_region(left, top, width, height)
                return Image.frombytes("RGBA", (width, height), data).convert("RGB")
            except Exception:
                pass
    try:
        import mss
    except Exception:
        mss = None

    if mss is not None:
        with mss.mss() as sct:
            return sct.grab({"left": left, "top": top, "width": right - left, "height": bottom - top})

    try:
        from PIL import ImageGrab
    except Exception as exc:
        raise RuntimeError("No capture backend available. Install mss or Pillow.") from exc

    return ImageGrab.grab(bbox=(left, top, right, bottom))


def save_frame(bounds: Tuple[int, int, int, int], path: str) -> bool:
    image = _capture_image(bounds)
    try:
        if hasattr(image, "save"):
            image.save(path)
            return True
        if hasattr(image, "rgb") and hasattr(image, "size"):
            try:
                from PIL import Image
            except Exception:
                return False
            raw = Image.frombytes("RGB", image.size, image.rgb)
            raw.save(path)
            return True
    except Exception:
        return False
    return False


def _capture_window_image(handle: int):
    if sys.platform != "win32":
        return None
    try:
        from PIL import Image
    except Exception:
        return None

    rect = wintypes.RECT()
    if ctypes.windll.user32.GetWindowRect(handle, ctypes.byref(rect)) == 0:
        return None
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 0 or height <= 0:
        return None

    hwnd_dc = ctypes.windll.user32.GetWindowDC(handle)
    mem_dc = ctypes.windll.gdi32.CreateCompatibleDC(hwnd_dc)
    bmp = ctypes.windll.gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
    if not bmp:
        ctypes.windll.gdi32.DeleteDC(mem_dc)
        ctypes.windll.user32.ReleaseDC(handle, hwnd_dc)
        return None

    ctypes.windll.gdi32.SelectObject(mem_dc, bmp)
    result = ctypes.windll.user32.PrintWindow(handle, mem_dc, 0)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

    bi = BITMAPINFO()
    bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.bmiHeader.biWidth = width
    bi.bmiHeader.biHeight = -height
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    bi.bmiHeader.biCompression = 0

    buffer = ctypes.create_string_buffer(width * height * 4)
    ctypes.windll.gdi32.GetDIBits(
        mem_dc, bmp, 0, height, buffer, ctypes.byref(bi), 0
    )

    ctypes.windll.gdi32.DeleteObject(bmp)
    ctypes.windll.gdi32.DeleteDC(mem_dc)
    ctypes.windll.user32.ReleaseDC(handle, hwnd_dc)

    if result == 0:
        return None

    return Image.frombuffer("RGB", (width, height), buffer, "raw", "BGRX", 0, 1)


def save_window_frame(handle: int, path: str) -> bool:
    bounds = _get_window_bounds(handle)
    image = _capture_image(bounds)
    if image is None:
        image = _capture_window_image(handle)
    if image is None:
        return False
    try:
        image.save(path)
        return True
    except Exception:
        return False
