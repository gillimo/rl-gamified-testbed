"""Pokemon Crystal PPO Training - Proper RL with value baseline and GAE.



This script replaces the broken REINFORCE implementation with PPO,

which properly handles:

- Sequential credit assignment via GAE

- Value baseline for variance reduction

- Stable policy updates via clipping

- Model checkpointing and resumption



Usage:

    python train_ppo.py [--resume PATH]

"""

import os

import sys

import time

import argparse

import json

import re

from pathlib import Path

from typing import Optional



# Enable ANSI colors on Windows

if sys.platform == 'win32':

    os.system('color')



import numpy as np

import torch

from stable_baselines3 import PPO

from stable_baselines3.common.callbacks import BaseCallback, CheckpointCallback

from stable_baselines3.common.logger import configure



from pokemon_env import PokemonCrystalEnv, REWARD_CATEGORIES

from decomposed_policy import DecomposedActorCriticPolicy

from src.trainer_stats import TrainerStats
from src.cli_ui import print_heartbeat, print_episode_box

from set_starter import set_starter

import config





# Pokemon-themed ANSI colors

class Colors:

    YELLOW = '\033[93m'

    RED = '\033[91m'

    BLUE = '\033[94m'

    GREEN = '\033[92m'

    PURPLE = '\033[95m'

    CYAN = '\033[96m'

    WHITE = '\033[97m'

    BOLD = '\033[1m'

    DIM = '\033[2m'

    RESET = '\033[0m'

    FIRE = '\033[38;5;208m'

    ELECTRIC = '\033[38;5;226m'

    GHOST = '\033[38;5;99m'





class PokemonTrainingCallback(BaseCallback):

    """RPG-style training callback with visual boxes and delta tracking."""



    NUM_ACTIONS = 8  # Pokemon Crystal: A, B, Start, Select, Up, Down, Left, Right



    def __init__(self, trainer_stats: TrainerStats, max_episode_steps: int = 1000, verbose: int = 1, constraints_path: Optional[Path] = None, logs_dir: Optional[Path] = None):

        super().__init__(verbose)

        self.trainer_stats = trainer_stats

        self.max_episode_steps = max_episode_steps

        self.constraints_path = constraints_path

        self.logs_dir = logs_dir

        self.constraints_mtime = 0

        self.constraints = {}



        self.episode_rewards = []

        self.episode_lengths = []

        self.current_episode_reward = 0.0

        self.current_episode_length = 0

        self.last_print_step = 0



        # Heartbeat tracking for kid-friendly display

        self.episode_total_gain = 0.0

        self.episode_total_loss = 0.0

        self.episode_best_moment = 0.0  # largest absolute reward seen

        self.episode_best_moment_breakdown = {}

        self.heartbeat_printed = False  # track if we need to overwrite
        self.last_heartbeat_lines = 0

        self.episode_peak_reward = 0.0

        self.episode_current_level = 1

        self.episode_level_for_steps = 1

        self.prev_episode_level = 1

        self.episode_lava_penalty = 0.0

        self.split_history = []

        self.last_entropy = None

        self.last_info = {}

        self.last_reward = 0.0

        self.entropy_coef_base = None

        self.entropy_level_table = None

        self.entropy_floor = 0.02

        self.entropy_decay = 0.9

        self.learning_color_index = 0

        self.learning_colors = [

            Colors.PURPLE,

            Colors.BLUE,

            Colors.GREEN,

            Colors.ELECTRIC,

            Colors.FIRE,

            Colors.CYAN,

        ]
        self.Colors = Colors



        # Interval tracking for heartbeat (last 100 steps)

        self.interval_rewards = {

            'exploration': 0.0,

            'battle': 0.0,

            'progression': 0.0,

            'penalties': 0.0,

            'lava': 0.0,

        }



        # Delta tracking for PPO updates

        self.prev_episode_count = 0

        self.prev_avg_reward = 0.0

        self.prev_confidence = 50.0



        # High score tracking

        self.prev_best_episode_reward = trainer_stats.best_episode_reward

        self.cycle_history = []

        self.prev_episode_reward = 0.0

        self.prev_avg10 = 0.0

        self.prev_avg_all = 0.0

        self.prev_avg10_heartbeat = None

        self.last_avg_delta = 0.0

        self.last_progress_index = 0.0

        self.avg_reward_ema = None

        self.prev_avg_reward_ema = None

        self.episode_return_ema = None

        self.prev_episode_return_ema = None

        self.policy_index = 0.0

        self.policy_index_sign = 0

        self.index_green_count = 0

        self.index_red_count = 0

        self.index_green_mag = 0.0

        self.index_red_mag = 0.0

        self.progress_streak = 0

        self.progress_streak_sign = 0

        self.rollout_reward_sum = 0.0

        self.rollout_step_count = 0

        self.cycle_episode_rewards = []



    def _entropy_to_confidence(self, entropy: float) -> float:

        """Convert entropy to confidence percentage.



        Entropy ranges from 0 (certain) to ln(num_actions) (random).

        We invert so: 0% = random guessing, 100% = fully confident.

        """

        max_entropy = np.log(self.NUM_ACTIONS)  # ~2.08 for 8 actions

        if max_entropy <= 0:

            return 50.0

        # Clamp entropy to valid range

        entropy = max(0, min(abs(entropy), max_entropy))

        # Higher entropy = less confident, so invert

        confidence = 100 * (1 - (entropy / max_entropy))

        return confidence



    def _on_training_start(self) -> None:

        self._load_constraints(force=True)

        self._apply_entropy_for_level(1)

        if getattr(self, "training_env", None) is not None:

            try:

                self.training_env.reset()

            except Exception:

                pass

        self.current_episode_reward = 0.0

        self.current_episode_length = 0

        self.episode_total_gain = 0.0

        self.episode_total_loss = 0.0

        self.episode_best_moment = 0.0

        self.episode_best_moment_breakdown = {}

        self.heartbeat_printed = False

        self.episode_peak_reward = 0.0

        self.episode_current_level = 1

        self.episode_level_for_steps = 1

        self.prev_episode_level = 1

        self.episode_lava_penalty = 0.0

        self.last_info = {}

        self.last_reward = 0.0

        for key in self.interval_rewards:

            self.interval_rewards[key] = 0.0

        self._update_episode_steps(1, force=True)



    def _apply_entropy_for_level(self, level: int) -> None:

        if not self.model:

            return

        base = self.entropy_coef_base if self.entropy_coef_base is not None else float(getattr(self.model, "ent_coef", 0.05))

        level_table = self.entropy_level_table or {}

        if level in level_table:

            self.model.ent_coef = float(level_table[level])

        else:

            decayed = base * (self.entropy_decay ** max(level - 4, 0))

            self.model.ent_coef = max(decayed, self.entropy_floor)



    def _load_constraints(self, force: bool = False) -> None:

        if not self.constraints_path:

            self.entropy_coef_base = float(getattr(self.model, "ent_coef", 0.05)) if self.model else 0.05

            self.entropy_level_table = {1: 0.08, 2: 0.06, 3: 0.04, 4: 0.03}

            self.entropy_floor = 0.02

            self.entropy_decay = 0.9

            return

        try:

            if not self.constraints_path.exists():

                return

            mtime = self.constraints_path.stat().st_mtime

            if not force and mtime <= self.constraints_mtime:

                return

            with open(self.constraints_path, "r", encoding="utf-8") as f:

                self.constraints = json.load(f)

            self.constraints_mtime = mtime

            self.entropy_coef_base = float(self.constraints.get("ent_coef_decay_base", self.constraints.get("ent_coef", 0.05)))

            self.entropy_level_table = {

                1: float(self.constraints.get("ent_coef_level_1", 0.08)),

                2: float(self.constraints.get("ent_coef_level_2", 0.06)),

                3: float(self.constraints.get("ent_coef_level_3", 0.04)),

                4: float(self.constraints.get("ent_coef_level_4", 0.03)),

            }

            self.entropy_floor = float(self.constraints.get("ent_coef_floor", 0.02))

            self.entropy_decay = float(self.constraints.get("ent_coef_decay", 0.9))

        except Exception:

            return



    def _next_learning_color(self) -> str:

        color = self.learning_colors[self.learning_color_index % len(self.learning_colors)]

        self.learning_color_index += 1

        return color



    def _on_step(self) -> bool:

        infos = self.locals.get("infos", [{}])

        rewards = self.locals.get("rewards", [0])

        dones = self.locals.get("dones", [False])

        if self.num_timesteps % 100 == 0:

            self._load_constraints()

            if self.episode_current_level:

                self._apply_entropy_for_level(self.episode_current_level)

        if self.logger:

            entropy_value = self.logger.name_to_value.get("train/entropy", None)

            if entropy_value not in (None, 0):

                self.last_entropy = min(abs(entropy_value), np.log(self.NUM_ACTIONS))



        for info, reward, done in zip(infos, rewards, dones):

            self.last_info = info or {}

            self.last_reward = reward

            self.current_episode_reward += reward

            self.rollout_reward_sum += reward

            self.rollout_step_count += 1

            self.current_episode_length += 1

            if self.current_episode_reward > self.episode_peak_reward:

                self.episode_peak_reward = self.current_episode_reward

            self.episode_current_level = self._score_to_level(self.episode_peak_reward)

            if self.episode_current_level > self.prev_episode_level:

                old_steps = self.max_episode_steps

                self._update_episode_steps(self.episode_current_level)

                new_steps = self.max_episode_steps

                self._apply_entropy_for_level(self.episode_current_level)

                print(f"  {Colors.ELECTRIC}★ EPISODE LEVEL UP!{Colors.RESET} {Colors.WHITE}{self.prev_episode_level}{Colors.RESET} → {Colors.YELLOW}{self.episode_current_level}{Colors.RESET}  {Colors.DIM}Steps: {old_steps:,} → {new_steps:,}{Colors.RESET}")

                self.prev_episode_level = self.episode_current_level



            # Track interval rewards from info breakdown

            breakdown = info.get('reward_breakdown', {})

            for key in self.interval_rewards:

                self.interval_rewards[key] += breakdown.get(key, 0.0)

            lava_delta = breakdown.get("lava", 0.0)

            if lava_delta < 0:

                self.episode_lava_penalty += abs(lava_delta)



            # Track gains/losses for heartbeat display

            if reward > 0:

                self.episode_total_gain += reward

            else:

                self.episode_total_loss += reward

            if abs(reward) > abs(self.episode_best_moment):

                self.episode_best_moment = reward

                self.episode_best_moment_breakdown = dict(breakdown)



            if done:

                self.episode_rewards.append(self.current_episode_reward)

                self.episode_lengths.append(self.current_episode_length)

                self.trainer_stats.add_episode_reward(self.current_episode_reward)

                self.trainer_stats.finish_episode(info)

                self._print_episode_box(info)

                self._check_high_score()

                self.cycle_episode_rewards.append(self.current_episode_reward)

                self.current_episode_reward = 0.0

                self.current_episode_length = 0

                # Reset interval tracking

                for key in self.interval_rewards:

                    self.interval_rewards[key] = 0.0

                # Reset heartbeat tracking

                self.episode_total_gain = 0.0

                self.episode_total_loss = 0.0

                self.episode_best_moment = 0.0

                self.episode_best_moment_breakdown = {}

                self.heartbeat_printed = False

                self.episode_peak_reward = 0.0

                self.episode_current_level = 1

                self.episode_level_for_steps = 1

                self._update_episode_steps(1, force=True)

                self.prev_episode_level = 1

                self.episode_lava_penalty = 0.0

                self.last_info = {}

                self.last_reward = 0.0



        # Heartbeat every step

        if self.num_timesteps - self.last_print_step >= 1:

            self._print_heartbeat()

            self.last_print_step = self.num_timesteps

            # Reset interval tracking after heartbeat

            for key in self.interval_rewards:

                self.interval_rewards[key] = 0.0



        return True



    def _print_heartbeat(self):

        """Print kid-friendly boxed progress that updates in place."""
        return print_heartbeat(self)

        # Calculate progress

        step = self.current_episode_length

        total = self.max_episode_steps

        pct = int((step / total) * 100) if total > 0 else 0



        # Progress bar (20 chars wide)

        bar_filled = pct // 5

        # Use ASCII for stable width across terminals.
        bar = '#' * bar_filled + '-' * (20 - bar_filled)



        # Format values

        gain = self.episode_total_gain

        loss = self.episode_total_loss

        best = self.episode_best_moment



        # Build box lines (13 lines total)

        box_width = 50

        badges = self.last_info.get("badges", 0)

        pokedex = self.last_info.get("pokedex_owned", 0)

        lava_active = self.last_info.get("lava_mode_active", False)

        lava_seconds_left = self.last_info.get("lava_seconds_left", 0.0)

        if lava_active:

            lava_status = f"Lava: {Colors.RED}ON{Colors.CYAN}  Pen: -{self.episode_lava_penalty:,.0f}"

        else:

            if lava_seconds_left <= 1:

                lava_color = Colors.RED

            elif lava_seconds_left <= 5:

                lava_color = Colors.FIRE

            elif lava_seconds_left <= 10:

                lava_color = Colors.YELLOW

            else:

                lava_color = Colors.GREEN

            lava_status = f"Lava: {lava_color}OFF{Colors.CYAN}  {lava_color}{lava_seconds_left:>4.0f}s{Colors.CYAN}"

        breakdown = self.episode_best_moment_breakdown



        def _fmt_breakdown(label: str, value: float, zero_negative: bool = False) -> str:

            if value > 0:

                color = Colors.GREEN

                sign = "+"

            elif value < 0:

                color = Colors.RED

                sign = "-"

            else:

                color = Colors.WHITE

                sign = "-" if zero_negative else "+"

            return f"{label}:{color}{sign}{abs(value):,.0f}{Colors.CYAN}"



        breakdown_text = (

            f"{_fmt_breakdown('exp', breakdown.get('exploration', 0))} "

            f"{_fmt_breakdown('bat', breakdown.get('battle', 0))} "

            f"{_fmt_breakdown('prog', breakdown.get('progression', 0))} "

            f"{_fmt_breakdown('pen', breakdown.get('penalties', 0), True)} "

            f"{_fmt_breakdown('lava', breakdown.get('lava', 0), True)}"

        )



        xp_val = self.current_episode_reward

        split_color = Colors.WHITE

        if total > 0 and step > 0 and self.episode_rewards:

            recent = self.episode_rewards[-10:]

            avg_recent = float(np.mean(recent))

            best_recent = max(recent)

            best_ever = self.trainer_stats.best_episode_reward

            avg_pace = avg_recent * (step / total) if avg_recent else 0.0

            best_recent_pace = best_recent * (step / total) if best_recent else 0.0

            best_ever_pace = best_ever * (step / total) if best_ever else 0.0

            if best_ever_pace and xp_val >= best_ever_pace:

                xp_color = Colors.ELECTRIC

                xp_suffix = " âœ¨"

                split_color = Colors.ELECTRIC

            elif best_recent_pace and xp_val >= best_recent_pace:

                xp_color = Colors.PURPLE

                xp_suffix = ""

                split_color = Colors.PURPLE

            elif avg_pace and xp_val >= avg_pace:

                xp_color = Colors.GREEN

                xp_suffix = ""

                split_color = Colors.GREEN

            else:

                xp_color = Colors.RED

                xp_suffix = ""

                split_color = Colors.RED

        else:

            xp_color = Colors.WHITE

            xp_suffix = ""

        breakdown_text = f"{split_color}{breakdown_text}{Colors.CYAN}"



        next_level_points = self._next_level_points(self.episode_current_level)

        ansi_re = re.compile(r"\x1b\[[0-9;]*m")

        def _visible_len(value: str) -> int:

            return len(ansi_re.sub("", value))



        def _box_line(content: str) -> str:

            line = f"  │  {content}"

            pad = (box_width + 3) - _visible_len(line)

            if pad < 0:

                pad = 0

            return f"{line}{' ' * pad}│"



        xp_value = f"{xp_val:>10,.0f}{xp_suffix}"

        xp_line = _box_line(f"Episode XP: {xp_value}")

        xp_line = xp_line.replace(xp_value, f"{xp_color}{xp_value}{Colors.CYAN}", 1)



        if lava_active:

            lava_status_visible = f"Lava: ON  Pen: -{self.episode_lava_penalty:,.0f}"

            lava_status_colored = f"Lava: {Colors.RED}ON{Colors.CYAN}  Pen: {Colors.RED}-{self.episode_lava_penalty:,.0f}{Colors.CYAN}"

        else:

            lava_status_visible = f"Lava: OFF  {lava_seconds_left:>2.0f}s"

            lava_status_colored = f"Lava: {lava_color}OFF{Colors.CYAN}  {lava_color}{lava_seconds_left:>2.0f}s{Colors.CYAN}"

        lava_line = _box_line(lava_status_visible).replace(lava_status_visible, lava_status_colored, 1)



        entropy_val = self.last_entropy if self.last_entropy is not None else np.log(self.NUM_ACTIONS)

        if self.current_episode_length > 0:

            recent_rewards = (self.episode_rewards[-9:] if len(self.episode_rewards) >= 9 else list(self.episode_rewards))

            recent_rewards = recent_rewards + [self.current_episode_reward]

        else:

            recent_rewards = self.episode_rewards[-10:]

        avg_recent = float(np.mean(recent_rewards)) if recent_rewards else 0.0

        if self.avg_reward_ema is None:

            self.avg_reward_ema = avg_recent

        else:

            # Long-term trend (slow EMA)

            alpha = 0.02

            self.avg_reward_ema = (alpha * avg_recent) + ((1 - alpha) * self.avg_reward_ema)

        if self.prev_avg_reward_ema is None:

            self.prev_avg_reward_ema = self.avg_reward_ema

        avg_delta_raw = avg_recent - (self.prev_avg10_heartbeat if self.prev_avg10_heartbeat is not None else avg_recent)

        if abs(avg_delta_raw) > 0.0001:

            self.last_avg_delta = avg_delta_raw

            avg_delta = avg_delta_raw

        else:

            avg_delta = self.last_avg_delta

        avg_sign = "+" if avg_delta >= 0 else ""

        avg_color = Colors.GREEN if avg_delta > 0 else Colors.RED if avg_delta < 0 else Colors.WHITE

        avg_line = _box_line(f"Avg Reward: {avg_recent:>10,.0f} ({avg_sign}{avg_delta:>7,.1f})")

        avg_line = avg_line.replace(

            f"{avg_sign}{avg_delta:>7,.1f}",

            f"{avg_color}{avg_sign}{avg_delta:>7,.1f}{Colors.CYAN}",

            1,

        )

        progress_index = self.policy_index

        progress_sign = self.policy_index_sign

        if progress_sign > 0:

            streak_label = 'POS'

            streak_color = Colors.ELECTRIC if self.progress_streak >= 200 else Colors.GREEN

        elif progress_sign < 0:

            streak_label = 'NEG'

            streak_color = Colors.FIRE if self.progress_streak >= 50 else Colors.RED

        else:

            streak_label = 'NEUT'

            streak_color = Colors.WHITE

        if progress_index > 0.01:

            trend_label = f"{Colors.GREEN}IMPROVING{Colors.CYAN}"

        elif progress_index < -0.01:

            trend_label = f"{Colors.RED}DAMAGING{Colors.CYAN}"

        else:

            trend_label = f"{Colors.WHITE}STABLE{Colors.CYAN}"

        pi_sign = "+" if progress_index >= 0 else ""

        pi_color = Colors.GREEN if progress_index > 0 else Colors.RED if progress_index < 0 else Colors.WHITE

        pi_text = f"{pi_sign}{progress_index:>6.2f}"

        streak_text = f"{self.progress_streak:>3}"

        pi_line = _box_line(f"Model Index: {pi_text} ({streak_text})")

        pi_line = pi_line.replace(pi_text, f"{pi_color}{pi_text}{Colors.CYAN}", 1)

        pi_line = pi_line.replace(streak_text, f"{streak_color}{streak_text}{Colors.CYAN}", 1)

        trend_line = _box_line(f"Training Trend: {trend_label}")

        ratio_den = self.index_red_count if self.index_red_count > 0 else 1

        ratio_val = self.index_green_count / ratio_den

        ratio_text = f"{self.index_green_count}:{self.index_red_count} ({ratio_val:>4.2f}x)"

        ratio_line = _box_line(f"Index Ratio: {ratio_text}")

        ratio_line = ratio_line.replace(

            ratio_text,

            f"{Colors.GREEN}{self.index_green_count}{Colors.CYAN}:{Colors.RED}{self.index_red_count}{Colors.CYAN} ({Colors.WHITE}{ratio_val:>4.2f}x{Colors.CYAN})",

            1,

        )

        net_mag = self.index_green_mag - self.index_red_mag

        mag_color = Colors.GREEN if net_mag >= 0 else Colors.RED

        mag_text = f"{net_mag:,.1f}"

        mag_line = _box_line(f"Index Magnitude: {mag_text}")

        mag_line = mag_line.replace(

            mag_text,

            f"{mag_color}{mag_text}{Colors.CYAN}",

            1,

        )

        gold = self.split_history.count('gold')

        purple = self.split_history.count('purple')

        green = self.split_history.count('green')

        red = self.split_history.count('red')

        splits_text = f"Splits G:{gold} P:{purple} Gr:{green} R:{red}"

        splits_line = _box_line(splits_text)

        splits_line = splits_line.replace(f"G:{gold}", f"G:{Colors.ELECTRIC}{gold}{Colors.CYAN}", 1)

        splits_line = splits_line.replace(f"P:{purple}", f"P:{Colors.PURPLE}{purple}{Colors.CYAN}", 1)

        splits_line = splits_line.replace(f"Gr:{green}", f"Gr:{Colors.GREEN}{green}{Colors.CYAN}", 1)

        splits_line = splits_line.replace(f"R:{red}", f"R:{Colors.RED}{red}{Colors.CYAN}", 1)

        lines = [

            f"  ┌{'─' * box_width}┐",

            xp_line,

            _box_line(f"Gilly Lv: {self.episode_current_level} (Ep {len(self.episode_rewards)})"),

            _box_line(f"Next Lv: {next_level_points:>10,.0f} xp"),

            _box_line(f"{bar}  {pct:>3}%"),

            _box_line(f"Entropy: {entropy_val:>6.4f}"),

            avg_line,

            pi_line,

            trend_line,

            ratio_line,

            mag_line,

            splits_line,

            _box_line(f"Badges: {badges}/8  Dex: {pokedex}/151"),

            lava_line,

            _box_line(f"Points Gained:   {'+' if gain >= 0 else ''}{gain:,.0f}"),

            _box_line(f"Points Lost:     {loss:,.0f}"),

            _box_line(f"Best Moment:     {'+' if best >= 0 else ''}{best:,.0f}"),

            _box_line(f" {breakdown_text}"),

            f"  └{'─' * box_width}┘",

        ]



        # Clear previous heartbeat box area.
        if self.heartbeat_printed:
            # Clear a fixed range that covers the previous box and any trailing lines.
            clear_lines = len(lines) + 6
            sys.stdout.write(f"\033[{clear_lines}A")
            for _ in range(clear_lines):
                sys.stdout.write("\033[2K\r\n")
            sys.stdout.write(f"\033[{clear_lines}A")

        # Print all lines (clear each line to avoid residual text)
        for line in lines:
            sys.stdout.write(f"\033[2K\r{Colors.CYAN}{line}{Colors.RESET}\n")

        self.last_heartbeat_lines = len(lines)

        self.prev_avg_reward_ema = self.avg_reward_ema

        self.prev_avg10_heartbeat = avg_recent

        self.heartbeat_printed = True

        sys.stdout.flush()



    def _score_to_level(self, score: float) -> int:

        """Map episode score to a level (monotonic during the episode)."""

        if score <= 0:

            return 1

        exponent = 1.3524365633771591

        level = int((score / 1000.0) ** (1.0 / exponent)) + 1

        first_grass_reached = bool(self.last_info.get("first_grass_reached", False))

        max_level = self.trainer_stats.MAX_LEVEL if first_grass_reached else 5

        return min(level, max_level)



    def _next_level_points(self, level: int) -> float:

        """Points needed to reach the next level."""

        exponent = 1.3524365633771591

        next_level_score = 1000.0 * (level ** exponent)

        return max(0.0, next_level_score - self.episode_peak_reward)



    def _update_episode_steps(self, level: int, force: bool = False) -> None:

        """Update step cap for the current episode based on its level."""

        new_steps = calculate_episode_steps(level)

        if not force and new_steps <= self.max_episode_steps:

            return

        self.max_episode_steps = new_steps

        self.episode_level_for_steps = level

        if getattr(self, "training_env", None) is not None:

            self.training_env.set_attr("max_episode_steps", new_steps)

    def _print_episode_box(self, info: dict):
        """Print RPG-style episode complete box."""
        return print_episode_box(self, info)
        # Clear heartbeat box so summary does not overlap.
        if self.heartbeat_printed and self.last_heartbeat_lines > 0:
            clear_lines = self.last_heartbeat_lines + 6
            sys.stdout.write(f"\033[{clear_lines}A")
            for _ in range(clear_lines):
                sys.stdout.write("\033[2K\r\n")
            sys.stdout.write(f"\033[{clear_lines}A")
            self.heartbeat_printed = False

        # Print newline to move past the heartbeat line
        print()

        ep = len(self.episode_rewards)
        r = self.episode_rewards[-1]
        avg10 = np.mean(self.episode_rewards[-10:]) if self.episode_rewards else 0
        avg_all = np.mean(self.episode_rewards) if self.episode_rewards else 0
        r_delta = r - self.prev_episode_reward
        avg10_delta = avg10 - self.prev_avg10
        avg_all_delta = avg_all - self.prev_avg_all
        lv = self.episode_current_level

        # Get game stats from info
        badges = info.get('badges', 0)
        pokedex = info.get('pokedex_owned', 0)
        best = self.trainer_stats.best_episode_reward
        total_xp = self.trainer_stats.total_xp

        # Calculate confidence from latest entropy
        # NOTE: entropy_loss = -ent_coef * entropy, so we need to recover actual entropy
        entropy_value = self.logger.name_to_value.get("train/entropy", None) if self.logger else None
        entropy_loss = self.logger.name_to_value.get("train/entropy_loss", None) if self.logger else None
        max_entropy = np.log(self.NUM_ACTIONS)  # ~2.08 for 8 actions
        if entropy_value not in (None, 0):
            actual_entropy = min(abs(entropy_value), max_entropy)
        elif entropy_loss not in (None, 0):
            ent_coef = getattr(self.model, 'ent_coef', 0.01) if self.model else 0.01
            actual_entropy = abs(entropy_loss) / ent_coef if ent_coef > 0 else max_entropy
            actual_entropy = min(actual_entropy, max_entropy)
        else:
            actual_entropy = max_entropy
        self.last_entropy = actual_entropy
        confidence = self._entropy_to_confidence(actual_entropy)

        print(f"\n  {Colors.PURPLE}╔{'═'*62}╗{Colors.RESET}")
        print(f"  {Colors.PURPLE}║{Colors.RESET}  {Colors.BOLD}{Colors.YELLOW}⚔️  EPISODE {ep} COMPLETE  ⚔️{Colors.RESET}                              {Colors.PURPLE}║{Colors.RESET}")
        print(f"  {Colors.PURPLE}╠{'═'*62}╣{Colors.RESET}")
        print(f"  {Colors.PURPLE}║{Colors.RESET}  REWARD: {Colors.ELECTRIC}{r:>10,.0f}{Colors.RESET} {Colors.DIM}({r_delta:+.0f}){Colors.RESET}  │  10-EP AVG: {Colors.WHITE}{avg10:>10,.0f}{Colors.RESET} {Colors.DIM}({avg10_delta:+.0f}){Colors.RESET}   {Colors.PURPLE}║{Colors.RESET}")
        print(f"  {Colors.PURPLE}║{Colors.RESET}  LIFETIME AVG: {Colors.WHITE}{avg_all:>10,.0f}{Colors.RESET} {Colors.DIM}({avg_all_delta:+.0f}){Colors.RESET}                          {Colors.PURPLE}║{Colors.RESET}")
        print(f"  {Colors.PURPLE}╠{'═'*62}╣{Colors.RESET}")
        print(f"  {Colors.PURPLE}║{Colors.RESET}  {Colors.CYAN}📊 CHARACTER STATS:{Colors.RESET}                                        {Colors.PURPLE}║{Colors.RESET}")
        print(f"  {Colors.PURPLE}║{Colors.RESET}    Gilly Lv: {Colors.YELLOW}{lv}{Colors.RESET}                                          {Colors.PURPLE}║{Colors.RESET}")
        print(f"  {Colors.PURPLE}║{Colors.RESET}    Badges: {Colors.YELLOW}{badges}/8{Colors.RESET}         Pokedex: {Colors.RED}{pokedex}/151{Colors.RESET}                   {Colors.PURPLE}║{Colors.RESET}")
        print(f"  {Colors.PURPLE}║{Colors.RESET}    Best Score: {Colors.GREEN}{int(best):,}{Colors.RESET}   Total XP: {Colors.WHITE}{int(total_xp):,}{Colors.RESET}                  {Colors.PURPLE}║{Colors.RESET}")
        print(f"  {Colors.PURPLE}╠{'═'*62}╣{Colors.RESET}")
        print(f"  {Colors.PURPLE}║{Colors.RESET}  {Colors.CYAN}🧠 LEARNING STATUS:{Colors.RESET}                                        {Colors.PURPLE}║{Colors.RESET}")

        # Confidence display with trend
        conf_color = Colors.GREEN if confidence > 60 else (Colors.YELLOW if confidence > 30 else Colors.RED)
        conf_diff = confidence - self.prev_confidence
        trend = ""
        if abs(conf_diff) > 1:
            if conf_diff > 0:
                trend = f" {Colors.GREEN}(↑ IMPROVING){Colors.RESET}"
            else:
                trend = f" {Colors.RED}(↓ declining){Colors.RESET}"
        print(f"  {Colors.PURPLE}║{Colors.RESET}    Confidence: {conf_color}{confidence:.5f}%{Colors.RESET}{trend}                              {Colors.PURPLE}║{Colors.RESET}")
        print(f"  {Colors.PURPLE}║{Colors.RESET}    {Colors.DIM}(0% = random guessing, 100% = fully confident){Colors.RESET}            {Colors.PURPLE}║{Colors.RESET}")
        print(f"  {Colors.PURPLE}╚{'═'*62}╝{Colors.RESET}\n")

        self._record_episode_split(r)
        self.prev_episode_reward = r
        self.prev_avg10 = avg10
        self.prev_avg_all = avg_all

        # Update policy-improvement index from episode returns (long-horizon EMA)
        if self.episode_return_ema is None:
            self.episode_return_ema = r
        else:
            alpha = 0.1
            self.episode_return_ema = (alpha * r) + ((1 - alpha) * self.episode_return_ema)
        if self.prev_episode_return_ema is None:
            self.prev_episode_return_ema = self.episode_return_ema
        ema_delta = self.episode_return_ema - self.prev_episode_return_ema
        progress_index_raw = (ema_delta / max(abs(self.prev_episode_return_ema), 1.0)) * 100.0
        if abs(progress_index_raw) > 0.01:
            self.last_progress_index = progress_index_raw
        self.policy_index = self.last_progress_index
        self.policy_index_sign = 1 if self.policy_index > 0.01 else -1 if self.policy_index < -0.01 else 0
        if self.policy_index_sign == 0:
            pass
        elif self.policy_index_sign != self.progress_streak_sign:
            self.progress_streak_sign = self.policy_index_sign
            self.progress_streak = 1
        else:
            self.progress_streak += 1
        if self.policy_index_sign > 0:
            self.index_green_count += 1
            self.index_green_mag += abs(self.policy_index)
        elif self.policy_index_sign < 0:
            self.index_red_count += 1
            self.index_red_mag += abs(self.policy_index)
        self.prev_episode_return_ema = self.episode_return_ema



    def _record_episode_split(self, reward: float) -> None:

        """Classify episode outcome relative to last 10 episodes."""

        recent = self.episode_rewards[:-1][-10:]

        best_ever = self.trainer_stats.best_episode_reward

        if not recent:

            label = "gold"

        else:

            avg_recent = float(np.mean(recent))

            best_recent = max(recent)

            if best_ever and reward >= best_ever:

                label = "gold"

            elif reward >= best_recent:

                label = "purple"

            elif reward >= avg_recent:

                label = "green"

            else:

                label = "red"

        self.split_history.append(label)

        if len(self.split_history) > 10:

            self.split_history.pop(0)



    def _check_high_score(self):

        """Celebrate new high score for the roguelite run."""

        best = self.trainer_stats.best_episode_reward

        if best > self.prev_best_episode_reward:

            print(f"\n  {Colors.ELECTRIC}╔{'═'*62}╗{Colors.RESET}")

            print(f"  {Colors.ELECTRIC}║{Colors.RESET}  {Colors.BOLD}{Colors.YELLOW}🏆  NEW HIGH SCORE!  🏆{Colors.RESET}                                {Colors.ELECTRIC}║{Colors.RESET}")

            print(f"  {Colors.ELECTRIC}║{Colors.RESET}                                                              {Colors.ELECTRIC}║{Colors.RESET}")

            print(f"  {Colors.ELECTRIC}║{Colors.RESET}  Best Score: {Colors.GREEN}{int(best):,}{Colors.RESET}                                           {Colors.ELECTRIC}║{Colors.RESET}")

            print(f"  {Colors.ELECTRIC}║{Colors.RESET}                                                              {Colors.ELECTRIC}║{Colors.RESET}")

            print(f"  {Colors.ELECTRIC}║{Colors.RESET}  {Colors.DIM}\"The journey continues...\"{Colors.RESET}                                {Colors.ELECTRIC}║{Colors.RESET}")

            print(f"  {Colors.ELECTRIC}╚{'═'*62}╝{Colors.RESET}\n")

            self.prev_best_episode_reward = best



    def _on_rollout_end(self) -> None:

        """Print PPO update box with deltas."""

        if self.logs_dir is not None:

            try:

                self.logs_dir.mkdir(parents=True, exist_ok=True)

            except Exception:

                pass

        if self.verbose > 0:

            # Print newline to move past the heartbeat line

            print()



            entropy_value = self.logger.name_to_value.get("train/entropy", None)

            entropy_loss = self.logger.name_to_value.get("train/entropy_loss", None)

            value_loss = self.logger.name_to_value.get("train/value_loss", 0)

            policy_loss = self.logger.name_to_value.get("train/policy_gradient_loss", 0)



            # Calculate current stats

            # NOTE: Prefer train/entropy when available, else recover from entropy_loss.

            max_entropy = np.log(self.NUM_ACTIONS)

            if entropy_value not in (None, 0):

                actual_entropy = min(abs(entropy_value), max_entropy)

            elif entropy_loss not in (None, 0):

                ent_coef = getattr(self.model, 'ent_coef', 0.01) if self.model else 0.01

                actual_entropy = abs(entropy_loss) / ent_coef if ent_coef > 0 else max_entropy

                actual_entropy = min(actual_entropy, max_entropy)

            else:

                actual_entropy = max_entropy

            self.last_entropy = actual_entropy

            curr_episode_count = len(self.episode_rewards)

            if self.cycle_episode_rewards:

                curr_avg_reward = float(np.mean(self.cycle_episode_rewards))

                avg_source = "episodes"

            else:

                curr_avg_reward = (self.rollout_reward_sum / self.rollout_step_count) if self.rollout_step_count else 0.0

                avg_source = "rollout"

            curr_confidence = self._entropy_to_confidence(actual_entropy)



            # Calculate deltas against previous cycle snapshot

            prev_episode_count = self.prev_episode_count

            prev_avg_reward = self.prev_avg_reward

            prev_confidence = self.prev_confidence

            ep_delta = curr_episode_count - prev_episode_count

            avg_delta = curr_avg_reward - prev_avg_reward

            cycle_model_index = (avg_delta / max(abs(prev_avg_reward), 1.0)) * 100.0

            conf_delta = curr_confidence - prev_confidence



            show_standard_update = True



            # Update previous values for next delta calculation

            self.prev_episode_count = curr_episode_count

            self.prev_avg_reward = curr_avg_reward

            self.prev_confidence = curr_confidence

            self.rollout_reward_sum = 0.0

            self.rollout_step_count = 0

            self.cycle_episode_rewards = []



            # Track last 10 learning cycles

            self.cycle_history.append({

                "avg_reward": curr_avg_reward,

                "model_index": cycle_model_index,

                "confidence": curr_confidence,

                "entropy": actual_entropy,

                "policy_loss": policy_loss,

                "value_loss": value_loss,

            })

            if len(self.cycle_history) > 10:

                self.cycle_history.pop(0)

            if len(self.cycle_history) == 10 and (self.num_timesteps // self.model.n_steps) % 10 == 0:

                show_standard_update = False

                self._print_cycle_trends(self._next_learning_color())



            if show_standard_update:

                frame_color = self._next_learning_color()

                indent = "    "

                print(f"\n{indent}{frame_color}╔{'═'*54}╗{Colors.RESET}")

                print(f"{indent}{frame_color}║{Colors.RESET}  {Colors.BOLD}📈 LEARNING UPDATE @ {self.num_timesteps:,} steps{Colors.RESET}               {frame_color}║{Colors.RESET}")

                print(f"{indent}{frame_color}╠{'═'*54}╣{Colors.RESET}")

                print(f"{indent}{frame_color}║{Colors.RESET}  {Colors.WHITE}CHANGES THIS CYCLE:{Colors.RESET}                                {frame_color}║{Colors.RESET}")



                # Episodes delta

                if ep_delta > 0:

                    print(f"{indent}{frame_color}║{Colors.RESET}    Episodes: {prev_episode_count} → {curr_episode_count} {Colors.GREEN}(+{ep_delta}){Colors.RESET}                       {frame_color}║{Colors.RESET}")



                # Avg reward delta (rollout-level)

                avg_color = Colors.GREEN if avg_delta > 0 else Colors.RED if avg_delta < 0 else Colors.WHITE

                avg_sign = "+" if avg_delta >= 0 else ""

                avg_label = "Avg Reward" if avg_source == "episodes" else "Avg Reward/Step"

                print(f"{indent}{frame_color}║{Colors.RESET}    {avg_label}: {prev_avg_reward:.0f} → {curr_avg_reward:.0f} {avg_color}({avg_sign}{avg_delta:.0f}){Colors.RESET}                 {frame_color}║{Colors.RESET}")



                # Confidence delta

                conf_color = Colors.GREEN if conf_delta > 0 else Colors.RED if conf_delta < 0 else Colors.WHITE

                conf_sign = "+" if conf_delta >= 0 else ""

                print(f"{indent}{frame_color}║{Colors.RESET}    Confidence: {prev_confidence:.5f}% → {curr_confidence:.5f}% {conf_color}({conf_sign}{conf_delta:.5f}%){Colors.RESET}               {frame_color}║{Colors.RESET}")



                if self.model and self.model.n_steps > 0 and (self.num_timesteps % self.model.n_steps) == 0:

                    ckpt_name = f"ppo_pokemon_{self.num_timesteps}_steps.zip"

                    print(f"{indent}{frame_color}║{Colors.RESET}    Checkpoint: {Colors.ELECTRIC}{ckpt_name}{Colors.RESET}                         {frame_color}║{Colors.RESET}")



                print(f"{indent}{frame_color}╠{'═'*54}╣{Colors.RESET}")

                print(f"{indent}{frame_color}║{Colors.RESET}  {Colors.DIM}TECHNICAL:{Colors.RESET}                                          {frame_color}║{Colors.RESET}")

                print(f"{indent}{frame_color}║{Colors.RESET}    Policy Loss: {policy_loss:>8.4f}    Value Loss: {value_loss:>8.4f}   {frame_color}║{Colors.RESET}")

                print(f"{indent}{frame_color}║{Colors.RESET}    Entropy: {actual_entropy:>8.4f}                              {frame_color}║{Colors.RESET}")

                print(f"{indent}{frame_color}╚{'═'*54}╝{Colors.RESET}\n")



            # Reset heartbeat so next one prints fresh (doesn't overwrite this box)

            self.heartbeat_printed = False

    def _print_cycle_trends(self, frame_color: str) -> None:
        """Print last-10-cycle trend box."""
        if len(self.cycle_history) < 2:
            return

        start = self.cycle_history[0]
        end = self.cycle_history[-1]



        def _trend_line(label: str, key: str, invert: bool = False) -> str:

            s = start[key]

            e = end[key]

            delta = e - s

            delta_for_color = -delta if invert else delta

            color = Colors.GREEN if delta_for_color > 0 else (Colors.RED if delta_for_color < 0 else Colors.WHITE)

            sign = "+" if delta >= 0 else "-"

            delta_abs = abs(delta)

            delta_text = f"{sign}{delta_abs:7.2f}"

            return f"    {frame_color}║{Colors.RESET}  {label}: {s:>8.2f} → {e:>8.2f} {color}({delta_text}){Colors.RESET}        {frame_color}║{Colors.RESET}"



        print(f"\n    {frame_color}╔{'═'*54}╗{Colors.RESET}")

        print(f"    {frame_color}║{Colors.RESET}  {Colors.BOLD}{Colors.CYAN}📊 LAST 10 CYCLES TREND{Colors.RESET}                  {frame_color}║{Colors.RESET}")

        print(f"    {frame_color}╠{'═'*54}╣{Colors.RESET}")

        print(_trend_line("Avg Reward", "avg_reward"))

        print(_trend_line("Model Index", "model_index"))

        print(_trend_line("Confidence", "confidence"))

        print(_trend_line("Entropy", "entropy", invert=True))

        print(_trend_line("Policy Loss", "policy_loss", invert=True))

        print(_trend_line("Value Loss", "value_loss", invert=True))

        print(f"    {frame_color}╚{'═'*54}╝{Colors.RESET}\n")





class TimestepsCheckpointCallback(CheckpointCallback):

    """Checkpoint callback that names files by actual timesteps."""



    def __init__(self, save_freq: int, save_path: str, name_prefix: str = "rl_model", **kwargs):

        super().__init__(save_freq=save_freq, save_path=save_path, name_prefix=name_prefix, **kwargs)



    def _on_step(self) -> bool:

        result = super()._on_step()

        if self.n_calls % self.save_freq == 0:

            timestep_name = f"{self.name_prefix}_{self.num_timesteps}_steps"

            try:

                self.model.save(os.path.join(self.save_path, timestep_name))

            except Exception:

                pass

        return result



def calculate_episode_steps(trainer_level: int) -> int:

    """Calculate max episode steps based on trainer level."""

    levels_gained = trainer_level - 1

    total_steps = int(config.BASE_STEPS_PER_EPISODE * (config.STEPS_MULTIPLIER ** levels_gained))

    return min(total_steps, config.MAX_STEPS_CAP)





def _format_checkpoint_card(path: Optional[str]) -> Optional[str]:

    if not path:

        return None

    ckpt_path = Path(path)

    if not ckpt_path.exists():

        return None



    size_mb = ckpt_path.stat().st_size / (1024 * 1024)

    mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(ckpt_path.stat().st_mtime))

    match = re.search(r"ppo_pokemon_(\d+)_steps", ckpt_path.name)

    steps = f"{int(match.group(1)):,}" if match else "unknown"



    lines = [

        f"  {Colors.BLUE}╔{'═'*58}╗{Colors.RESET}",

        f"  {Colors.BLUE}║{Colors.RESET}  {Colors.BOLD}{Colors.CYAN}🧪 RESUME CHECKPOINT{Colors.RESET}                               {Colors.BLUE}║{Colors.RESET}",

        f"  {Colors.BLUE}╠{'═'*58}╣{Colors.RESET}",

        f"  {Colors.BLUE}║{Colors.RESET}  {Colors.WHITE}File:{Colors.RESET}  {Colors.ELECTRIC}{ckpt_path.name}{Colors.RESET}                 {Colors.BLUE}║{Colors.RESET}",

        f"  {Colors.BLUE}║{Colors.RESET}  {Colors.WHITE}Path:{Colors.RESET}  {Colors.DIM}{ckpt_path}{Colors.RESET}      {Colors.BLUE}║{Colors.RESET}",

        f"  {Colors.BLUE}║{Colors.RESET}  {Colors.WHITE}Steps:{Colors.RESET} {Colors.YELLOW}{steps}{Colors.RESET}   {Colors.WHITE}Size:{Colors.RESET} {size_mb:5.1f} MB        {Colors.BLUE}║{Colors.RESET}",

        f"  {Colors.BLUE}║{Colors.RESET}  {Colors.DIM}Saved: {mtime}{Colors.RESET}                                     {Colors.BLUE}║{Colors.RESET}",

        f"  {Colors.BLUE}╚{'═'*58}╝{Colors.RESET}",

    ]

    return "\n".join(lines)





def main():

    parser = argparse.ArgumentParser(description="Pokemon Crystal PPO Training")

    parser.add_argument("--resume", type=str, help="Path to model checkpoint to resume from")

    parser.add_argument("--total-timesteps", type=int, default=1_000_000, help="Total training timesteps")

    args = parser.parse_args()



    # Auto-detect latest checkpoint if --resume not specified

    if not args.resume:

        models_dir = Path("models")

        if models_dir.exists():

            checkpoints = list(models_dir.glob("ppo_pokemon_*_steps.zip"))

            if checkpoints:

                def _step_key(path: Path) -> int:

                    match = re.search(r"ppo_pokemon_(\d+)_steps", path.name)

                    return int(match.group(1)) if match else -1

                checkpoints.sort(key=lambda p: (_step_key(p), p.stat().st_mtime))

                args.resume = str(checkpoints[-1])



    # Print banner

    print(f"\n  {Colors.PURPLE}╔{'═'*56}╗{Colors.RESET}")
    print(f"  {Colors.PURPLE}║{Colors.RESET}  {Colors.BOLD}{Colors.YELLOW}⚡ POKEMON CRYSTAL PPO AGENT ⚡{Colors.RESET}                  {Colors.PURPLE}║{Colors.RESET}")
    print(f"  {Colors.PURPLE}║{Colors.RESET}  {Colors.GHOST}👻 Proper RL with GAE & Value Baseline{Colors.RESET}            {Colors.PURPLE}║{Colors.RESET}")
    print(f"  {Colors.PURPLE}╠{'═'*56}╣{Colors.RESET}")
    print(f"  {Colors.PURPLE}║{Colors.RESET}  {Colors.WHITE}PPO: Proximal Policy Optimization{Colors.RESET}                  {Colors.PURPLE}║{Colors.RESET}")
    print(f"  {Colors.PURPLE}║{Colors.RESET}  {Colors.GREEN}Decomposed Value Heads for reward categories{Colors.RESET}       {Colors.PURPLE}║{Colors.RESET}")
    print(f"  {Colors.PURPLE}║{Colors.RESET}  {Colors.CYAN}Starter: {Colors.GHOST}Gastly{Colors.RESET} (Species {config.STARTER_SPECIES})                    {Colors.PURPLE}║{Colors.RESET}")
    print(f"  {Colors.PURPLE}╚{'═'*56}╝{Colors.RESET}")



    # Initialize trainer stats

    stats = TrainerStats()

    stats.print_stats(Colors)



    checkpoint_card = _format_checkpoint_card(args.resume)

    if checkpoint_card:

        print(checkpoint_card)



    best_level = stats.get_trainer_level()

    max_episode_steps = calculate_episode_steps(1)



    print(f"\nHigh Score: {int(stats.best_episode_reward):,} (Best Level {best_level})")

    print(f"Base Episode Steps: {max_episode_steps:,}")



    # Set Gastly as starter

    print("\nSetting Gastly as starter Pokemon...")

    set_starter()

    time.sleep(1)



    # Create environment

    print("\nCreating environment...")

    env = PokemonCrystalEnv(

        frames_per_action=1,

        save_slot=1,

        return_reward_breakdown=True,

        max_episode_steps=max_episode_steps,

    )

    env.trainer_level_provider = stats.get_trainer_level



    # Ensure directories exist

    models_dir = Path("models")

    logs_dir = Path("logs/ppo")

    models_dir.mkdir(parents=True, exist_ok=True)

    logs_dir.mkdir(parents=True, exist_ok=True)



    # Configure logger for TensorBoard

    logger = configure(str(logs_dir), ["tensorboard"])



    constraints_path = Path(__file__).parent / "model_constraints.json"

    constraints = {}

    if constraints_path.exists():

        try:

            with open(constraints_path, "r", encoding="utf-8") as f:

                constraints = json.load(f)

        except Exception:

            constraints = {}



    # Create or load model

    if args.resume and Path(args.resume).exists():

        print(f"\nResuming from checkpoint: {args.resume}")

        model = PPO.load(

            args.resume,

            env=env,

            custom_objects={"policy_class": DecomposedActorCriticPolicy},

        )

        model.set_logger(logger)

    else:

        print("\nCreating new PPO model...")

        model = PPO(

            policy=DecomposedActorCriticPolicy,

            env=env,

            learning_rate=constraints.get("learning_rate", config.LEARNING_RATE),

            n_steps=int(constraints.get("n_steps", 100)),            # Fast updates for visible entropy movement

            batch_size=int(constraints.get("batch_size", 64)),       # Mini-batch size for updates

            n_epochs=int(constraints.get("n_epochs", 10)),           # Epochs per PPO update

            gamma=constraints.get("gamma", 0.99),                    # Discount factor (long-horizon credit)

            gae_lambda=constraints.get("gae_lambda", 0.95),          # GAE parameter for advantage estimation

            clip_range=constraints.get("clip_range", 0.2),           # PPO clipping parameter

            clip_range_vf=None,     # Don't clip value function (can help stability)

            ent_coef=constraints.get("ent_coef", 0.05),              # Restore exploration to avoid action collapse

            vf_coef=constraints.get("vf_coef", 0.5),                 # Value function coefficient

            max_grad_norm=constraints.get("max_grad_norm", 0.5),     # Gradient clipping

            verbose=0,              # Suppress SB3 logging

            tensorboard_log=str(logs_dir),

            device="auto",

        )

        model.set_logger(logger)



    # Create callbacks

    training_callback = PokemonTrainingCallback(

        trainer_stats=stats,

        max_episode_steps=max_episode_steps,

        verbose=1,

        constraints_path=constraints_path,

        logs_dir=logs_dir,

    )



    checkpoint_callback = TimestepsCheckpointCallback(

        save_freq=model.n_steps,

        save_path=str(models_dir),

        name_prefix="ppo_pokemon",

        save_replay_buffer=False,

        save_vecnormalize=False,

    )



    print(f"\nIMPORTANT: Make sure you have saved a state in BizHawk slot 1!")

    print(f"  (In BizHawk: File > Save State > Slot 1, or press Shift+F1)")

    print(f"\nStarting PPO training for {args.total_timesteps:,} timesteps...")

    print(f"  n_steps={model.n_steps}, batch_size={model.batch_size}, n_epochs={model.n_epochs}")

    print(f"\nTensorBoard logs: {logs_dir}")

    print(f"  Run: tensorboard --logdir={logs_dir}")

    print(f"\nPress Ctrl+C to stop training\n")



    try:

        model.learn(

            total_timesteps=args.total_timesteps,

            callback=[training_callback, checkpoint_callback],

            progress_bar=False,  # We have our own progress display

            reset_num_timesteps=args.resume is None,

        )

    except KeyboardInterrupt:

        print("\n\nTraining stopped by user.")



    # Save final model

    final_path = models_dir / "ppo_pokemon_final.zip"

    model.save(str(final_path))

    print(f"\nFinal model saved: {final_path}")



    # Print final stats

    print(f"\nTraining Summary:")

    print(f"  Total Episodes: {len(training_callback.episode_rewards)}")

    print(f"  Best Level (all-time): {stats.get_trainer_level()}")

    if training_callback.episode_rewards:

        print(f"  Best Episode Reward: {max(training_callback.episode_rewards):.1f}")

        print(f"  Avg Reward (last 10): {np.mean(training_callback.episode_rewards[-10:]):.1f}")





if __name__ == "__main__":

    main()



