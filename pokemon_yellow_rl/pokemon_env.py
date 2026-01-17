"""Pokemon Yellow Gymnasium Environment - PPO-compatible wrapper"""
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from typing import Dict, Tuple, Optional, Any

from src.game_interface import GameInterface
from src.reward_calculator import RewardCalculator
from src.policy_network import normalize_state, STATE_SIZE_WITH_SPATIAL


# Reward categories for decomposed value learning
REWARD_CATEGORIES = ["exploration", "battle", "progression", "penalties", "lava"]


class PokemonYellowEnv(gym.Env):
    """Gymnasium environment wrapper for Pokemon Yellow RL training.

    This environment wraps the BizHawk emulator communication to provide
    a standard Gymnasium interface for use with PPO and other RL algorithms.

    Features:
    - Discrete action space (8 buttons)
    - Continuous observation space (normalized state vector)
    - Optional reward breakdown for decomposed value learning
    """

    metadata = {"render_modes": ["human"], "render_fps": 60}

    def __init__(
        self,
        frames_per_action: int = 4,
        save_slot: int = 1,
        return_reward_breakdown: bool = True,
        max_episode_steps: int = 1000,
    ):
        """Initialize the Pokemon Yellow environment.

        Args:
            frames_per_action: Number of frames to hold each button press
            save_slot: BizHawk save state slot to use for resets
            return_reward_breakdown: Whether to include reward breakdown in info dict
            max_episode_steps: Maximum steps per episode (used for truncation)
        """
        super().__init__()

        # Game interface and reward calculator
        self.game = GameInterface(frames_per_action=frames_per_action, save_slot=save_slot)
        self.reward_calc = RewardCalculator()

        # Environment settings
        self.return_reward_breakdown = return_reward_breakdown
        self.max_episode_steps = max_episode_steps
        self.current_step = 0

        # Action space: 8 buttons (UP, DOWN, LEFT, RIGHT, A, B, START, SELECT)
        self.action_space = spaces.Discrete(8)

        # Observation space: normalized state vector
        self.observation_space = spaces.Box(
            low=0.0,
            high=1.0,
            shape=(STATE_SIZE_WITH_SPATIAL,),
            dtype=np.float32
        )

        # Track previous state for reward calculation
        self._prev_state: Optional[Dict] = None

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Reset the environment to initial state.

        Args:
            seed: Random seed (unused, game is deterministic from save state)
            options: Additional options (unused)

        Returns:
            observation: Initial state observation
            info: Additional information dict
        """
        super().reset(seed=seed)

        # Reset game via save state load
        self.game.reset()
        self.reward_calc.reset()
        self.current_step = 0

        # Get initial state
        self._prev_state = self.game.get_state()
        observation = normalize_state(self._prev_state)

        info = {
            "episode_step": 0,
            "position": (self._prev_state.get("x", 0), self._prev_state.get("y", 0)),
            "map": self._prev_state.get("map", 0),
        }

        if self.return_reward_breakdown:
            info["reward_breakdown"] = {cat: 0.0 for cat in REWARD_CATEGORIES}

        return observation, info

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """Execute one step in the environment.

        Args:
            action: Action index (0-7)

        Returns:
            observation: New state observation
            reward: Reward from this step
            terminated: Whether episode ended naturally
            truncated: Whether episode was cut short (max steps)
            info: Additional information dict
        """
        assert self.action_space.contains(action), f"Invalid action {action}"

        # Execute action
        self.game.send_action(action)
        self.current_step += 1

        # Get new state
        curr_state = self.game.get_state()

        # Calculate reward (with optional breakdown)
        if self.return_reward_breakdown:
            reward, breakdown = self.reward_calc.calculate_reward(
                self._prev_state, curr_state, return_breakdown=True
            )
        else:
            reward = self.reward_calc.calculate_reward(self._prev_state, curr_state)
            breakdown = None

        # Get observation
        observation = normalize_state(curr_state)

        # Check termination conditions
        terminated = False  # Pokemon Yellow doesn't have a natural end state for RL
        truncated = self.current_step >= self.max_episode_steps

        # Build info dict
        info = {
            "episode_step": self.current_step,
            "position": (curr_state.get("x", 0), curr_state.get("y", 0)),
            "map": curr_state.get("map", 0),
            "in_battle": curr_state.get("in_battle", 0),
            "badges": curr_state.get("badges", 0),
            "pokedex_owned": curr_state.get("pokedex_owned", 0),
        }

        if self.return_reward_breakdown and breakdown is not None:
            info["reward_breakdown"] = breakdown

        # Update state tracking
        self._prev_state = curr_state

        return observation, reward, terminated, truncated, info

    def render(self):
        """Render the environment (handled by BizHawk window)."""
        pass  # BizHawk handles rendering

    def close(self):
        """Clean up environment resources."""
        pass  # No cleanup needed for file-based communication

    def get_action_meanings(self) -> list:
        """Return human-readable action names."""
        return ["UP", "DOWN", "LEFT", "RIGHT", "A", "B", "START", "SELECT"]


def make_pokemon_env(
    frames_per_action: int = 4,
    save_slot: int = 1,
    max_episode_steps: int = 1000,
) -> PokemonYellowEnv:
    """Factory function to create a Pokemon Yellow environment.

    Args:
        frames_per_action: Number of frames to hold each button press
        save_slot: BizHawk save state slot to use for resets
        max_episode_steps: Maximum steps per episode

    Returns:
        Configured PokemonYellowEnv instance
    """
    return PokemonYellowEnv(
        frames_per_action=frames_per_action,
        save_slot=save_slot,
        return_reward_breakdown=True,
        max_episode_steps=max_episode_steps,
    )
