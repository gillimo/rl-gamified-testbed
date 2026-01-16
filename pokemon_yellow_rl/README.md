# Pokemon Yellow RL Agent

Reinforcement learning agent that learns to play Pokemon Yellow from scratch.

## Features

- **Memory-based rewards** - 91 reward events tracked via game RAM
- **Fast training** - 15 actions/second (900x faster than LLM approach)
- **RPG-style stats** - Trainer level, XP, badges, Pokedex progress
- **Gastly starter** - Your favorite Pokemon (Haunter → Gengar at level 40)
- **Trade evolutions enabled** - No trading needed, evolves at level 40

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Start BizHawk with Pokemon Yellow loaded

3. Load the RL Lua bridge in BizHawk console:
```lua
dofile("C:/Users/gilli/OneDrive/Desktop/projects/pokemon_yellow_agent/tools/bizhawk/pokemon_yellow_rl_bridge.lua")
```

4. Run training:
```bash
cd pokemon_yellow_rl
python train_rl.py
```

## Configuration

Edit `config.py` to change:
- Starter Pokemon (default: Gastly, species 92)
- Training parameters (epsilon, learning rate, etc.)
- Network architecture

## Rewards

Key rewards (ascending priority):
- Exploration: +0.1 per new tile
- Dialogue: +2 per text advance, +30 completion (diminishing returns)
- Level up: +150 (early game), +100 (mid), +75 (late)
- Catching new species: **+1500** (EXTREME)
- Gym badges: **+5000** (MASSIVE)
- Elite Four: **+8000** per member

Penalties:
- Pokemon fainted: -50
- Stuck (same position): -10 to -200
- All Pokemon fainted: -200

## Output

Training displays RPG-style stats:
```
==========================================================
  TRAINER STATS - Level 12
==========================================================
  XP: 14,523 [========            ] 45%
  Next Level: 800 XP
  Episode: #47
  Current Reward: 1,245.3
  Best Reward: 3,891.2
----------------------------------------------------------
  Badges Earned: 1/8
  Pokedex: 8/151 (8 caught)
==========================================================
```

## Models

Saved to `models/` every 10 episodes:
- `policy_ep10.pt`, `policy_ep20.pt`, etc.
- `policy_final_epN.pt` on Ctrl+C

## Architecture

- **Policy Network**: 128 → 256 → 128 → 8 (feedforward)
- **State**: 128 floats (normalized game memory)
- **Actions**: UP, DOWN, LEFT, RIGHT, A, B, START, SELECT
- **Training**: REINFORCE with experience replay
