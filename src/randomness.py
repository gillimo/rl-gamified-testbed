from __future__ import annotations

import os
import random
from typing import Optional


def seed_session(seed: Optional[int] = None) -> int:
    if seed is None:
        seed = int(os.urandom(4).hex(), 16)
    random.seed(seed)
    return seed
