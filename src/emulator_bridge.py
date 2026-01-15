import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class EmulatorState:
    timestamp: str
    map_id: Optional[int]
    player_x: Optional[int]
    player_y: Optional[int]
    player_direction: Optional[int]
    in_battle: Optional[int]
    raw: Dict[str, Any]


def read_emulator_state(path: Path) -> Optional[EmulatorState]:
    target = path
    if not target.exists():
        fallback = Path(__file__).resolve().parents[1] / "tools" / "bizhawk" / "emulator_state.json"
        if fallback.exists():
            target = fallback
        else:
            return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

    return EmulatorState(
        timestamp=payload.get("timestamp", datetime.utcnow().isoformat()),
        map_id=payload.get("map_id"),
        player_x=payload.get("player_x"),
        player_y=payload.get("player_y"),
        player_direction=payload.get("player_direction"),
        in_battle=payload.get("in_battle"),
        raw=payload,
    )
