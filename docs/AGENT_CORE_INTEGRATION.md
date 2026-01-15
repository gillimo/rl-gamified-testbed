# Agent Core Integration Guide

> **agent_core** is a high-performance Rust library providing screen capture, color detection, and input control for Python agents.

**Status:** v0.1.1 - Ready for use
**Source:** `C:\Users\gilli\OneDrive\Desktop\agent_core`

---

## Quick Start

### Installation

```bash
# Activate the venv that has agent_core installed
C:\Users\gilli\.venv\Scripts\activate

# Or use the venv Python directly
C:\Users\gilli\.venv\Scripts\python.exe your_script.py
```

If you need to rebuild:
```bash
cd C:\Users\gilli\OneDrive\Desktop\agent_core
python -m maturin develop --release
```

### Basic Usage

```python
import agent_core

# Capture the screen
width, height, frame = agent_core.capture_screen()
print(f"Captured {width}x{height} screen")

# Find yellow pixels (Pokemon Yellow uses yellow heavily!)
yellow_pixels = agent_core.detect_color(frame, width, height, 255, 255, 0, 30)

# Click somewhere
agent_core.click("left", 500, 300)

# Press a button
agent_core.press_key("Return")
```

---

## Current Capabilities (v0.1.1)

### The Eye - Vision Functions

| Function | Signature | Description | Returns |
|----------|-----------|-------------|---------|
| `capture_screen` | `()` | Capture full primary monitor | `(width, height, rgba_bytes)` |
| `capture_region` | `(x, y, width, height)` | Capture specific screen region | `rgba_bytes` |
| `detect_color` | `(data, w, h, r, g, b, tolerance)` | Find all pixels matching RGB within tolerance | `[(x, y), ...]` |
| `detect_arrow` | `(data, w, h)` | Find yellow arrow/marker | `(x, y, confidence)` or `None` |
| `detect_highlight` | `(data, w, h)` | Find cyan/turquoise highlight | `(x, y, confidence)` or `None` |

### OCR + Window Targeting

| Function | Signature | Description | Returns |
|----------|-----------|-------------|---------|
| `ocr_region` | `(data, w, h, x, y, width, height)` | OCR a region from an RGBA frame | `text` |
| `ocr_regions` | `(data, w, h, regions)` | OCR multiple regions | `[text, ...]` |
| `ocr_window_full` | `(title_contains)` | Focus window and OCR full window | `text` |
| `ocr_window_region` | `(title_contains, x, y, w, h)` | Focus window and OCR region | `text` |
| `ocr_window_full_all` | `([title_parts])` | Focus window matching all fragments | `text` |
| `ocr_window_region_all` | `([title_parts], x, y, w, h)` | Focus + OCR region by fragments | `text` |
| `ocr_window_full_all_record` | `([title_parts], suppress_json)` | OCR + record non-battle text | `json string` |

### The Hand - Input Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `move_mouse` | `(x, y)` | Move cursor to absolute screen position |
| `click` | `(button, x=None, y=None)` | Click mouse button ("left", "right", "middle") |
| `type_text` | `(text)` | Type a string of characters |
| `press_key` | `(key)` | Press a key by name |

**Supported Keys for `press_key`:**
- Navigation: `up`, `down`, `left`, `right`, `home`, `end`, `pageup`, `pagedown`
- Actions: `return`, `enter`, `escape`, `esc`, `tab`, `space`, `backspace`, `delete`
- Function: `f1` through `f12`
- Modifiers: `shift`, `control`, `ctrl`, `alt`
- Any single character: `a`, `b`, `1`, `2`, etc.

### Utilities

| Function | Signature | Description |
|----------|-----------|-------------|
| `map_coordinates` | `(ai_x, ai_y, ai_w, ai_h, screen_w, screen_h)` | Scale coordinates from AI space to screen space |
| `version` | `()` | Returns library version string |
| `validate_action_intent` | `(action_json)` | Validate action intent JSON | `json string` |
| `validate_snapshot` | `(snapshot_json)` | Validate observation JSON | `json string` |
| `get_recorded_text` | `(limit=None)` | Return recorded OCR lines | `[text, ...]` |
| `clear_recorded_text` | `()` | Clear recorded OCR buffer | `None` |

---

## Pokemon Yellow Integration Examples

### Example 1: Capture Game Window Region

```python
import agent_core

# Assuming emulator window is at known position
# Adjust these to match your emulator window location
EMU_X = 100
EMU_Y = 100
EMU_WIDTH = 640
EMU_HEIGHT = 576

def capture_game():
    """Capture just the game window"""
    frame = agent_core.capture_region(EMU_X, EMU_Y, EMU_WIDTH, EMU_HEIGHT)
    return frame, EMU_WIDTH, EMU_HEIGHT

frame, w, h = capture_game()
```

### Example 2: Detect Yellow Elements (Pikachu, Menus, HP Bar)

```python
import agent_core

def find_yellow_elements(frame, width, height):
    """Find yellow pixels - useful for Pikachu, menu highlights, etc."""
    # Pokemon Yellow's yellow: RGB(248, 208, 48) approximately
    # Use tolerance to catch variations
    yellows = agent_core.detect_color(frame, width, height, 248, 208, 48, 40)
    return yellows

def find_pikachu_yellow(frame, width, height):
    """Pikachu's specific yellow shade"""
    return agent_core.detect_color(frame, width, height, 248, 216, 56, 30)

# Get centroid of yellow region
def get_yellow_centroid(frame, width, height):
    yellows = find_yellow_elements(frame, width, height)
    if not yellows:
        return None
    avg_x = sum(p[0] for p in yellows) // len(yellows)
    avg_y = sum(p[1] for p in yellows) // len(yellows)
    return (avg_x, avg_y)
```

### Example 3: Detect Red HP Bar

```python
import agent_core

def find_hp_bar_red(frame, width, height):
    """Find red HP bar pixels"""
    # Pokemon Red/Yellow HP bar red: approximately RGB(248, 56, 32)
    return agent_core.detect_color(frame, width, height, 248, 56, 32, 30)

def find_hp_bar_green(frame, width, height):
    """Find green HP bar pixels (healthy)"""
    return agent_core.detect_color(frame, width, height, 112, 248, 56, 30)
```

### Example 4: Press Game Buttons

```python
import agent_core
import time

def press_a():
    """Press A button (mapped to Z or Enter typically)"""
    agent_core.press_key("z")  # Common emulator mapping
    time.sleep(0.1)

def press_b():
    """Press B button (mapped to X typically)"""
    agent_core.press_key("x")
    time.sleep(0.1)

def press_start():
    """Press Start button"""
    agent_core.press_key("return")
    time.sleep(0.1)

def move_dpad(direction):
    """Move D-pad: up, down, left, right"""
    agent_core.press_key(direction)
    time.sleep(0.1)

def hold_direction(direction, duration=0.5):
    """Hold a direction for walking"""
    # For now, press multiple times
    presses = int(duration / 0.1)
    for _ in range(presses):
        agent_core.press_key(direction)
        time.sleep(0.1)
```

### Example 5: Full Capture + Detect + Act Loop

```python
import agent_core
import time

EMU_X, EMU_Y = 100, 100
EMU_W, EMU_H = 640, 576

def game_loop():
    while True:
        # 1. Capture
        frame = agent_core.capture_region(EMU_X, EMU_Y, EMU_W, EMU_H)

        # 2. Detect
        yellows = agent_core.detect_color(frame, EMU_W, EMU_H, 248, 208, 48, 40)

        # 3. Analyze
        if len(yellows) > 100:
            print(f"Yellow detected: {len(yellows)} pixels")
            # Could be menu, Pikachu, etc.

        # 4. Act (example: press A if lots of yellow)
        if len(yellows) > 500:
            agent_core.press_key("z")  # Press A

        time.sleep(0.1)  # 10 FPS loop

# game_loop()
```

---

### Example 3: Record Non-Battle OCR Text (BizHawk + Yellow)

```python
import json
import agent_core

window_parts = ["bizhawk", "yellow"]
suppress = {
    "keywords": ["fight", "pkmn", "run", "hp", "lv", "pp", "bag"],
    "min_keyword_hits": 1,
    "case_insensitive": True,
    "color": {"r": 0, "g": 200, "b": 0, "tolerance": 40, "min_count": 500},
}

result = agent_core.ocr_window_full_all_record(window_parts, json.dumps(suppress))
print(result)
```

## Performance Characteristics

| Operation | Typical Latency | Notes |
|-----------|-----------------|-------|
| `capture_screen()` | 10-30ms | Full screen RGBA capture |
| `capture_region()` | 5-15ms | Depends on region size |
| `detect_color()` | 5-15ms | Parallel via Rayon, scales with image size |
| `detect_arrow()` | 5-10ms | Optimized for yellow detection |
| `move_mouse()` | <1ms | Direct Windows API |
| `click()` | <5ms | Includes brief delay |
| `press_key()` | <5ms | Direct input |

**Throughput:** Can achieve 30-60 FPS capture+detect loops depending on screen size and detection complexity.

---

## What's Coming (Roadmap)

### v0.2.0 - Humanization (Planned)
- **Timing Profiles**: Natural delays between actions (reaction time, dwell time)
- **Mouse Pathing**: Bezier curve movement instead of instant jumps
- **Presets**: NORMAL, FAST, SLOW, CAREFUL timing presets
- **Jitter/Tremor**: Micro-movements for natural mouse behavior

```python
# Future API (not yet available)
agent_core.set_timing_profile("NORMAL")
agent_core.move_mouse_human(500, 300)  # Bezier path with natural timing
```

### v0.3.0 - Advanced Detection (Planned)
- **Template Matching**: Find sprites/icons by reference image

```python
# Future API (not yet available)
matches = agent_core.find_template(frame, template_image)
```

### v0.4.0 - Hardware & Optimization (Planned)
- **Hardware Detection**: Auto-detect DPI, refresh rate
- **SIMD Optimization**: Faster color detection
- **Delta Detection**: Only process changed screen regions

### v1.0.0 - Full Agent Support (Planned)
- **Action Intents**: Expanded schema coverage + stricter validation
- **Pipeline Timing**: Budget enforcement for real-time loops
- **Multi-monitor**: Support for multiple displays

---

## Architecture Notes

```
┌─────────────────────────────────────────────────────┐
│                    Python Agent                      │
│              (pokemon_yellow_agent)                  │
└─────────────────────┬───────────────────────────────┘
                      │ import agent_core
                      ▼
┌─────────────────────────────────────────────────────┐
│                   agent_core                         │
│                  (Rust + PyO3)                       │
├─────────────────┬─────────────────┬─────────────────┤
│   The Eye       │   The Hand      │   Utilities     │
│   (Vision)      │   (Input)       │                 │
├─────────────────┼─────────────────┼─────────────────┤
│ capture_screen  │ move_mouse      │ map_coordinates │
│ capture_region  │ click           │ version         │
│ detect_color    │ type_text       │                 │
│ detect_arrow    │ press_key       │                 │
│ detect_highlight│                 │                 │
└─────────────────┴─────────────────┴─────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│              Native Windows APIs                     │
│         (xcap, enigo, Windows SendInput)            │
└─────────────────────────────────────────────────────┘
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'agent_core'"
Use the correct Python environment:
```bash
C:\Users\gilli\.venv\Scripts\python.exe your_script.py
```

### Capture returns wrong screen region
Check your monitor setup. `capture_screen()` uses the primary monitor. For multi-monitor, use `capture_region()` with exact coordinates.

### Keys not registering in emulator
- Make sure the emulator window has focus
- Some emulators need DirectInput - try running as administrator
- Check emulator key mappings match what you're sending

### Color detection finds nothing
- Check RGB values match your target (use a color picker tool)
- Increase tolerance (try 40-50)
- Verify frame data is correct size: `len(frame) == width * height * 4`

---

## Related Resources

- **agent_core source**: `C:\Users\gilli\OneDrive\Desktop\agent_core`
- **AgentOSRS reference**: `C:\Users\gilli\OneDrive\Desktop\projects\agentosrs` (more complex patterns)
- **Ollama models**: `ollama list` - moondream available for vision tasks

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.1 | 2026-01-15 | OCR + window targeting, JSON validation, record buffer |
| 0.1.0 | 2025-01-14 | Initial MVP - capture, detect, input |

---

*This document will be updated as agent_core evolves. Check version() to confirm your installed version.*

---

## Vision Models (Local)

Vision-language reasoning is handled via `src/local_model.py` (Ollama/Moondream).
This is separate from the agent_core Python API.
