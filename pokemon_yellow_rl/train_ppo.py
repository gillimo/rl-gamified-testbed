"""Pokemon Yellow PPO Training - Proper RL with value baseline and GAE.

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

from pokemon_env import PokemonYellowEnv, REWARD_CATEGORIES
from decomposed_policy import DecomposedActorCriticPolicy
from src.trainer_stats import TrainerStats
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
    """Custom callback for Pokemon-specific training diagnostics.

    Prints summary at end of each episode and after each PPO update.
    """

    def __init__(self, trainer_stats: TrainerStats, verbose: int = 1):
        super().__init__(verbose)
        self.trainer_stats = trainer_stats

        # Episode tracking
        self.episode_rewards = []
        self.episode_lengths = []
        self.current_episode_reward = 0.0
        self.current_episode_length = 0
        self.reward_breakdown_totals = {cat: 0.0 for cat in REWARD_CATEGORIES}

        # Interval tracking (for PPO update summaries)
        self.interval_reward = 0.0
        self.interval_max_gain = 0.0
        self.interval_max_loss = 0.0

    def _on_step(self) -> bool:
        """Called after every step."""
        # Get info from the environment
        infos = self.locals.get("infos", [{}])
        rewards = self.locals.get("rewards", [0])
        dones = self.locals.get("dones", [False])

        for info, reward, done in zip(infos, rewards, dones):
            self.current_episode_reward += reward
            self.current_episode_length += 1
            self.interval_reward += reward

            # Track breakdown if available
            breakdown = info.get("reward_breakdown", {})
            for cat, val in breakdown.items():
                self.reward_breakdown_totals[cat] += val

            # Track max gains/losses
            if reward > self.interval_max_gain:
                self.interval_max_gain = reward
            if reward < self.interval_max_loss:
                self.interval_max_loss = reward

            if done:
                self.episode_rewards.append(self.current_episode_reward)
                self.episode_lengths.append(self.current_episode_length)
                self.trainer_stats.add_episode_reward(self.current_episode_reward)
                self.trainer_stats.finish_episode(info)

                # Print episode summary (only on episode end)
                self._print_episode_summary()

                # Reset episode tracking
                self.current_episode_reward = 0.0
                self.current_episode_length = 0
                self.reward_breakdown_totals = {cat: 0.0 for cat in REWARD_CATEGORIES}
                self.interval_reward = 0.0
                self.interval_max_gain = 0.0
                self.interval_max_loss = 0.0

        return True

    def _print_episode_summary(self):
        """Print summary at end of each episode (not every step)."""
        avg_reward = np.mean(self.episode_rewards[-10:]) if self.episode_rewards else 0
        trainer_level = self.trainer_stats.get_trainer_level()
        ep_num = len(self.episode_rewards)

        print(f"  {Colors.CYAN}Episode {ep_num:>4}{Colors.RESET} │ "
              f"Steps: {self.num_timesteps:>7,} │ "
              f"Reward: {Colors.ELECTRIC}{self.episode_rewards[-1]:>8.1f}{Colors.RESET} │ "
              f"Avg(10): {Colors.WHITE}{avg_reward:>8.1f}{Colors.RESET} │ "
              f"Trainer Lv: {Colors.YELLOW}{trainer_level}{Colors.RESET}")

    def _on_rollout_end(self) -> None:
        """Called when a rollout (n_steps) completes."""
        # Print detailed diagnostics after each PPO update
        if self.verbose > 0 and len(self.episode_rewards) > 0:
            print()  # New line after heartbeat
            self._print_diagnostics()

    def _print_diagnostics(self):
        """Print model diagnostics after PPO update."""
        trainer_level = self.trainer_stats.get_trainer_level()
        avg_reward = np.mean(self.episode_rewards[-10:]) if self.episode_rewards else 0
        avg_length = np.mean(self.episode_lengths[-10:]) if self.episode_lengths else 0

        # Get value/policy metrics from logger
        entropy = self.logger.name_to_value.get("train/entropy_loss", 0)
        value_loss = self.logger.name_to_value.get("train/value_loss", 0)
        policy_loss = self.logger.name_to_value.get("train/policy_gradient_loss", 0)
        clip_fraction = self.logger.name_to_value.get("train/clip_fraction", 0)

        print(f"\n  {Colors.PURPLE}╔{'═'*60}╗{Colors.RESET}")
        print(f"  {Colors.PURPLE}║{Colors.RESET}  {Colors.BOLD}PPO UPDATE - Step {self.num_timesteps:,}{Colors.RESET}                              {Colors.PURPLE}║{Colors.RESET}")
        print(f"  {Colors.PURPLE}╠{'═'*60}╣{Colors.RESET}")
        print(f"  {Colors.PURPLE}║{Colors.RESET}  Trainer Level: {Colors.YELLOW}{trainer_level:>3}{Colors.RESET}      Episodes: {Colors.WHITE}{len(self.episode_rewards):>5}{Colors.RESET}              {Colors.PURPLE}║{Colors.RESET}")
        print(f"  {Colors.PURPLE}║{Colors.RESET}  Avg Reward (10ep): {Colors.ELECTRIC}{avg_reward:>10.1f}{Colors.RESET}                          {Colors.PURPLE}║{Colors.RESET}")
        print(f"  {Colors.PURPLE}║{Colors.RESET}  Avg Length (10ep): {Colors.WHITE}{avg_length:>10.0f}{Colors.RESET}                          {Colors.PURPLE}║{Colors.RESET}")
        print(f"  {Colors.PURPLE}╠{'═'*60}╣{Colors.RESET}")
        print(f"  {Colors.PURPLE}║{Colors.RESET}  {Colors.DIM}Policy Loss:{Colors.RESET}  {policy_loss:>10.4f}                              {Colors.PURPLE}║{Colors.RESET}")
        print(f"  {Colors.PURPLE}║{Colors.RESET}  {Colors.DIM}Value Loss:{Colors.RESET}   {value_loss:>10.4f}                              {Colors.PURPLE}║{Colors.RESET}")
        print(f"  {Colors.PURPLE}║{Colors.RESET}  {Colors.DIM}Entropy:{Colors.RESET}      {abs(entropy):>10.4f}                              {Colors.PURPLE}║{Colors.RESET}")
        print(f"  {Colors.PURPLE}║{Colors.RESET}  {Colors.DIM}Clip Frac:{Colors.RESET}    {clip_fraction:>10.4f}                              {Colors.PURPLE}║{Colors.RESET}")
        print(f"  {Colors.PURPLE}╚{'═'*60}╝{Colors.RESET}")


def calculate_episode_steps(trainer_level: int) -> int:
    """Calculate max episode steps based on trainer level."""
    levels_gained = trainer_level - 1
    total_steps = int(config.BASE_STEPS_PER_EPISODE * (config.STEPS_MULTIPLIER ** levels_gained))
    return min(total_steps, config.MAX_STEPS_CAP)


def main():
    parser = argparse.ArgumentParser(description="Pokemon Yellow PPO Training")
    parser.add_argument("--resume", type=str, help="Path to model checkpoint to resume from")
    parser.add_argument("--total-timesteps", type=int, default=1_000_000, help="Total training timesteps")
    args = parser.parse_args()

    # Print banner
    print(f"\n  {Colors.PURPLE}╔{'═'*56}╗{Colors.RESET}")
    print(f"  {Colors.PURPLE}║{Colors.RESET}  {Colors.BOLD}{Colors.YELLOW}⚡ POKEMON YELLOW PPO AGENT ⚡{Colors.RESET}                  {Colors.PURPLE}║{Colors.RESET}")
    print(f"  {Colors.PURPLE}║{Colors.RESET}  {Colors.GHOST}👻 Proper RL with GAE & Value Baseline{Colors.RESET}            {Colors.PURPLE}║{Colors.RESET}")
    print(f"  {Colors.PURPLE}╠{'═'*56}╣{Colors.RESET}")
    print(f"  {Colors.PURPLE}║{Colors.RESET}  {Colors.WHITE}PPO: Proximal Policy Optimization{Colors.RESET}                  {Colors.PURPLE}║{Colors.RESET}")
    print(f"  {Colors.PURPLE}║{Colors.RESET}  {Colors.GREEN}Decomposed Value Heads for reward categories{Colors.RESET}       {Colors.PURPLE}║{Colors.RESET}")
    print(f"  {Colors.PURPLE}║{Colors.RESET}  {Colors.CYAN}Starter: {Colors.GHOST}Gastly{Colors.RESET} (Species {config.STARTER_SPECIES})                    {Colors.PURPLE}║{Colors.RESET}")
    print(f"  {Colors.PURPLE}╚{'═'*56}╝{Colors.RESET}")

    # Initialize trainer stats
    stats = TrainerStats()
    trainer_level = stats.get_trainer_level()
    max_episode_steps = calculate_episode_steps(trainer_level)

    print(f"\nTrainer Level: {trainer_level}")
    print(f"Max Episode Steps: {max_episode_steps:,}")

    # Set Gastly as starter
    print("\nSetting Gastly as starter Pokemon...")
    set_starter()
    time.sleep(1)

    # Create environment
    print("\nCreating environment...")
    env = PokemonYellowEnv(
        frames_per_action=4,
        save_slot=1,
        return_reward_breakdown=True,
        max_episode_steps=max_episode_steps,
    )

    # Ensure directories exist
    models_dir = Path("pokemon_yellow_rl/models")
    logs_dir = Path("pokemon_yellow_rl/logs/ppo")
    models_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Configure logger for TensorBoard
    logger = configure(str(logs_dir), ["stdout", "tensorboard"])

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
            learning_rate=config.LEARNING_RATE,
            n_steps=1024,           # Steps before each update (fits within early episodes)
            batch_size=64,          # Mini-batch size for updates
            n_epochs=10,            # Epochs per PPO update
            gamma=0.99,             # Discount factor (long-horizon credit)
            gae_lambda=0.95,        # GAE parameter for advantage estimation
            clip_range=0.2,         # PPO clipping parameter
            clip_range_vf=None,     # Don't clip value function (can help stability)
            ent_coef=0.01,          # Entropy bonus for exploration
            vf_coef=0.5,            # Value function coefficient
            max_grad_norm=0.5,      # Gradient clipping
            verbose=1,
            tensorboard_log=str(logs_dir),
            device="auto",
        )
        model.set_logger(logger)

    # Create callbacks
    training_callback = PokemonTrainingCallback(trainer_stats=stats, verbose=1)

    checkpoint_callback = CheckpointCallback(
        save_freq=5000,
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
    print(f"  Final Trainer Level: {stats.get_trainer_level()}")
    if training_callback.episode_rewards:
        print(f"  Best Episode Reward: {max(training_callback.episode_rewards):.1f}")
        print(f"  Avg Reward (last 10): {np.mean(training_callback.episode_rewards[-10:]):.1f}")


if __name__ == "__main__":
    main()
