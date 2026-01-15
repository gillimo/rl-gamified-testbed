# Startup Notes (BizHawk)

## Quick Start

1) Launch BizHawk (EmuHawk.exe).
2) Load ROM:
   - `python run_app.py loadrom --rom "C:\Users\gilli\OneDrive\Desktop\projects\pokemon_yellow_agent\roms\Pokemon - Yellow Version (UE) [C][!].gbc"`
3) Press through the start menu:
   - `python run_app.py start --start-key "START,Z,ENTER"`
4) Run the agent:
   - `python run_app.py agent --steps 200 --log-state --actions "Z,ENTER"`

agent_core 0.1.1 is installed in `C:\Users\gilli\.venv`. Use that Python when needed.

## Turn-On Function

Load ROM, press through the start menu, and optionally start the agent loop.

- Minimal:
  - `python run_app.py turnon --rom "C:\Users\gilli\OneDrive\Desktop\projects\pokemon_yellow_agent\roms\Pokemon - Yellow Version (UE) [C][!].gbc"`
- With agent loop:
  - `python run_app.py turnon --rom "C:\Users\gilli\OneDrive\Desktop\projects\pokemon_yellow_agent\roms\Pokemon - Yellow Version (UE) [C][!].gbc" --turnon-agent-steps 200 --log-state --actions "Z,ENTER"`
 - Build agent_core first (only if you changed the Rust library):
  - `python run_app.py turnon --rom "C:\Users\gilli\OneDrive\Desktop\projects\pokemon_yellow_agent\roms\Pokemon - Yellow Version (UE) [C][!].gbc" --build-agent-core`

## Window Title

If the BizHawk window title differs, pass it via `--window`.
