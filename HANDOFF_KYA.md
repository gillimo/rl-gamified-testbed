# Pokemon Yellow Agent - Handoff Summary for Kya

**Date:** 2026-01-15
**Status:** Ready for Implementation
**Current Branch:** master

---

## Current Situation

### Problem
The Pokemon Yellow agent is **stuck** and not progressing:
- **Position frozen:** `map: 18, pos: (0,3)` for 15+ steps
- **Can't read text:** Moondream hallucinates instead of reading Game Boy dialogue
- **Random actions:** Defaults to UP/RIGHT without understanding context
- **No goals:** No short-term or medium-term objective tracking

### Root Cause
Moondream is receiving vague prompts and cannot read small pixel Game Boy text, so it's making up descriptions like "Windows Start menu" and "Minecraft code".

---

## Solution: OCR + Hierarchical Goals

### What We're Adding

1. **OCR Text Reading (Tesseract)**
   - Already built into agent_core, just needs Python exposure
   - Will read actual dialogue: "Welcome to the world of Pokemon!"
   - Faster than vision (~1s vs 60-90s)

2. **Hierarchical Goal Tracking (Phi3)**
   - Medium-term: "Complete intro sequence and get starter Pokemon"
   - Short-term: "Advance dialogue by pressing A"
   - Goals update as agent progresses

3. **Stuck Detection**
   - Detects when position/text frozen for 3+ steps
   - Automatically tries recovery (press A for dialogue, B to back out)

---

## Implementation Plan

### Tickets (in order)
All tickets documented in `agent_core/docs/TICKETS.md`

#### **T-011: OCR Python API Exposure** (agent_core)
**Status:** Not Started
**Estimated Time:** 10 minutes

**Files to Edit:**
1. `agent_core/python/agent_core/__init__.py`
   - Add: `ocr_region = _core.ocr_region`
   - Add: `ocr_regions = _core.ocr_regions`
   - Add: `ocr_window_full = _core.ocr_window_full`

2. `agent_core/python/agent_core/models.py`
   - Add `TextReader` class (see plan for full code)
   - Update `Spotter.see()` to accept `ocr_text` parameter

**Result:** Python code can now call `agent_core.ocr_region()` directly

---

#### **T-012: Hierarchical Goal Manager** (pokemon_yellow_agent)
**Status:** Not Started
**Estimated Time:** 20 minutes

**Files to Create:**
1. `pokemon_yellow_agent/src/goal_manager.py` (NEW)
   - Full implementation in plan file

**What It Does:**
- Uses Phi3 to analyze progress every N steps
- Updates short/medium-term goals
- Detects stuck state (position + text unchanging)
- Suggests recovery actions

---

#### **T-013: Pokemon Yellow Agent - OCR Integration**
**Status:** Not Started
**Estimated Time:** 20 minutes

**Files to Edit:**
1. `pokemon_yellow_agent/run_agent.py`
   - Import OCR functions and GoalManager
   - Add `extract_game_text()` function
   - Update main loop (see plan for detailed code)

**New Flow:**
```
1. Capture screen
2. OCR text (top + bottom regions)
3. Vision with OCR context
4. Update goals every 3-5 steps
5. Check if stuck
6. Executor decides with FULL context
7. Execute action
```

---

## Detailed Plan Location

**Full implementation details:** `C:/Users/gilli/.claude/plans/reflective-tumbling-pond.md`

The plan includes:
- Complete code for all classes/functions
- Line-by-line explanation
- Test cases and verification steps
- Performance considerations

---

## Performance Note

**Current runtime:** ~60-120 seconds per step
- Moondream (vision): 60-90s (CPU-bound)
- Phi3 (reasoning): 20-40s (via Ollama)
- OCR: <1s
- Capture: <0.1s

**Mitigation (in this PR):**
- Use OCR instead of asking Moondream to read text
- Cache observations if screen unchanged
- Run goal updates less frequently (every 3-5 steps)

**Long-term fix (future):** GPU acceleration or smaller models (T-014)

---

## Testing Plan

### Test Case 1: Fresh Game Start
**Expected:**
- OCR reads: "Welcome to the world of Pokemon!"
- Goal: "Advance dialogue"
- Action: Presses A repeatedly
- **Success:** Map changes from 18 to next area

### Test Case 2: Character Naming
**Expected:**
- OCR reads: "What is your name?" + name options
- Goal: "Select character name"
- Action: Navigate menu, press A
- **Success:** Character named, game progresses

### Test Case 3: Stuck Detection
**Expected:**
- After 3 steps with no change, stuck detected
- Action: Press A (for dialogue) or B (to back out)
- **Success:** Position changes or dialogue advances

---

## Current State of Codebase

### What's Already Done ✅
- agent_core: Capture, Detection, OCR (Rust), Input, Vision
- Pokemon Yellow agent: Basic Spotter + Executor loop
- Lua bridge: BizHawk input/state communication
- Git history: Clean, latest commit improves vision prompts

### What Needs Doing 🔧
- T-011: Expose OCR to Python
- T-012: Add GoalManager class
- T-013: Integrate into run_agent.py
- Test with fresh Pokemon Yellow save

---

## Important Files

### Agent Core
```
agent_core/
├── src/
│   ├── ocr.rs (Tesseract integration - already works!)
│   ├── lib.rs (PyO3 bindings - OCR functions exist but not exposed to Python)
│   └── capture.rs, detection.rs, input.rs (all working)
├── python/agent_core/
│   ├── __init__.py (EDIT: add OCR exports)
│   └── models.py (EDIT: add TextReader, update Spotter)
└── docs/
    └── TICKETS.md (updated, clean, current)
```

### Pokemon Yellow Agent
```
pokemon_yellow_agent/
├── run_agent.py (EDIT: add OCR + GoalManager)
├── src/
│   ├── goal_manager.py (CREATE)
│   ├── perception.py (already has window finding)
│   └── lua_input.py (working)
└── data/
    ├── emulator_state.json (Lua writes here)
    └── input_command.json (Agent writes here)
```

---

## Quick Start for Kya

1. **Read the plan:** `C:/Users/gilli/.claude/plans/reflective-tumbling-pond.md`
2. **Check tickets:** `agent_core/docs/TICKETS.md` (T-011, T-012, T-013)
3. **Start with T-011:** Expose OCR in agent_core
4. **Test incrementally:** After each ticket, verify it works
5. **Final test:** Fresh Pokemon Yellow game, watch it progress past intro

---

## Expected Outcome

**Before:**
```
[13:56:25] Saw: The image shows a computer screen displaying...
[13:56:25] -> UP
[13:56:25] >>> UP
Game: {'map': 18, 'pos': '(0,3)', 'battle': 0}  (STUCK!)
```

**After:**
```
[14:01:12] OCR Text: Welcome to the world of Pokemon!
[14:01:12] Saw: Dialogue box with welcome message visible
[14:01:13] Goals:
Medium-term: Complete intro sequence
Short-term: Advance dialogue by pressing A
[14:01:13] -> A
[14:01:13] >>> A
Game: {'map': 18, 'pos': '(0,3)', 'battle': 0}  (dialogue advancing)
```

---

## Questions or Issues?

- **Plan unclear?** Check `reflective-tumbling-pond.md` for detailed code
- **OCR not working?** Verify Tesseract installed at `C:\Program Files\Tesseract-OCR\tesseract.exe`
- **Phi3 slow?** It's expected (~20-40s), mitigated by running goal updates less often
- **Agent still stuck?** Check logs for OCR text output, verify it's reading actual dialogue

---

## Notes from Previous Developer

- All local models (Moondream + Phi3 + Tesseract)
- Agent_core is agnostic - don't put Pokemon-specific code there
- GoalManager is Pokemon-specific, stays in pokemon_yellow_agent
- Runtime is slow but acceptable for now (T-014 will optimize later)
- Fresh game save each run, so agent must handle intro every time

**Good luck! 🎮**
