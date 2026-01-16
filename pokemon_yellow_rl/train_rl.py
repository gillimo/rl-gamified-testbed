"""Pokemon Yellow RL Training Loop"""
import torch
import torch.optim as optim
import torch.nn.functional as F
import time
from pathlib import Path

from src.policy_network import PolicyNetwork, normalize_state
from src.reward_calculator import RewardCalculator
from src.game_interface import GameInterface
from src.experience_buffer import ExperienceBuffer
from src.trainer_stats import TrainerStats
from set_starter import set_starter
import config


def train_step(policy, optimizer, batch):
    """Train policy network on batch of experiences."""
    import numpy as np
    states, actions, rewards, next_states = [], [], [], []

    for state, action, reward, next_state in batch:
        states.append(normalize_state(state))
        actions.append(action)
        rewards.append(reward)
        next_states.append(normalize_state(next_state))

    states = torch.FloatTensor(np.array(states))
    actions = torch.LongTensor(np.array(actions))
    rewards = torch.FloatTensor(np.array(rewards))
    next_states = torch.FloatTensor(np.array(next_states))

    # Policy gradient loss
    action_probs = policy(states)
    selected_probs = action_probs.gather(1, actions.unsqueeze(1)).squeeze()

    # REINFORCE: maximize log prob weighted by reward
    loss = -(torch.log(selected_probs + 1e-10) * rewards).mean()

    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

    return loss.item()


def calculate_episode_steps(trainer_level: int) -> int:
    """Calculate steps for this episode based on Trainer Level (Persistent RPG progression).

    Exponential growth: base * (multiplier ^ levels_gained)
    """
    levels_gained = trainer_level - 1
    total_steps = int(config.BASE_STEPS_PER_EPISODE * (config.STEPS_MULTIPLIER ** levels_gained))
    return min(total_steps, config.MAX_STEPS_CAP)


def main():
    print("=" * 60)
    print("  POKEMON YELLOW RL AGENT - ROGUELITE MODE")
    print("  Hard reset each episode. Level up = more steps!")
    print(f"  Starter: Gastly (Species {config.STARTER_SPECIES})")
    print("=" * 60)

    # Setup
    policy = PolicyNetwork(state_size=config.STATE_SIZE, action_size=config.ACTION_SIZE, hidden_size=config.HIDDEN_SIZE)
    optimizer = optim.Adam(policy.parameters(), lr=config.LEARNING_RATE)
    game = GameInterface(frames_per_action=4)
    reward_calc = RewardCalculator()
    buffer = ExperienceBuffer(maxlen=config.BUFFER_SIZE)
    stats = TrainerStats()

    # Training params
    epsilon = config.EPSILON_START

    # Set Gastly as starter (send command to Lua)
    print("\nSetting Gastly as starter Pokemon...")
    set_starter()
    time.sleep(1)  # Give Lua time to process

    # Ensure models folder exists
    Path("pokemon_yellow_rl/models").mkdir(parents=True, exist_ok=True)

    print("\nStarting training (Roguelite Mode)...")
    print(f"Base steps: {config.BASE_STEPS_PER_EPISODE} × {config.STEPS_MULTIPLIER}^level (cap: {config.MAX_STEPS_CAP:,})")
    print(f"Exploration (epsilon): {config.EPSILON_START} -> {config.EPSILON_END}")
    print("\nIMPORTANT: Make sure you have saved a state in BizHawk slot 1!")
    print("  (In BizHawk: File > Save State > Slot 1, or press Shift+F1)")
    print("\nPress Ctrl+C to stop training\n")

    try:
        while True:
            # Calculate steps for this episode based on persistent Trainer Level
            current_trainer_level = stats.get_trainer_level()
            episode_steps = calculate_episode_steps(current_trainer_level)

            # Start new episode (hard reset)
            game.reset()
            reward_calc.reset()
            prev_state = game.get_state()
            episode_reward = 0
            episode_max_level = config.STARTER_LEVEL

            print(f"\n--- Episode {stats.episode_count + 1} | Steps: {episode_steps} | Trainer Level: {current_trainer_level} ---")

            interval_max_gain = -float('inf')
            interval_max_loss = float('inf')

            for step in range(episode_steps):
                # Select action (epsilon-greedy)
                state_vec = normalize_state(prev_state)
                action = policy.select_action(state_vec, epsilon=epsilon)

                # Execute action
                game.send_action(action)
                curr_state = game.get_state()

                # Track max level this episode
                party = curr_state.get('party', [])
                if party:
                    for mon in party:
                        if mon and mon.get('level', 0) > episode_max_level:
                            episode_max_level = mon['level']

                # Calculate reward
                reward = reward_calc.calculate_reward(prev_state, curr_state)
                episode_reward += reward
                if episode_reward < 0:
                    episode_reward = 0.0

                interval_max_gain = max(interval_max_gain, reward)
                interval_max_loss = min(interval_max_loss, reward)

                # Debug: flag suspicious rewards
                if reward > 1000:
                    print(f"  [DEBUG] High reward {reward:.0f} - badges:{curr_state.get('badges')}, pokedex:{curr_state.get('pokedex_owned')}")

                # Store experience
                buffer.add(prev_state, action, reward, curr_state)
                stats.add_episode_reward(reward)

                # Train every 32 steps
                if len(buffer) >= 32 and step % 32 == 0:
                    batch = buffer.sample(32)
                    loss = train_step(policy, optimizer, batch)

                prev_state = curr_state

                # Print periodic updates
                if step % 100 == 0:
                    if interval_max_gain == -float('inf'): interval_max_gain = 0.0
                    if interval_max_loss == float('inf'): interval_max_loss = 0.0
                    print(f"  [Step {step:4d}/{episode_steps}] Reward: {episode_reward:8.1f} | Gain: {interval_max_gain:6.1f} | Loss: {interval_max_loss:6.1f} | Pos: ({curr_state.get('x', 0)}, {curr_state.get('y', 0)})")
                    interval_max_gain = -float('inf')
                    interval_max_loss = float('inf')

            # Episode complete - check for level up
            old_level = current_trainer_level
            stats.finish_episode(curr_state)
            new_level = stats.get_trainer_level()
            
            if new_level > old_level:
                old_steps = calculate_episode_steps(old_level)
                new_steps = calculate_episode_steps(new_level)
                print(f"\n  *** TRAINER LEVEL UP: {old_level} -> {new_level}! Steps: {old_steps} -> {new_steps} ***")

            stats.print_stats()

            # Decay exploration
            epsilon = max(config.EPSILON_END, epsilon * config.EPSILON_DECAY)

            # Save model every 10 episodes
            if stats.episode_count % 10 == 0:
                model_path = f"pokemon_yellow_rl/models/policy_ep{stats.episode_count}.pt"
                torch.save(policy.state_dict(), model_path)
                print(f"  [SAVED] Model checkpoint: {model_path}")

    except KeyboardInterrupt:
        print("\n\nTraining stopped by user.")
        print(f"Total episodes: {stats.episode_count}")
        final_trainer_level = stats.get_trainer_level()
        print(f"Final Trainer Level: {final_trainer_level}")
        print(f"Steps/Episode Capacity: {calculate_episode_steps(final_trainer_level)}")

        # Save final model
        final_path = f"pokemon_yellow_rl/models/policy_final_ep{stats.episode_count}.pt"
        torch.save(policy.state_dict(), final_path)
        print(f"\nFinal model saved: {final_path}")


if __name__ == "__main__":
    main()
