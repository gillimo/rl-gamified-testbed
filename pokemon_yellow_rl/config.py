"""RL Training Configuration"""

# Starter Pokemon Configuration
STARTER_SPECIES = 92  # Gastly (your favorite!)
# Other options:
# 25 = Pikachu (default Yellow starter)
# 1 = Bulbasaur, 4 = Charmander, 7 = Squirtle
# 92 = Gastly -> 93 = Haunter -> 94 = Gengar (trade evo at 25)

STARTER_LEVEL = 5
STARTER_NICKNAME = "GASTLY"  # Optional

# Training Parameters (Roguelite Mode)
BASE_STEPS_PER_EPISODE = 5000   # Starting steps
STEPS_MULTIPLIER = 1.15         # Multiply steps by this per level (exponential)
MAX_STEPS_CAP = 500000          # Cap to prevent runaway episodes

EPSILON_START = 0.5  # Exploration rate at start
EPSILON_END = 0.1    # Minimum exploration rate
EPSILON_DECAY = 0.995

# Network Parameters
STATE_SIZE = 128
ACTION_SIZE = 8
HIDDEN_SIZE = 256
LEARNING_RATE = 1e-3

# Experience Replay
BUFFER_SIZE = 10000
BATCH_SIZE = 32
TRAIN_FREQUENCY = 32  # Train every N steps

# Saving
SAVE_FREQUENCY = 10  # Save model every N episodes
