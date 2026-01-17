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
from tqdm import tqdm
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
    """Custom callback with tqdm progress bar that updates in place."""

    def __init__(self, trainer_stats: TrainerStats, total_timesteps: int, verbose: int = 1):
        super().__init__(verbose)
        self.trainer_stats = trainer_stats
        self.total_timesteps = total_timesteps

        # Episode tracking
        self.episode_rewards = []
        self.episode_lengths = []
        self.current_episode_reward = 0.0
        self.current_episode_length = 0
        self.reward_breakdown_totals = {cat: 0.0 for cat in REWARD_CATEGORIES}

        # tqdm progress bar (created on first step)
        self.pbar = None

    def _on_training_start(self) -> None:
        """Called when training starts."""
        self.pbar = tqdm(
            total=self.total_timesteps,
            desc=f"{Colors.YELLOW}⚡ Training{Colors.RESET}",
            unit="step",
            dynamic_ncols=True,
            colour="yellow",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}] {postfix}"
        )

    def _on_step(self) -> bool:
        """Called after every step."""
        # Update progress bar
        if self.pbar:
            self.pbar.update(1)

        # Get info from the environment
        infos = self.locals.get("infos", [{}])
        rewards = self.locals.get("rewards", [0])
        dones = self.locals.get("dones", [False])

        for info, reward, done in zip(infos, rewards, dones):
            self.current_episode_reward += reward
            self.current_episode_length += 1

            # Track breakdown if available
            breakdown = info.get("reward_breakdown", {})
            for cat, val in breakdown.items():
                self.reward_breakdown_totals[cat] += val

            if done:
                self.episode_rewards.append(self.current_episode_reward)
                self.episode_lengths.append(self.current_episode_length)
                self.trainer_stats.add_episode_reward(self.current_episode_reward)
                self.trainer_stats.finish_episode(info)

                # Print colorful episode summary (tqdm.write doesn't break the bar)
                ep_num = len(self.episode_rewards)
                avg = np.mean(self.episode_rewards[-10:]) if len(self.episode_rewards) >= 10 else self.episode_rewards[-1]
                trainer_lv = self.trainer_stats.get_trainer_level()
                tqdm.write(
                    f"  {Colors.CYAN}═══ Episode {ep_num} ═══{Colors.RESET} "
                    f"Reward: {Colors.ELECTRIC}{self.episode_rewards[-1]:>7.0f}{Colors.RESET} │ "
                    f"Avg: {Colors.WHITE}{avg:>6.0f}{Colors.RESET} │ "
                    f"Lv: {Colors.YELLOW}{trainer_lv}{Colors.RESET}"
                )

                # Reset episode tracking
                self.current_episode_reward = 0.0
                self.current_episode_length = 0
                self.reward_breakdown_totals = {cat: 0.0 for cat in REWARD_CATEGORIES}

        # Update progress bar postfix with colorful stats
        if self.pbar and self.num_timesteps % 100 == 0:
            avg_reward = np.mean(self.episode_rewards[-10:]) if self.episode_rewards else 0
            trainer_level = self.trainer_stats.get_trainer_level()

            # Colorful postfix string
            postfix = (
                f"{Colors.CYAN}Ep:{Colors.WHITE}{len(self.episode_rewards):>3}{Colors.RESET} │ "
                f"{Colors.GREEN}Reward:{Colors.ELECTRIC}{self.current_episode_reward:>7.0f}{Colors.RESET} │ "
                f"{Colors.DIM}Avg:{Colors.WHITE}{avg_reward:>6.0f}{Colors.RESET} │ "
                f"{Colors.PURPLE}Lv:{Colors.YELLOW}{trainer_level}{Colors.RESET}"
            )
            self.pbar.set_postfix_str(postfix)

        return True

    def _on_training_end(self) -> None:
        """Called when training ends."""
        if self.pbar:
            self.pbar.close()



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
            verbose=0,              # Disable SB3's own logging (we have custom callback)
            tensorboard_log=str(logs_dir),
            device="auto",
        )
        model.set_logger(logger)

    # Create callbacks
    training_callback = PokemonTrainingCallback(
        trainer_stats=stats,
        total_timesteps=args.total_timesteps,
        verbose=1
    )

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
