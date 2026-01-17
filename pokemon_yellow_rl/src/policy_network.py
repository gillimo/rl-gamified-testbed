"""Policy Network - State to Action mapping with spatial awareness"""
import torch
import torch.nn as nn
import numpy as np
from typing import Dict

# Updated state size to include spatial features
STATE_SIZE_WITH_SPATIAL = 140

class PolicyNetwork(nn.Module):
    """Simple feedforward network for Pokemon Yellow RL."""

    def __init__(self, state_size=STATE_SIZE_WITH_SPATIAL, action_size=8, hidden_size=256):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(state_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_size // 2, action_size),
            nn.Softmax(dim=-1)
        )

    def forward(self, state):
        return self.network(state)

    def select_action(self, state, epsilon=0.1):
        """Epsilon-greedy action selection."""
        if np.random.random() < epsilon:
            return np.random.randint(0, 8)  # Random exploration
        else:
            with torch.no_grad():
                state_tensor = torch.FloatTensor(state).unsqueeze(0)
                probs = self.forward(state_tensor)
                return torch.multinomial(probs, 1).item()


def normalize_state(state_dict: Dict) -> np.ndarray:
    """Convert game state dict to normalized vector with spatial features."""
    features = []

    # Position (normalize to 0-1)
    features.append(state_dict.get('x', 0) / 255.0)
    features.append(state_dict.get('y', 0) / 255.0)
    features.append(state_dict.get('map', 0) / 255.0)

    # Money (normalize to max ~1M)
    features.append(min(state_dict.get('money', 0) / 1000000.0, 1.0))

    # Badges (0-8)
    features.append(state_dict.get('badges', 0) / 8.0)

    # Pokedex progress (0-151)
    features.append(state_dict.get('pokedex_owned', 0) / 151.0)
    features.append(state_dict.get('pokedex_seen', 0) / 151.0)

    # Battle status (-1, 0, 1, 2)
    features.append((state_dict.get('in_battle', 0) + 1) / 3.0)

    # === SPATIAL AWARENESS FEATURES (NEW) ===
    # Player direction (one-hot: down=0, up=4, left=8, right=12)
    direction = state_dict.get('player_direction', 0)
    features.append(1.0 if direction == 0 else 0.0)   # facing down
    features.append(1.0 if direction == 4 else 0.0)   # facing up
    features.append(1.0 if direction == 8 else 0.0)   # facing left
    features.append(1.0 if direction == 12 else 0.0)  # facing right

    # Tile ahead passable (0=blocked, 1=passable)
    features.append(float(state_dict.get('tile_ahead_passable', 0)))

    # Tile ahead raw value (normalized)
    features.append(state_dict.get('tile_ahead', 0) / 255.0)

    # Map dimensions (helps agent understand boundaries)
    features.append(state_dict.get('map_width', 0) / 255.0)
    features.append(state_dict.get('map_height', 0) / 255.0)

    # Position relative to map bounds (are we near edge?)
    map_width = state_dict.get('map_width', 10) * 2  # blocks to tiles
    map_height = state_dict.get('map_height', 10) * 2
    x, y = state_dict.get('x', 0), state_dict.get('y', 0)
    features.append(x / max(map_width, 1))  # normalized x position in map
    features.append(y / max(map_height, 1))  # normalized y position in map

    # Map type hint (indoor maps typically have low IDs, outdoor higher)
    map_id = state_dict.get('map', 0)
    features.append(1.0 if map_id <= 12 else 0.0)  # indoor (houses, labs)
    features.append(1.0 if 13 <= map_id <= 50 else 0.0)  # routes/towns

    # Party Pokemon (6 slots, 10 features each = 60)
    party = state_dict.get('party', [])
    for i in range(6):
        if i < len(party) and party[i]:
            mon = party[i]
            features.append(mon.get('species', 0) / 151.0)
            features.append(mon.get('level', 0) / 100.0)
            hp_ratio = mon.get('hp', 0) / max(mon.get('max_hp', 1), 1)
            features.append(hp_ratio)
            features.append(mon.get('attack', 0) / 500.0)
            features.append(mon.get('defense', 0) / 500.0)
            features.append(mon.get('speed', 0) / 500.0)
            features.append(mon.get('special', 0) / 500.0)
            features.append(mon.get('status', 0) / 7.0)
            # Move presence (binary)
            features.append(1.0 if mon.get('move_1', 0) > 0 else 0.0)
            features.append(1.0 if mon.get('move_2', 0) > 0 else 0.0)
        else:
            # Empty slot
            features.extend([0.0] * 10)

    # Pad to STATE_SIZE_WITH_SPATIAL if needed
    while len(features) < STATE_SIZE_WITH_SPATIAL:
        features.append(0.0)

    return np.array(features[:STATE_SIZE_WITH_SPATIAL], dtype=np.float32)
