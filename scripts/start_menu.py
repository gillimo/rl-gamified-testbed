import argparse
from pathlib import Path

from src.start_menu import run_start_sequence


def main() -> None:
    parser = argparse.ArgumentParser(description="Press through the start menu")
    parser.add_argument("--window", default="BizHawk")
    parser.add_argument("--presses", type=int, default=6)
    parser.add_argument("--key", default="START")
    parser.add_argument("--hold-ms", type=int, default=80)
    parser.add_argument("--settle-ms", type=int, default=400)
    parser.add_argument("--snapshots", action="store_true")
    args = parser.parse_args()

    snapshot_dir = None
    if args.snapshots:
        root = Path(__file__).resolve().parents[1]
        snapshot_dir = root / "logs" / "snapshots"

    run_start_sequence(
        window_title=args.window,
        presses=args.presses,
        key=args.key,
        hold_ms=args.hold_ms,
        settle_ms=args.settle_ms,
        snapshot_dir=snapshot_dir,
    )


if __name__ == "__main__":
    main()
