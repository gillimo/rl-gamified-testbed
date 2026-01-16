"""RPG-style Trainer Stats Tracker"""
from typing import Dict


class TrainerStats:
    """Track agent's progress with RPG-style leveling."""

    MAX_LEVEL = 100

    def __init__(self):
        self.total_xp = 0.0  # Total reward earned across all episodes
        self.episode_count = 0
        self.best_episode_reward = 0.0
        self.current_episode_reward = 0.0

        # Milestones
        self.max_badges = 0
        self.max_pokedex = 0
        self.total_pokemon_caught = 0
        self.total_levels_gained = 0

    def get_trainer_level(self) -> int:
        """Calculate trainer level from total XP.

        Scaling: Level 100 requires ~500,000 XP (full game completion)
        - 8 badges × 5000 = 40,000 XP
        - 151 pokemon × 1500 = 226,500 XP
        - Exploration + battles = ~230,000 XP
        """
        if self.total_xp <= 0:
            return 1
        import math
        # Level = sqrt(XP / 50) + 1, so level 100 ≈ 490,050 XP
        level = int(math.sqrt(self.total_xp / 50.0)) + 1
        return min(level, self.MAX_LEVEL)

    def add_episode_reward(self, reward: float):
        """Add reward to current episode."""
        self.current_episode_reward += reward
        if self.current_episode_reward < 0:
            self.current_episode_reward = 0.0

    def finish_episode(self, game_state: Dict):
        """Complete current episode and update stats."""
        self.episode_count += 1
        self.total_xp += max(self.current_episode_reward, 0)  # Only positive XP counts
        self.best_episode_reward = max(self.best_episode_reward, self.current_episode_reward)

        # Update milestones
        self.max_badges = max(self.max_badges, game_state.get('badges', 0))
        pokedex = game_state.get('pokedex_owned', 0)
        if pokedex > self.max_pokedex:
            self.total_pokemon_caught += (pokedex - self.max_pokedex)
            self.max_pokedex = pokedex

        # Reset episode reward
        self.current_episode_reward = 0.0

    def print_stats(self):
        """Print RPG-style stats to console."""
        level = self.get_trainer_level()
        xp_bar = self._get_xp_bar(level)

        print("\n" + "=" * 60)
        print(f"  TRAINER STATS - Level {level}")
        print("=" * 60)
        print(f"  XP: {int(self.total_xp):,} {xp_bar}")
        if level >= self.MAX_LEVEL:
            print(f"  Next Level: MAX LEVEL REACHED!")
        else:
            # XP needed = (level^2 * 50) - current_xp
            next_level_xp = (level ** 2) * 50 - self.total_xp
            print(f"  Next Level: {int(max(0, next_level_xp)):,} XP needed")
        print(f"  Episode: #{self.episode_count}")
        print(f"  Current Reward: {self.current_episode_reward:,.1f}")
        print(f"  Best Reward: {self.best_episode_reward:,.1f}")
        print("-" * 60)
        print(f"  Badges Earned: {self.max_badges}/8")
        print(f"  Pokedex: {self.max_pokedex}/151 ({self.total_pokemon_caught} caught)")
        print("=" * 60 + "\n")

    def _get_xp_bar(self, level: int) -> str:
        """Generate ASCII XP progress bar."""
        if level >= self.MAX_LEVEL:
            return "[====================] MAX"
        # Same formula as get_trainer_level: level = sqrt(XP/50) + 1
        # So XP for level N = ((N-1)^2) * 50
        current_level_xp = ((level - 1) ** 2) * 50
        next_level_xp = (level ** 2) * 50
        xp_in_level = self.total_xp - current_level_xp
        xp_needed = next_level_xp - current_level_xp

        if xp_needed <= 0:
            progress = 1.0
        else:
            progress = min(max(xp_in_level / xp_needed, 0.0), 1.0)

        bar_length = 20
        filled = int(progress * bar_length)
        bar = "[" + "=" * filled + " " * (bar_length - filled) + "]"
        return f"{bar} {int(progress * 100)}%"
