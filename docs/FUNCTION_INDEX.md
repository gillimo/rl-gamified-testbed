# Function Index (pokemon_yellow_agent)
Quick reference for finding functions. Update line numbers as code changes.
## src/app_cli.py (Main CLI)
| Line | Function | Purpose |
|------|----------|---------|
| 31 | `save_log` | Write run logs |
| 39 | `cmd_status` | Report legacy state |
| 48 | `cmd_ratings` | Report legacy ratings |
| 57 | `cmd_plan` | Report legacy plan |
| 71 | `cmd_dependencies` | Report legacy deps |
| 79 | `cmd_risk` | Report legacy risk |
| 84 | `cmd_smoke` | Smoke test emulator + bridge |
| 110 | `cmd_agent` | Run exploratory agent loop |
| 143 | `main` | Entry point |

## src/agent_loop.py
| Line | Function | Purpose |
|------|----------|---------|
| 20 | `_pick_action` | Random action helper |
| 24 | `run_agent_loop` | Loop: read state -> act -> note |

## src/emulator_bridge.py
| Line | Function | Purpose |
|------|----------|---------|
| 9 | `EmulatorState` | Emulator snapshot model |
| 19 | `read_emulator_state` | Read JSON bridge file |

## src/notes.py
| Line | Function | Purpose |
|------|----------|---------|
| 5 | `read_notes` | Read agent notes |
| 11 | `append_note` | Append a timestamped note |

## src/pokemon_memory.py
| Line | Function | Purpose |
|------|----------|---------|
| 5 | `MemoryMap` | Memory address map |

## src/telemetry.py
| Line | Function | Purpose |
|------|----------|---------|
| 7 | `append_jsonl` | Append JSONL state entries |
| 14 | `snapshot_name` | Filename helper for snapshots |

## src/perception.py
| Line | Function | Purpose |
|------|----------|---------|
| 15 | `WindowInfo` | Window metadata |
| 22 | `_get_window_bounds` | Window bounds |
| 28 | `_get_window_title` | Window title |
| 35 | `is_window_focused` | Focus check |
| 44 | `focus_window` | Focus window |
| 56 | `find_windows` | Find windows by title |
| 78 | `find_window` | Find first window match |
| 83 | `capture_frame` | Capture screen region |
| 101 | `capture_session` | Capture performance stats |
| 167 | `_capture_image` | Screen capture backend |
| 186 | `save_frame` | Save screen capture |
| 205 | `_capture_window_image` | Capture window via PrintWindow |
| 273 | `save_window_frame` | Save window capture |

## src/engine.py (Legacy Template)
| Line | Function | Purpose |
|------|----------|---------|
| - | `...` | Add functions here |

## gui/app.py (GUI)
| Line | Function | Purpose |
|------|----------|---------|
| - | `...` | Add functions here |

## Key Constants

| File | Line | Constant | Purpose |
|------|------|----------|---------|
| 5 | `POKEMON_YELLOW` | Memory addresses |

---
*Update this index when adding major functions.*
*Run: `rg -n "^(def|class) " src/*.py` to find functions.*
