# RL Gamified Advanced Test

Mission Learning Statement
- Mission: Build a gamified reinforcement learning testbed with emulator-driven agents.
- Learning focus: RL environment design, reward shaping, OCR/vision integration, and control loops.
- Project start date: 2026-01-15 (inferred from earliest git commit)

Emulator-driven RL sandbox that combines vision, input control, and episodic evaluation to test agent behaviors in a constrained environment.

## Features

- Emulator-driven environments with scripted control loops
- OCR/vision hooks for state extraction
- Reward shaping and episodic evaluation
- CLI + GUI tooling for monitoring

## Installation

### Requirements

- Python 3.8+
- Emulator dependencies (see `tools/` and `docs/`)

## Quick Start

```bash
python run_app.py status
python run_app.py gui
```

## Usage

- RL-specific flows live in `pokemon_crystal_rl/` and `pokemon_yellow_rl/`.
- Use `run_agent.py` to launch agent loops.

## Architecture

```
Emulator
  |
  v
Frame Capture + OCR
  |
  v
State + Reward
  |
  v
Agent Policy
  |
  v
Input Controller -> Emulator
```

## Project Structure

```
run_app.py            # CLI/GUI entry
run_agent.py          # Agent loop
src/                  # Core logic
pokemon_crystal_rl/   # RL environment
pokemon_yellow_rl/    # RL environment
```

## Building

No build step required. Run directly with Python.

## Contributing

See `docs/` for internal notes and `CHANGELOG.md` for updates.

## License

MIT License - see [LICENSE](LICENSE) for details.
