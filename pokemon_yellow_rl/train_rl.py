"""Pokemon Yellow RL Training Loop"""
import os
import sys
import torch
import torch.optim as optim
import torch.nn.functional as F
import time
from pathlib import Path

# Enable ANSI colors on Windows
if sys.platform == 'win32':
    os.system('color')

from src.policy_network import PolicyNetwork, normalize_state
from src.reward_calculator import RewardCalculator
from src.game_interface import GameInterface
from src.experience_buffer import ExperienceBuffer
from src.trainer_stats import TrainerStats
from set_starter import set_starter
import config

# Pokemon-themed ANSI colors
class Colors:
    YELLOW = '\033[93m'      # Pikachu yellow
    RED = '\033[91m'         # Charizard red
    BLUE = '\033[94m'        # Blastoise blue
    GREEN = '\033[92m'       # Bulbasaur green
    PURPLE = '\033[95m'      # Gengar purple
    CYAN = '\033[96m'        # Water/Ice
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

    # Pokemon type colors
    FIRE = '\033[38;5;208m'   # Orange
    ELECTRIC = '\033[38;5;226m'  # Bright yellow
    GRASS = '\033[38;5;40m'   # Bright green
    POISON = '\033[38;5;129m' # Purple
    GHOST = '\033[38;5;99m'   # Ghost purple


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
    print(f"\n  {Colors.PURPLE}╔{'═'*56}╗{Colors.RESET}")
    print(f"  {Colors.PURPLE}║{Colors.RESET}  {Colors.BOLD}{Colors.YELLOW}⚡ POKEMON YELLOW RL AGENT ⚡{Colors.RESET}                    {Colors.PURPLE}║{Colors.RESET}")
    print(f"  {Colors.PURPLE}║{Colors.RESET}  {Colors.GHOST}👻 Roguelite Mode - Gastly Edition{Colors.RESET}                  {Colors.PURPLE}║{Colors.RESET}")
    print(f"  {Colors.PURPLE}╠{'═'*56}╣{Colors.RESET}")
    print(f"  {Colors.PURPLE}║{Colors.RESET}  {Colors.WHITE}Hard reset each episode{Colors.RESET}                              {Colors.PURPLE}║{Colors.RESET}")
    print(f"  {Colors.PURPLE}║{Colors.RESET}  {Colors.GREEN}Level up = more steps!{Colors.RESET}                               {Colors.PURPLE}║{Colors.RESET}")
    print(f"  {Colors.PURPLE}║{Colors.RESET}  {Colors.CYAN}Starter: {Colors.GHOST}Gastly{Colors.RESET} (Species {config.STARTER_SPECIES})                      {Colors.PURPLE}║{Colors.RESET}")
    print(f"  {Colors.PURPLE}╚{'═'*56}╝{Colors.RESET}")

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

            print(f"\n{Colors.CYAN}{'─'*60}")
            print(f"  Episode {Colors.WHITE}{Colors.BOLD}{stats.episode_count + 1}{Colors.RESET}{Colors.CYAN} │ Steps: {Colors.WHITE}{episode_steps:,}{Colors.CYAN} │ Trainer Lv: {Colors.YELLOW}{current_trainer_level}{Colors.RESET}")
            print(f"{Colors.CYAN}{'─'*60}{Colors.RESET}")

            # Heartbeat tracking
            interval_total_gain = 0.0
            interval_total_loss = 0.0
            interval_max_gain = 0.0
            interval_max_loss = 0.0
            interval_max_gain_name = "None"
            interval_max_loss_name = "None"

            def get_reward_name(prev_s, curr_s, reward_val):
                """Identify what caused this reward."""
                if reward_val > 0:
                    if curr_s.get('badges', 0) > prev_s.get('badges', 0):
                        return "BADGE!"
                    if curr_s.get('pokedex_owned', 0) > prev_s.get('pokedex_owned', 0):
                        return "Caught Pokemon"
                    for i, mon in enumerate(curr_s.get('party', [])):
                        prev_mon = prev_s.get('party', [{}] * 6)[i] if i < len(prev_s.get('party', [])) else {}
                        if mon and prev_mon:
                            if mon.get('level', 0) > prev_mon.get('level', 0):
                                return "Level Up"
                            if mon.get('hp', 0) > prev_mon.get('hp', 0):
                                return "Healed"
                    if curr_s.get('map') != prev_s.get('map'):
                        return "New Area"
                    if curr_s.get('in_battle', 0) > 0:
                        if curr_s.get('enemy_hp', 0) < prev_s.get('enemy_hp', 0):
                            return "Damage Dealt"
                        return "Battle Action"
                    return "Exploration"
                else:
                    if curr_s.get('text_box_id', 0) > 0:
                        menu = curr_s.get('menu_item', 0)
                        if menu == 4: return "Save Menu"
                        if menu == 5: return "Options Menu"
                        if menu == 6: return "Exit Menu"
                        return "Menu Penalty"
                    for i, mon in enumerate(curr_s.get('party', [])):
                        prev_mon = prev_s.get('party', [{}] * 6)[i] if i < len(prev_s.get('party', [])) else {}
                        if mon and prev_mon and prev_mon.get('hp', 0) > 0 and mon.get('hp', 0) == 0:
                            return "Pokemon Fainted"
                    if (curr_s.get('map'), curr_s.get('x'), curr_s.get('y')) == (prev_s.get('map'), prev_s.get('x'), prev_s.get('y')):
                        return "Stuck"
                    return "Lava Mode"

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

                # Track gains and losses with names
                if reward > 0:
                    interval_total_gain += reward
                    if reward > interval_max_gain:
                        interval_max_gain = reward
                        interval_max_gain_name = get_reward_name(prev_state, curr_state, reward)
                elif reward < 0:
                    interval_total_loss += reward
                    if reward < interval_max_loss:
                        interval_max_loss = reward
                        interval_max_loss_name = get_reward_name(prev_state, curr_state, reward)

                # Debug: flag suspicious rewards
                if reward > 1000:
                    print(f"  {Colors.FIRE}[!] HIGH REWARD {reward:.0f}{Colors.RESET} - badges:{curr_state.get('badges')}, pokedex:{curr_state.get('pokedex_owned')}")

                # Store experience
                buffer.add(prev_state, action, reward, curr_state)
                stats.add_episode_reward(reward)

                # Train every 32 steps
                if len(buffer) >= 32 and step % 32 == 0:
                    batch = buffer.sample(32)
                    loss = train_step(policy, optimizer, batch)

                prev_state = curr_state

                # Heartbeat: Live-updating box (redraws in place every step)
                pct = int((step / episode_steps) * 100)
                bar_filled = pct // 5
                bar = f"{'█' * bar_filled}{'░' * (20 - bar_filled)}"

                # Move cursor up 12 lines to redraw box (if not first draw)
                if step > 0:
                    print(f"\033[12A", end='')

                print(f"  {Colors.CYAN}┌{'─'*56}┐{Colors.RESET}\033[K")
                print(f"  {Colors.CYAN}│{Colors.RESET} {Colors.BOLD}Step {step:,}/{episode_steps:,}{Colors.RESET}  [{Colors.YELLOW}{bar}{Colors.RESET}] {pct}%{' ' * (10 - len(str(pct)))} {Colors.CYAN}│{Colors.RESET}\033[K")
                print(f"  {Colors.CYAN}├{'─'*56}┤{Colors.RESET}\033[K")
                print(f"  {Colors.CYAN}│{Colors.RESET}  {Colors.WHITE}Total Reward:{Colors.RESET}  {Colors.ELECTRIC}{episode_reward:>12,.1f}{Colors.RESET}                      {Colors.CYAN}│{Colors.RESET}\033[K")
                print(f"  {Colors.CYAN}│{Colors.RESET}  {Colors.GREEN}Total Gain:{Colors.RESET}    {Colors.GREEN}+{interval_total_gain:>11,.1f}{Colors.RESET}                      {Colors.CYAN}│{Colors.RESET}\033[K")
                print(f"  {Colors.CYAN}│{Colors.RESET}  {Colors.RED}Total Loss:{Colors.RESET}    {Colors.RED}{interval_total_loss:>12,.1f}{Colors.RESET}                      {Colors.CYAN}│{Colors.RESET}\033[K")
                print(f"  {Colors.CYAN}├{'─'*56}┤{Colors.RESET}\033[K")
                print(f"  {Colors.CYAN}│{Colors.RESET}  {Colors.GREEN}Best Gain:{Colors.RESET}     {Colors.GREEN}+{interval_max_gain:>8,.1f}{Colors.RESET}  {Colors.DIM}({interval_max_gain_name:<15}){Colors.RESET} {Colors.CYAN}│{Colors.RESET}\033[K")
                print(f"  {Colors.CYAN}│{Colors.RESET}  {Colors.RED}Worst Loss:{Colors.RESET}    {Colors.RED}{interval_max_loss:>9,.1f}{Colors.RESET}  {Colors.DIM}({interval_max_loss_name:<15}){Colors.RESET} {Colors.CYAN}│{Colors.RESET}\033[K")
                print(f"  {Colors.CYAN}├{'─'*56}┤{Colors.RESET}\033[K")
                print(f"  {Colors.CYAN}│{Colors.RESET}  {Colors.DIM}Position: ({curr_state.get('x', 0):>3}, {curr_state.get('y', 0):>3}) Map: {curr_state.get('map', 0):>3}{Colors.RESET}                    {Colors.CYAN}│{Colors.RESET}\033[K")
                print(f"  {Colors.CYAN}└{'─'*56}┘{Colors.RESET}\033[K", end='', flush=True)

                # Reset interval tracking every 100 steps
                if step % 100 == 0 and step > 0:
                    interval_total_gain = 0.0
                    interval_total_loss = 0.0
                    interval_max_gain = 0.0
                    interval_max_loss = 0.0
                    interval_max_gain_name = "None"
                    interval_max_loss_name = "None"

            # Move past the box for episode end
            print("\n")

            # Episode complete - check for level up
            old_level = current_trainer_level
            stats.finish_episode(curr_state)
            new_level = stats.get_trainer_level()

            if new_level > old_level:
                old_steps = calculate_episode_steps(old_level)
                new_steps = calculate_episode_steps(new_level)
                print(f"\n  {Colors.ELECTRIC}{'★' * 20}{Colors.RESET}")
                print(f"  {Colors.ELECTRIC}★{Colors.RESET}  {Colors.BOLD}{Colors.YELLOW}TRAINER LEVEL UP!{Colors.RESET}  {Colors.ELECTRIC}★{Colors.RESET}")
                print(f"  {Colors.ELECTRIC}★{Colors.RESET}  {Colors.WHITE}Level {Colors.RED}{old_level}{Colors.WHITE} → {Colors.GREEN}{new_level}{Colors.RESET}        {Colors.ELECTRIC}★{Colors.RESET}")
                print(f"  {Colors.ELECTRIC}★{Colors.RESET}  {Colors.DIM}Steps: {old_steps:,} → {new_steps:,}{Colors.RESET}  {Colors.ELECTRIC}★{Colors.RESET}")
                print(f"  {Colors.ELECTRIC}{'★' * 20}{Colors.RESET}")

            stats.print_stats(Colors)

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
