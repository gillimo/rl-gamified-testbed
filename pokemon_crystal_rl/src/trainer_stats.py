"""RPG-style Trainer Stats Tracker with Persistence"""
import json
from pathlib import Path
from typing import Dict

# Stats file path
STATS_PATH = Path(__file__).parent.parent / "trainer_stats.json"


class TrainerStats:
    """Track agent's progress with RPG-style leveling. Persists across sessions."""

    MAX_LEVEL = 100

    def __init__(self, auto_load: bool = True):
        self.total_xp = 0.0  # Total reward earned across all episodes
        self.episode_count = 0
        self.best_episode_reward = 0.0
        self.best_episode_level = 0
        self.current_episode_reward = 0.0

        # Milestones
        self.max_badges = 0
        self.max_pokedex = 0
        self.total_pokemon_caught = 0
        self.total_levels_gained = 0

        # Auto-load saved stats
        if auto_load:
            self.load()

    def get_trainer_level(self) -> int:
        """Calculate roguelite level from best episode reward.

        Level reflects your best single-episode score.
        Early levels are harder: Level 2 requires 1,000 points.
        Level 100 targets 500,000 points.
        """
        if self.best_episode_reward <= 0:
            return 1
        level = int(self._level_from_score(self.best_episode_reward)) + 1
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
        episode_level = int(game_state.get("episode_level", 1))
        if episode_level >= 6:
            if episode_level > self.best_episode_level or (
                episode_level == self.best_episode_level and self.current_episode_reward > self.best_episode_reward
            ):
                self.best_episode_reward = self.current_episode_reward
                self.best_episode_level = episode_level
        elif self.best_episode_level < 6:
            if self.current_episode_reward > self.best_episode_reward:
                self.best_episode_reward = self.current_episode_reward

        # Update milestones
        self.max_badges = max(self.max_badges, game_state.get('badges', 0))
        pokedex = game_state.get('pokedex_owned', 0)
        if pokedex > self.max_pokedex:
            self.total_pokemon_caught += (pokedex - self.max_pokedex)
            self.max_pokedex = pokedex

        # Reset episode reward
        self.current_episode_reward = 0.0

        # Auto-save after each episode
        self.save()

    def print_stats(self, Colors=None):
        """Print RPG-style stats to console with Pokemon colors."""
        level = self.get_trainer_level()

        # Default no-color if Colors not provided
        if Colors is None:
            class Colors:
                YELLOW = RED = BLUE = GREEN = PURPLE = CYAN = WHITE = ''
                BOLD = DIM = RESET = ELECTRIC = FIRE = GRASS = ''

        # XP bar with color
        xp_bar = self._get_xp_bar_colored(level, Colors)

        # Badge icons (filled vs empty)
        badge_icons = f"{Colors.YELLOW}{'●' * self.max_badges}{Colors.DIM}{'○' * (8 - self.max_badges)}{Colors.RESET}"

        # Pokedex progress bar
        dex_pct = int((self.max_pokedex / 151) * 20)
        dex_bar = f"{Colors.RED}{'█' * dex_pct}{Colors.DIM}{'░' * (20 - dex_pct)}{Colors.RESET}"

        print(f"\n  {Colors.PURPLE}+{'-'*58}+{Colors.RESET}")
        print(f"  {Colors.PURPLE}|{Colors.RESET}  {Colors.BOLD}{Colors.YELLOW}⚡ ROGUELITE STATS ⚡{Colors.RESET}                            {Colors.PURPLE}|{Colors.RESET}")
        print(f"  {Colors.PURPLE}+{'-'*58}+{Colors.RESET}")
        print(f"  {Colors.PURPLE}|{Colors.RESET}                                                          {Colors.PURPLE}|{Colors.RESET}")
        print(f"  {Colors.PURPLE}|{Colors.RESET}   {Colors.WHITE}Best Run Lv:{Colors.RESET}  {Colors.BOLD}{Colors.ELECTRIC}{level:>3}{Colors.RESET}  {xp_bar}        {Colors.PURPLE}|{Colors.RESET}")
        print(f"  {Colors.PURPLE}|{Colors.RESET}   {Colors.WHITE}High Score:{Colors.RESET}  {Colors.CYAN}{int(self.best_episode_reward):>10,}{Colors.RESET}                         {Colors.PURPLE}|{Colors.RESET}")

        if level >= self.MAX_LEVEL:
            print(f"  {Colors.PURPLE}|{Colors.RESET}   {Colors.FIRE}★ MAX LEVEL REACHED! ★{Colors.RESET}                         {Colors.PURPLE}|{Colors.RESET}")
        else:
            next_level_score = (level ** 2) * 50 - self.best_episode_reward
            print(f"  {Colors.PURPLE}|{Colors.RESET}   {Colors.DIM}Next Best Lv:{Colors.RESET}  {Colors.WHITE}{int(max(0, next_level_score)):,} pts needed{Colors.RESET}              {Colors.PURPLE}|{Colors.RESET}")

        print(f"  {Colors.PURPLE}|{Colors.RESET}                                                          {Colors.PURPLE}|{Colors.RESET}")
        print(f"  {Colors.PURPLE}+{'-'*58}+{Colors.RESET}")
        print(f"  {Colors.PURPLE}|{Colors.RESET}   {Colors.WHITE}Episodes Played:{Colors.RESET}  {Colors.BOLD}{self.episode_count}{Colors.RESET}                                {Colors.PURPLE}|{Colors.RESET}")
        print(f"  {Colors.PURPLE}|{Colors.RESET}                                                          {Colors.PURPLE}|{Colors.RESET}")
        print(f"  {Colors.PURPLE}+{'-'*58}+{Colors.RESET}")
        print(f"  {Colors.PURPLE}|{Colors.RESET}   {Colors.YELLOW}Badges:{Colors.RESET}    {badge_icons}  {Colors.WHITE}{self.max_badges}/8{Colors.RESET}                    {Colors.PURPLE}|{Colors.RESET}")
        print(f"  {Colors.PURPLE}|{Colors.RESET}   {Colors.RED}Pokedex:{Colors.RESET}   [{dex_bar}] {Colors.WHITE}{self.max_pokedex}/151{Colors.RESET}         {Colors.PURPLE}|{Colors.RESET}")
        print(f"  {Colors.PURPLE}|{Colors.RESET}   {Colors.DIM}Pokemon Caught: {self.total_pokemon_caught}{Colors.RESET}                               {Colors.PURPLE}|{Colors.RESET}")
        print(f"  {Colors.PURPLE}|{Colors.RESET}                                                          {Colors.PURPLE}|{Colors.RESET}")
        print(f"  {Colors.PURPLE}+{'-'*58}+{Colors.RESET}\n")

    def _get_xp_bar_colored(self, level: int, Colors) -> str:
        """Generate colored XP progress bar (based on best episode score)."""
        if level >= self.MAX_LEVEL:
            return f"{Colors.ELECTRIC}[{'█'*20}]{Colors.RESET} {Colors.FIRE}MAX{Colors.RESET}"

        current_level_score = self._score_for_level(level)
        next_level_score = self._score_for_level(level + 1)
        score_in_level = self.best_episode_reward - current_level_score
        score_needed = next_level_score - current_level_score

        if score_needed <= 0:
            progress = 1.0
        else:
            progress = min(max(score_in_level / score_needed, 0.0), 1.0)

        bar_length = 20
        filled = int(progress * bar_length)
        bar = f"{Colors.GREEN}{'█' * filled}{Colors.DIM}{'░' * (bar_length - filled)}{Colors.RESET}"
        return f"[{bar}] {Colors.WHITE}{int(progress * 100)}%{Colors.RESET}"

    def _get_xp_bar(self, level: int) -> str:
        """Generate ASCII XP progress bar (based on best episode score)."""
        if level >= self.MAX_LEVEL:
            return "[====================] MAX"
        current_level_score = self._score_for_level(level)
        next_level_score = self._score_for_level(level + 1)
        score_in_level = self.best_episode_reward - current_level_score
        score_needed = next_level_score - current_level_score

        if score_needed <= 0:
            progress = 1.0
        else:
            progress = min(max(score_in_level / score_needed, 0.0), 1.0)

        bar_length = 20
        filled = int(progress * bar_length)
        bar = "[" + "=" * filled + " " * (bar_length - filled) + "]"
        return f"{bar} {int(progress * 100)}%"

    def _score_for_level(self, level: int) -> float:
        """Score threshold for a given level (Level 2 = 1,000, Level 100 = 500,000)."""
        if level <= 1:
            return 0.0
        exponent = 1.3524365633771591
        return 1000.0 * ((level - 1) ** exponent)

    def _level_from_score(self, score: float) -> float:
        """Inverse of score curve: returns 0-based level progress (Level 1 = 0)."""
        if score <= 0:
            return 0.0
        exponent = 1.3524365633771591
        return (score / 1000.0) ** (1.0 / exponent)

    def save(self):
        """Save stats to JSON file."""
        # Convert all values to native Python types to avoid numpy.float32 serialization errors
        data = {
            "total_xp": float(self.total_xp),
            "episode_count": int(self.episode_count),
            "best_episode_reward": float(self.best_episode_reward),
            "best_episode_level": int(self.best_episode_level),
            "max_badges": int(self.max_badges),
            "max_pokedex": int(self.max_pokedex),
            "total_pokemon_caught": int(self.total_pokemon_caught),
            "total_levels_gained": int(self.total_levels_gained),
        }
        try:
            with open(STATS_PATH, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"  [WARN] Failed to save trainer stats: {e}")

    def load(self):
        """Load stats from JSON file if it exists."""
        try:
            if STATS_PATH.exists():
                with open(STATS_PATH) as f:
                    data = json.load(f)
                self.total_xp = data.get("total_xp", 0.0)
                self.episode_count = data.get("episode_count", 0)
                self.best_episode_reward = data.get("best_episode_reward", 0.0)
                self.best_episode_level = data.get("best_episode_level", 0)
                self.max_badges = data.get("max_badges", 0)
                self.max_pokedex = data.get("max_pokedex", 0)
                self.total_pokemon_caught = data.get("total_pokemon_caught", 0)
                self.total_levels_gained = data.get("total_levels_gained", 0)
                print(f"  [LOAD] Roguelite stats loaded: Best Lv {self.get_trainer_level()}, {int(self.total_xp):,} XP")
        except Exception as e:
            print(f"  [WARN] Failed to load trainer stats: {e}")

    def reset(self):
        """Reset all stats to fresh start (Level 1)."""
        self.total_xp = 0.0
        self.episode_count = 0
        self.best_episode_reward = 0.0
        self.current_episode_reward = 0.0
        self.max_badges = 0
        self.max_pokedex = 0
        self.total_pokemon_caught = 0
        self.total_levels_gained = 0
        self.save()
        print("  [RESET] Trainer stats reset to Level 1!")


def reset_trainer_stats():
    """Utility function to reset trainer stats from command line."""
    stats = TrainerStats(auto_load=False)
    stats.reset()
    print("Trainer stats have been reset to Level 1.")


if __name__ == "__main__":
    reset_trainer_stats()
