import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

from src.engine import (
    load_json,
    validate_state,
    migrate_state,
    compute_ratings,
    detect_bottlenecks,
    build_dependency_graph,
    generate_plan,
    compare_paths,
    risk_score,
)
from src.agent_loop import run_agent_loop
from src.emulator_bridge import read_emulator_state
from src.notes import append_note
from src.perception import find_window, force_focus_window, save_frame, save_window_frame
from src.telemetry import snapshot_name
from src.start_menu import (
    calibrate_start_menu,
    is_start_menu,
    load_rom,
    run_start_sequence,
    turn_on,
)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
STATE_PATH = DATA_DIR / "state.json"
EMU_STATE_PATH = DATA_DIR / "emulator_state.json"
NOTES_PATH = DATA_DIR / "agent_notes.md"
LOGS_DIR = ROOT / "logs"
AGENT_CORE_DIR = Path(r"C:\Users\gilli\OneDrive\Desktop\agent_core")


def save_log(message):
    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"run_{stamp}.log"
    log_path.write_text(message, encoding="utf-8")


def cmd_status(state):
    account = state.get("account", {})
    skills = state.get("skills", {})
    print("Status")
    print(f"- Name: {account.get('name', 'Unknown')}")
    print(f"- Mode: {account.get('mode', 'main')}")
    print(f"- Avg skill: {sum(skills.values())/max(1, len(skills)) if skills else 0:.1f}")


def cmd_ratings(state):
    ratings, reasons = compute_ratings(state)
    print("Ratings")
    for k, v in ratings.items():
        print(f"- {k.replace('_', ' ').title()}: {v}/100")
        for r in reasons.get(k, [])[:3]:
            print(f"  reason: {r}")


def cmd_plan(state):
    plan = generate_plan(state)
    print("Plan")
    for horizon in ["short", "mid", "long"]:
        print(f"{horizon.title()} horizon:")
        for idx, item in enumerate(plan.get(horizon, []), start=1):
            prereqs = ", ".join(item.get("prereqs", [])) or "none"
            print(f" {idx}) {item.get('task')} ({item.get('time')})")
            print(f"    why: {item.get('why')}; prereqs: {prereqs}")
    print("Alternate paths:")
    for opt in compare_paths(state):
        print(f"- {opt['path']}: {opt['tradeoff']} ({opt['notes']})")


def cmd_dependencies(state):
    graph = build_dependency_graph(state)
    print("Dependencies")
    for node, reqs in graph.items():
        if reqs:
            print(f"- {node}: {', '.join(reqs)}")


def cmd_risk(state):
    print(f"Risk score: {risk_score(state)}/100")
    print(f"Bottlenecks: {', '.join(detect_bottlenecks(state))}")


def cmd_smoke(window_title: str, emu_state: Path, notes_path: Path) -> None:
    window = find_window(window_title)
    if not window:
        print(f"Window not found: {window_title}")
    else:
        focused = window.focused or force_focus_window(window.handle)
        print(f"Window: {window.title} focused={focused}")
        LOGS_DIR.mkdir(exist_ok=True)
        snapshot_path = LOGS_DIR / snapshot_name("smoke")
        if save_window_frame(window.handle, str(snapshot_path)) or save_frame(
            window.bounds, str(snapshot_path)
        ):
            print(f"Saved snapshot: {snapshot_path}")

    state = read_emulator_state(emu_state)
    if state:
        print(
            "Emulator state: "
            f"map={state.map_id} pos=({state.player_x},{state.player_y}) battle={state.in_battle}"
        )
        append_note(notes_path, "Smoke test: emulator state read successfully.")
    else:
        print(f"Emulator state missing or unreadable: {emu_state}")
        append_note(notes_path, "Smoke test: emulator state missing or unreadable.")


def cmd_agent(
    window_title: str,
    emu_state: Path,
    notes_path: Path,
    steps: int,
    log_state: bool,
    snapshot_every_n: int,
    no_move_limit: int,
    backoff_ms: int,
    hold_ms: int,
    settle_ms: int,
    actions_csv: str,
) -> None:
    log_path = None
    action_log_path = None
    snapshot_dir = None
    if log_state:
        LOGS_DIR.mkdir(exist_ok=True)
        log_path = LOGS_DIR / "emulator_state_log.jsonl"
        action_log_path = LOGS_DIR / "agent_action_log.jsonl"
    if snapshot_every_n > 0:
        snapshot_dir = LOGS_DIR / "snapshots"
    actions = None
    if actions_csv:
        actions = [item.strip() for item in actions_csv.split(",") if item.strip()]
    ocr_log_path = LOGS_DIR / "ocr_text.jsonl"
    run_agent_loop(
        state_path=emu_state,
        notes_path=notes_path,
        window_title=window_title,
        steps=steps,
        hold_ms=hold_ms,
        settle_ms=settle_ms,
        actions=actions,
        log_path=log_path,
        action_log_path=action_log_path,
        snapshot_dir=snapshot_dir,
        snapshot_every_n=snapshot_every_n,
        no_move_limit=no_move_limit,
        backoff_ms=backoff_ms,
        ocr_log_path=ocr_log_path,
    )


def build_agent_core() -> None:
    if not AGENT_CORE_DIR.exists():
        print(f"agent_core project not found: {AGENT_CORE_DIR}")
        return
    try:
        subprocess.run(
            [sys.executable, "-m", "maturin", "develop", "--release"],
            cwd=str(AGENT_CORE_DIR),
            check=True,
        )
    except FileNotFoundError:
        print("Python executable not found; cannot build agent_core.")
    except subprocess.CalledProcessError:
        print("agent_core build failed.")


def main():
    parser = argparse.ArgumentParser(description="pokemon_yellow_agent CLI")    
    parser.add_argument("command", nargs="?", default="status")
    parser.add_argument("--state", default=str(STATE_PATH))
    parser.add_argument("--emu-state", default=str(EMU_STATE_PATH))
    parser.add_argument("--notes", default=str(NOTES_PATH))
    parser.add_argument("--window", default="BizHawk")
    parser.add_argument("--steps", type=int, default=25)
    parser.add_argument("--log-state", action="store_true")
    parser.add_argument("--snapshot-every", type=int, default=5)
    parser.add_argument("--no-move-limit", type=int, default=8)
    parser.add_argument("--backoff-ms", type=int, default=1200)
    parser.add_argument("--hold-ms", type=int, default=60)
    parser.add_argument("--settle-ms", type=int, default=200)
    parser.add_argument("--actions", default="")
    parser.add_argument("--start-presses", type=int, default=6)
    parser.add_argument("--start-key", default="START")
    parser.add_argument("--start-hold-ms", type=int, default=80)
    parser.add_argument("--start-settle-ms", type=int, default=400)
    parser.add_argument("--start-snapshots", action="store_true")
    parser.add_argument("--start-detect", action="store_true")
    parser.add_argument("--start-threshold", type=int, default=120)
    parser.add_argument("--rom", default="")
    parser.add_argument("--turnon-agent-steps", type=int, default=0)
    parser.add_argument("--build-agent-core", action="store_true")
    args = parser.parse_args()

    state_path = Path(args.state)
    emu_state_path = Path(args.emu_state)
    notes_path = Path(args.notes)

    cmd = args.command.lower()
    if cmd in {"status", "ratings", "plan", "deps", "risk"}:
        state = load_json(state_path, {})
        if not state:
            print("State file missing or empty. Edit data/state.json first.")
            return
        state = migrate_state(state)
        errors = validate_state(state)
        if errors:
            print("State validation errors:")
            for e in errors:
                print(f"- {e}")
            return

    if cmd == "status":
        cmd_status(state)
    elif cmd == "ratings":
        cmd_ratings(state)
    elif cmd == "plan":
        cmd_plan(state)
    elif cmd == "deps":
        cmd_dependencies(state)
    elif cmd == "risk":
        cmd_risk(state)
    elif cmd == "smoke":
        cmd_smoke(args.window, emu_state_path, notes_path)
    elif cmd == "agent":
        cmd_agent(
            args.window,
            emu_state_path,
            notes_path,
            args.steps,
            args.log_state,
            args.snapshot_every,
            args.no_move_limit,
            args.backoff_ms,
            args.hold_ms,
            args.settle_ms,
            args.actions,
        )
    elif cmd == "start":
        snapshot_dir = None
        if args.start_snapshots:
            snapshot_dir = LOGS_DIR / "snapshots"
        menu_hash_path = DATA_DIR / "start_menu_hash.txt"
        run_start_sequence(
            window_title=args.window,
            presses=args.start_presses,
            key=args.start_key,
            hold_ms=args.start_hold_ms,
            settle_ms=args.start_settle_ms,
            snapshot_dir=snapshot_dir,
            menu_hash_path=(menu_hash_path if args.start_detect else None),
            menu_hash_threshold=args.start_threshold,
        )
    elif cmd == "loadrom":
        if not args.rom:
            print("Missing --rom path.")
            return
        load_rom(
            window_title=args.window,
            rom_path=Path(args.rom),
            settle_ms=args.start_settle_ms,
        )
    elif cmd == "turnon":
        if not args.rom:
            print("Missing --rom path.")
            return
        snapshot_dir = None
        if args.start_snapshots:
            snapshot_dir = LOGS_DIR / "snapshots"
        if args.build_agent_core:
            build_agent_core()
        turn_on(
            window_title=args.window,
            rom_path=Path(args.rom),
            presses=args.start_presses,
            key=args.start_key,
            hold_ms=args.start_hold_ms,
            settle_ms=args.start_settle_ms,
            snapshot_dir=snapshot_dir,
        )
        if args.turnon_agent_steps > 0:
            cmd_agent(
                args.window,
                emu_state_path,
                notes_path,
                args.turnon_agent_steps,
                args.log_state,
                args.snapshot_every,
                args.no_move_limit,
                args.backoff_ms,
                args.hold_ms,
                args.settle_ms,
                args.actions,
            )
    elif cmd == "menucalibrate":
        snapshot_dir = None
        if args.start_snapshots:
            snapshot_dir = LOGS_DIR / "snapshots"
        menu_hash_path = DATA_DIR / "start_menu_hash.txt"
        calibrate_start_menu(
            window_title=args.window,
            menu_hash_path=menu_hash_path,
            snapshot_dir=snapshot_dir,
        )
        print(f"Saved start menu hash to {menu_hash_path}")
    elif cmd == "menustatus":
        menu_hash_path = DATA_DIR / "start_menu_hash.txt"
        snapshot_dir = None
        if args.start_snapshots:
            snapshot_dir = LOGS_DIR / "snapshots"
        detected = is_start_menu(
            window_title=args.window,
            menu_hash_path=menu_hash_path,
            threshold=args.start_threshold,
            snapshot_dir=snapshot_dir,
        )
        print(f"Start menu detected: {detected}")
    else:
        print("Unknown command. Try: status, ratings, plan, deps, risk, smoke, agent, start, loadrom, turnon, menucalibrate, menustatus")

    save_log(f"Command: {cmd}\n")


if __name__ == "__main__":
    main()
