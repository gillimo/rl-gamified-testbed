"""Policy Network - State to Action mapping"""
import torch
import torch.nn as nn
import numpy as np
from typing import Dict

class PolicyNetwork(nn.Module):
    """Simple feedforward network for Pokemon Yellow RL."""

    def __init__(self, state_size=128, action_size=8, hidden_size=256):
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
    """Convert game state dict to normalized vector."""
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

    # Pad to 128 if needed
    while len(features) < 128:
        features.append(0.0)

    return np.array(features[:128], dtype=np.float32)
