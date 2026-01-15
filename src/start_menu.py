import time
from pathlib import Path
from typing import Optional

from src.input_exec import (
    press_key_combo,
    press_key_name,
    press_key_name_window,
    type_text,
)
from src.perception import find_window, focus_window, is_window_focused, save_window_frame
from src.screen_hash import compute_image_hash
from src.telemetry import snapshot_name


def run_start_sequence(
    window_title: str,
    presses: int = 6,
    key: str = "START",
    hold_ms: int = 80,
    settle_ms: int = 400,
    snapshot_dir: Optional[Path] = None,
    menu_hash_path: Optional[Path] = None,
    menu_hash_threshold: int = 120,
) -> None:
    window = find_window(window_title)
    if not window:
        raise RuntimeError(f"Window not found: {window_title}")
    focused = ensure_focus(window_title)

    if snapshot_dir:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        before = snapshot_dir / snapshot_name("start_menu_before")
        save_window_frame(window.handle, str(before))

    if menu_hash_path and menu_hash_path.exists():
        if not is_start_menu(
            window_title=window_title,
            menu_hash_path=menu_hash_path,
            threshold=menu_hash_threshold,
            snapshot_dir=snapshot_dir,
        ):
            print("Start menu not detected; skipping start sequence.")
            return

    keys = [k.strip() for k in key.split(",") if k.strip()]
    if not keys:
        keys = ["START"]

    for _ in range(max(1, presses)):
        for item in keys:
            if focused:
                press_key_name(item, hold_ms=hold_ms)
        time.sleep(settle_ms / 1000.0)

    if snapshot_dir:
        after = snapshot_dir / snapshot_name("start_menu_after")
        save_window_frame(window.handle, str(after))


def load_rom(
    window_title: str,
    rom_path: Path,
    settle_ms: int = 400,
) -> None:
    if not ensure_focus(window_title):
        raise RuntimeError("Unable to focus emulator window.")

    # Open ROM dialog in BizHawk (Alt+F, then O).
    press_key_combo("ALT+F")
    time.sleep(0.2)
    press_key_name("O")
    time.sleep(0.4)

    type_text(str(rom_path))
    time.sleep(0.1)
    press_key_name("ENTER")
    time.sleep(settle_ms / 1000.0)


def turn_on(
    window_title: str,
    rom_path: Path,
    presses: int = 6,
    key: str = "START",
    hold_ms: int = 80,
    settle_ms: int = 400,
    snapshot_dir: Optional[Path] = None,
) -> None:
    load_rom(window_title=window_title, rom_path=rom_path, settle_ms=settle_ms)
    run_start_sequence(
        window_title=window_title,
        presses=presses,
        key=key,
        hold_ms=hold_ms,
        settle_ms=settle_ms,
        snapshot_dir=snapshot_dir,
    )


def ensure_focus(window_title: str) -> bool:
    window = find_window(window_title)
    if not window:
        return False
    return window.focused or is_window_focused(window.handle)


def is_start_menu(
    window_title: str,
    menu_hash_path: Path,
    threshold: int = 120,
    snapshot_dir: Optional[Path] = None,
) -> bool:
    menu_hash = _read_menu_hash(menu_hash_path)
    if not menu_hash:
        return False

    window = find_window(window_title)
    if not window:
        raise RuntimeError(f"Window not found: {window_title}")

    if snapshot_dir:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        sample_path = snapshot_dir / snapshot_name("start_menu_sample")
    else:
        sample_path = menu_hash_path.parent / "start_menu_sample.png"

    save_window_frame(window.handle, str(sample_path))
    current_hash = compute_image_hash(sample_path)
    if not current_hash:
        return False

    distance = _hash_distance(menu_hash, current_hash)
    return distance <= threshold


def calibrate_start_menu(
    window_title: str,
    menu_hash_path: Path,
    snapshot_dir: Optional[Path] = None,
) -> None:
    window = find_window(window_title)
    if not window:
        raise RuntimeError(f"Window not found: {window_title}")

    if snapshot_dir:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        sample_path = snapshot_dir / snapshot_name("start_menu_calibrate")
    else:
        sample_path = menu_hash_path.parent / "start_menu_calibrate.png"

    save_window_frame(window.handle, str(sample_path))
    current_hash = compute_image_hash(sample_path)
    if not current_hash:
        raise RuntimeError("Unable to compute start menu hash.")

    menu_hash_path.parent.mkdir(parents=True, exist_ok=True)
    menu_hash_path.write_text(current_hash, encoding="utf-8")


def _read_menu_hash(path: Path) -> Optional[str]:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    return value or None


def _hash_distance(left: str, right: str) -> int:
    try:
        left_int = int(left, 16)
        right_int = int(right, 16)
    except Exception:
        return 10**9
    value = left_int ^ right_int
    count = 0
    while value:
        value &= value - 1
        count += 1
    return count
