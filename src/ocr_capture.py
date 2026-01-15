"""Window-targeted OCR capture with suppression rules for battle text."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

try:
    import agent_core
except ImportError:
    agent_core = None

from src.telemetry import append_jsonl

DEFAULT_WINDOW_PARTS = ["bizhawk", "yellow"]
DEFAULT_SUPPRESS = {
    "keywords": ["fight", "pkmn", "run", "hp", "lv", "pp", "bag"],
    "min_keyword_hits": 1,
    "case_insensitive": True,
    # Rough HP bar green detection; tune min_count as needed.
    "color": {"r": 0, "g": 200, "b": 0, "tolerance": 40, "min_count": 500},
}


def record_non_battle_text(
    window_parts: Optional[List[str]] = None,
    suppress: Optional[Dict] = None,
    log_path: Optional[Path] = None,
) -> Optional[Dict]:
    if agent_core is None:
        return None
    parts = window_parts or DEFAULT_WINDOW_PARTS
    cfg = suppress or DEFAULT_SUPPRESS

    response = agent_core.ocr_window_full_all_record(parts, json.dumps(cfg))
    payload = json.loads(response)

    if log_path:
        append_jsonl(
            log_path,
            {
                "text": payload.get("text"),
                "recorded": payload.get("recorded"),
                "suppressed": payload.get("suppressed"),
                "reasons": payload.get("reasons"),
                "keyword_hits": payload.get("keyword_hits"),
                "color_hits": payload.get("color_hits"),
                "window_title": payload.get("window_title"),
            },
        )

    return payload
