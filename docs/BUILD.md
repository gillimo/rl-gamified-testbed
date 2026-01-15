# Build and Setup (Pokemon Yellow Agent)

This guide is adapted from AgentOSRS workflows and trimmed to the minimal loop:
emulator -> memory bridge -> agent loop -> notes.

## Prereqs
- Windows 10/11.
- Python 3.10+.
- A local Pokemon Yellow ROM you own (place it in `roms/`).
- BizHawk emulator already downloaded to `tools/bizhawk/`.

## Project bootstrap (one-time)
1) Validate the template:
   - `scripts\validate_template.ps1`
2) (Optional) Run the original bootstrap for docs/metadata:
   - `scripts\bootstrap.ps1 -ProjectName pokemon_yellow_agent -Domain games`
3) Add your handle to `docs/LOGBOOK.md`.

## Python environment
1) Create a venv:
   - `python -m venv .venv`
2) Activate it:
   - `.\.venv\Scripts\Activate.ps1`
3) Install minimal deps:
   - `pip install mss pillow`

## Emulator setup (BizHawk only)
BizHawk is required for the Lua memory bridge.

1) Launch `tools\bizhawk\EmuHawk.exe`.
2) Load your ROM from `roms\`.
3) Keep the emulator window title visible; the agent uses it to focus the window.

## Emulator memory bridge (BizHawk Lua)
We use BizHawk Lua to read memory and write a JSON snapshot that the agent reads.

1) Use the included Lua script at `tools\bizhawk\pokemon_yellow_bridge.lua`.
2) In BizHawk: `Tools` -> `Lua Console` -> open the script.
3) Verify `data/emulator_state.json` updates as the game runs.

## Agent loop (minimal)
1) Start the emulator and load a save or new game.
2) Run the agent loop (after the Lua bridge is live):
   - `python run_app.py agent --window "EmuHawk" --log-state --snapshot-every 5`
   - Update the window title string if your BizHawk title differs.
3) Notes are appended to `data/agent_notes.md` each step.
4) Logs land in `logs/emulator_state_log.jsonl` and `logs/snapshots/`.

## Testing checklist
- Emulator window focus works (agent can send arrow key presses).
- `data/emulator_state.json` updates and the agent logs map/position.
- `data/agent_notes.md` entries appear for each step.
- `python run_app.py smoke --window "EmuHawk"` confirms state readback.
- `python run_app.py smoke --window "EmuHawk"` saves a snapshot in `logs/`.

## Reuse from AgentOSRS (trimmed)
- Window capture/focus: `src/perception.py`
- Input sending: `src/input_exec.py`
- Timing/randomness: `src/timing.py`, `src/randomness.py`

## Notes for human-like learning
- Keep the agent loop exploratory, with small random actions.
- Record observations and hypotheses in `data/agent_notes.md`.
- Avoid model training; use incremental heuristics and memory feedback.
