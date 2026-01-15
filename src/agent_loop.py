import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from src.emulator_bridge import read_emulator_state
from src.input_exec import press_key_name, press_key_name_window, move_mouse, click
from src.notes import append_note
from src.ocr_capture import record_non_battle_text
from src.perception import (
    find_window,
    force_focus_window,
    is_window_focused,
    save_frame,
    save_window_frame,
)
from src.screen_hash import compute_image_hash
from src.telemetry import append_jsonl, snapshot_name
from src.timing import TimingProfile, sample_reaction_ms, sample_inter_action_ms


def _pick_action(phase: str) -> str:
    if phase == "boot":
        return random.choice(["ENTER", "START", "Z"])
    if phase == "dialogue":
        return random.choice(["Z", "Z", "X", "ENTER"])
    if phase == "explore":
        return random.choice(
            ["UP", "DOWN", "LEFT", "RIGHT", "UP", "DOWN", "LEFT", "RIGHT", "Z", "X"]
        )
    return random.choice(["UP", "DOWN", "LEFT", "RIGHT", "Z", "X", "ENTER"])


def _phase_for_state(state, no_move_streak: int) -> str:
    if not state:
        return "unknown"
    if state.in_battle:
        return "battle"
    if state.map_id == 0 and state.player_x == 0 and state.player_y == 0:
        return "boot"
    if no_move_streak >= 3:
        return "dialogue"
    return "explore"


def run_agent_loop(
    state_path: Path,
    notes_path: Path,
    window_title: str,
    steps: int = 25,
    hold_ms: int = 60,
    settle_ms: int = 200,
    actions: Optional[List[str]] = None,
    log_path: Optional[Path] = None,
    action_log_path: Optional[Path] = None,
    snapshot_dir: Optional[Path] = None,
    snapshot_every_n: int = 5,
    no_move_limit: int = 8,
    backoff_ms: int = 1200,
    ocr_log_path: Optional[Path] = None,
) -> None:
    timing_profile = TimingProfile.NORMAL
    window = find_window(window_title)
    if not window:
        raise RuntimeError(f"Window not found: {window_title}")

    if not window.focused:
        if not force_focus_window(window.handle):
            append_note(notes_path, "Warning: initial focus failed.")

    action_pool = actions or ["UP", "DOWN", "LEFT", "RIGHT", "Z", "X", "ENTER"]

    append_note(notes_path, "Starting agent loop.")
    no_move_streak = 0
    visual_streak = 0
    last_state = None
    last_snapshot_hash = None
    for idx in range(steps):
        state = read_emulator_state(state_path)
        state_age_s = None
        state_stale = False
        if state:
            try:
                state_time = datetime.fromisoformat(state.timestamp.replace("Z", "+00:00"))
                state_age_s = (datetime.now(timezone.utc) - state_time).total_seconds()
                state_stale = state_age_s > 2.0
            except Exception:
                state_age_s = None
                state_stale = False
            append_note(
                notes_path,
                f"step {idx + 1}: map={state.map_id} pos=({state.player_x},{state.player_y}) battle={state.in_battle}",
            )
            if log_path:
                append_jsonl(
                    log_path,
                    {
                        "timestamp": state.timestamp,
                        "step": idx + 1,
                        "map_id": state.map_id,
                        "player_x": state.player_x,
                        "player_y": state.player_y,
                        "player_direction": state.player_direction,
                        "in_battle": state.in_battle,
                    },
                )
        if state_stale:
            append_note(notes_path, "State stale; skipping input to avoid desync.")
            if action_log_path:
                append_jsonl(
                    action_log_path,
                    {
                        "step": idx + 1,
                        "event": "state_stale",
                        "state_age_s": state_age_s,
                    },
                )
            time.sleep(0.5)
            continue

        phase = _phase_for_state(state, no_move_streak)
        if phase == "battle":
            append_note(notes_path, "Battle detected. Stopping loop.")
            if action_log_path:
                append_jsonl(
                    action_log_path,
                    {"step": idx + 1, "event": "battle_detected"},
                )
            break

        action = _pick_action(phase) if actions is None else random.choice(action_pool)
        focus_ok = True
        input_method = "send_input"
        if not is_window_focused(window.handle):
            focus_ok = force_focus_window(window.handle)
            if not focus_ok:
                left, top, right, bottom = window.bounds
                target_x = int((left + right) / 2)
                target_y = int((top + bottom) / 2)
                move_mouse(target_x, target_y)
                click("left")
                time.sleep(0.1)
                focus_ok = is_window_focused(window.handle)

        if focus_ok:
            press_key_name(action, hold_ms=hold_ms)
        else:
            input_method = "window_message"
            if not press_key_name_window(window.handle, action, hold_ms=hold_ms):
                append_note(notes_path, "Skipped action due to input failure.")
                if action_log_path:
                    append_jsonl(
                        action_log_path,
                        {
                            "step": idx + 1,
                            "action": action,
                            "focus_ok": False,
                            "skipped": True,
                            "input_method": input_method,
                        },
                    )
                continue

        time.sleep(sample_reaction_ms(timing_profile) / 1000.0)
        time.sleep(sample_inter_action_ms(timing_profile) / 1000.0)
        time.sleep(settle_ms / 1000.0)

        next_state = read_emulator_state(state_path)
        moved = False
        if state and next_state:
            moved = (
                state.map_id != next_state.map_id
                or state.player_x != next_state.player_x
                or state.player_y != next_state.player_y
            )
        if moved:
            no_move_streak = 0
        else:
            no_move_streak += 1

        snapshot_path = None
        snapshot_hash = None
        if snapshot_dir and snapshot_every_n > 0 and (idx + 1) % snapshot_every_n == 0:
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            snapshot_path = snapshot_dir / snapshot_name("agent_step")
            if not save_window_frame(window.handle, str(snapshot_path)):
                save_frame(window.bounds, str(snapshot_path))
            if snapshot_path.exists():
                snapshot_hash = compute_image_hash(snapshot_path)
                if snapshot_hash == last_snapshot_hash:
                    visual_streak += 1
                else:
                    visual_streak = 0
                last_snapshot_hash = snapshot_hash

        if ocr_log_path:
            record_non_battle_text(log_path=ocr_log_path)

        if action_log_path:
            append_jsonl(
                action_log_path,
                {
                    "timestamp": (next_state.timestamp if next_state else None),
                    "step": idx + 1,
                    "action": action,
                    "focus_ok": focus_ok,
                    "input_method": input_method,
                    "phase": phase,
                    "state_age_s": state_age_s,
                    "state_stale": state_stale,
                    "state_before": {
                        "map_id": (state.map_id if state else None),
                        "player_x": (state.player_x if state else None),
                        "player_y": (state.player_y if state else None),
                        "player_direction": (state.player_direction if state else None),
                        "in_battle": (state.in_battle if state else None),
                    },
                    "state_after": {
                        "map_id": (next_state.map_id if next_state else None),
                        "player_x": (next_state.player_x if next_state else None),
                        "player_y": (next_state.player_y if next_state else None),
                        "player_direction": (next_state.player_direction if next_state else None),
                        "in_battle": (next_state.in_battle if next_state else None),
                    },
                    "moved": moved,
                    "no_move_streak": no_move_streak,
                    "visual_streak": visual_streak,
                    "snapshot_path": str(snapshot_path) if snapshot_path else None,
                    "snapshot_hash": snapshot_hash,
                },
            )

        if no_move_streak >= no_move_limit:
            append_note(notes_path, f"Backoff triggered after {no_move_streak} no-move steps.")
            time.sleep(backoff_ms / 1000.0)

    append_note(notes_path, "Agent loop complete.")
