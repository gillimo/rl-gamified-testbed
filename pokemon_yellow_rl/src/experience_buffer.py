"""Experience Replay Buffer"""
import random
from collections import deque
from typing import List, Tuple, Dict
import numpy as np

class ExperienceBuffer:
    """Store and sample (state, action, reward, next_state) tuples."""

    def __init__(self, maxlen=10000):
        self.buffer = deque(maxlen=maxlen)

    def add(self, state: Dict, action: int, reward: float, next_state: Dict):
        """Add experience to buffer."""
        self.buffer.append((state, action, reward, next_state))

    def sample(self, batch_size: int) -> List[Tuple[Dict, int, float, Dict]]:
        """Sample random batch from buffer."""
        return random.sample(self.buffer, min(batch_size, len(self.buffer)))

    def __len__(self):
        return len(self.buffer)

    def clear(self):
        """Clear all experiences."""
        self.buffer.clear()
