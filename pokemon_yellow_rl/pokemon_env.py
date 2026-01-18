"""Pokemon Yellow Gymnasium Environment - PPO-compatible wrapper"""
import time
import math
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from typing import Dict, Tuple, Optional, Any

from src.game_interface import GameInterface
from src.reward_calculator import RewardCalculator
from src.policy_network import normalize_state, STATE_SIZE_WITH_SPATIAL
import config


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
        self.episode_reward = 0.0
        self.episode_peak_reward = 0.0
        self.last_non_menu_action = 0

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
        self.episode_reward = 0.0
        self.episode_peak_reward = 0.0
        self.last_non_menu_action = 0

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

        # Execute action (mask START/SELECT during trail curriculum pre-grass phase)
        trail_enabled = bool(self.reward_calc.weights.get("discovery", {}).get("trail_curriculum", {}).get("enabled", False))
        if trail_enabled and not self.reward_calc.first_grass_reached and action in (6, 7):
            action = self.last_non_menu_action
        if action in (0, 1, 2, 3, 4, 5):
            self.last_non_menu_action = action

        # Execute action
        self.game.send_action(action)
        self.current_step += 1

        # Get new state
        curr_state = self.game.get_state()

        # Calculate reward (with optional breakdown)
        if self.return_reward_breakdown:
            reward, breakdown = self.reward_calc.calculate_reward(
                self._prev_state,
                curr_state,
                return_breakdown=True,
                episode_level=self._score_to_level(self.episode_peak_reward),
            )
        else:
            reward = self.reward_calc.calculate_reward(
                self._prev_state,
                curr_state,
                episode_level=self._score_to_level(self.episode_peak_reward),
            )
            breakdown = None

        # Get observation
        observation = normalize_state(curr_state)

        # Update episode reward and dynamic step cap (based on peak score)
        pre_grass_enabled = bool(self.reward_calc.weights.get("discovery", {}).get("enable_pre_grass_curriculum", False))
        if pre_grass_enabled and not self.reward_calc.first_grass_reached:
            pre_grass_cap = self._score_for_level(5) - 1
            if self.episode_reward + reward > pre_grass_cap:
                reward = max(0.0, pre_grass_cap - self.episode_reward)
        self.episode_reward += reward
        if self.episode_reward > self.episode_peak_reward:
            self.episode_peak_reward = self.episode_reward
        dynamic_level = self._score_to_level(self.episode_peak_reward)
        dynamic_max_steps = self._calculate_episode_steps(dynamic_level)
        self.max_episode_steps = dynamic_max_steps

        # Check termination conditions
        terminated = False  # Pokemon Yellow doesn't have a natural end state for RL
        truncated = self.current_step >= dynamic_max_steps

        # Build info dict
        info = {
            "episode_step": self.current_step,
            "position": (curr_state.get("x", 0), curr_state.get("y", 0)),
            "map": curr_state.get("map", 0),
            "in_battle": curr_state.get("in_battle", 0),
            "badges": curr_state.get("badges", 0),
            "pokedex_owned": curr_state.get("pokedex_owned", 0),
            "lava_mode_active": self.reward_calc.lava_mode_active,
            "left_start_map": self.reward_calc.left_start_map,
            "first_grass_reached": self.reward_calc.first_grass_reached,
            "episode_level": self._score_to_level(self.episode_peak_reward),
        }
        lava_cfg = self.reward_calc.weights.get("lava_mode", {})
        trigger_seconds = lava_cfg.get("trigger_seconds", 30)
        elapsed = time.time() - self.reward_calc.last_positive_reward_time
        info["lava_seconds_left"] = max(0.0, trigger_seconds - elapsed)
        party = curr_state.get("party", []) or []
        party_count = min(curr_state.get("party_count", 0), len(party))
        max_party_level = 0
        for i in range(party_count):
            mon = party[i]
            if mon and isinstance(mon, dict):
                max_party_level = max(max_party_level, mon.get("level", 0))
        info["max_party_level"] = max_party_level

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

    def _score_to_level(self, score: float) -> int:
        """Map episode peak score to a level (monotonic during episode)."""
        if score <= 0:
            return 1
        exponent = 1.3524365633771591
        level = int((score / 1000.0) ** (1.0 / exponent)) + 1
        pre_grass_enabled = bool(self.reward_calc.weights.get("discovery", {}).get("enable_pre_grass_curriculum", False))
        max_level = 5 if pre_grass_enabled and not self.reward_calc.first_grass_reached else 100
        return min(level, max_level)

    def _score_for_level(self, level: int) -> float:
        if level <= 1:
            return 0.0
        exponent = 1.3524365633771591
        return 1000.0 * ((level - 1) ** exponent)

    def _calculate_episode_steps(self, level: int) -> int:
        """Calculate max episode steps based on level."""
        levels_gained = max(level - 1, 0)
        total_steps = int(config.BASE_STEPS_PER_EPISODE * (config.STEPS_MULTIPLIER ** levels_gained))
        return min(total_steps, config.MAX_STEPS_CAP)


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
