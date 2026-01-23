"""CLI rendering helpers for training UI."""
import sys
import re
import numpy as np


def print_heartbeat(cb) -> None:
    """Render the heartbeat box for the given callback instance."""
    step = cb.current_episode_length
    total = cb.max_episode_steps
    pct = int((step / total) * 100) if total > 0 else 0

    bar_filled = pct // 5
    bar = "#" * bar_filled + "-" * (20 - bar_filled)

    gain = cb.episode_total_gain
    loss = cb.episode_total_loss
    best = cb.episode_best_moment

    box_width = 50
    badges = cb.last_info.get("badges", 0)
    pokedex = cb.last_info.get("pokedex_owned", 0)
    lava_active = cb.last_info.get("lava_mode_active", False)
    lava_seconds_left = cb.last_info.get("lava_seconds_left", 0.0)

    if lava_active:
        lava_status = f"Lava: {cb.Colors.RED}ON{cb.Colors.CYAN}  Pen: -{cb.episode_lava_penalty:,.0f}"
    else:
        if lava_seconds_left <= 1:
            lava_color = cb.Colors.RED
        elif lava_seconds_left <= 5:
            lava_color = cb.Colors.FIRE
        elif lava_seconds_left <= 10:
            lava_color = cb.Colors.YELLOW
        else:
            lava_color = cb.Colors.GREEN
        lava_status = f"Lava: {lava_color}OFF{cb.Colors.CYAN}  {lava_color}{lava_seconds_left:>4.0f}s{cb.Colors.CYAN}"

    breakdown = cb.episode_best_moment_breakdown

    def _fmt_breakdown(label: str, value: float, zero_negative: bool = False) -> str:
        if value > 0:
            color = cb.Colors.GREEN
            sign = "+"
        elif value < 0:
            color = cb.Colors.RED
            sign = "-"
        else:
            color = cb.Colors.WHITE
            sign = "-" if zero_negative else "+"
        return f"{label}:{color}{sign}{abs(value):,.0f}{cb.Colors.CYAN}"

    breakdown_text = (
        f"{_fmt_breakdown('exp', breakdown.get('exploration', 0))} "
        f"{_fmt_breakdown('bat', breakdown.get('battle', 0))} "
        f"{_fmt_breakdown('prog', breakdown.get('progression', 0))} "
        f"{_fmt_breakdown('pen', breakdown.get('penalties', 0), True)} "
        f"{_fmt_breakdown('lava', breakdown.get('lava', 0), True)}"
    )

    xp_val = cb.current_episode_reward
    split_color = cb.Colors.WHITE
    if total > 0 and step > 0 and cb.episode_rewards:
        recent = cb.episode_rewards[-10:]
        avg_recent = float(np.mean(recent))
        best_recent = max(recent)
        best_ever = cb.trainer_stats.best_episode_reward
        avg_pace = avg_recent * (step / total) if avg_recent else 0.0
        best_recent_pace = best_recent * (step / total) if best_recent else 0.0
        best_ever_pace = best_ever * (step / total) if best_ever else 0.0
        if best_ever_pace and xp_val >= best_ever_pace:
            xp_color = cb.Colors.ELECTRIC
            xp_suffix = " *"
            split_color = cb.Colors.ELECTRIC
        elif best_recent_pace and xp_val >= best_recent_pace:
            xp_color = cb.Colors.PURPLE
            xp_suffix = ""
            split_color = cb.Colors.PURPLE
        elif avg_pace and xp_val >= avg_pace:
            xp_color = cb.Colors.GREEN
            xp_suffix = ""
            split_color = cb.Colors.GREEN
        else:
            xp_color = cb.Colors.RED
            xp_suffix = ""
            split_color = cb.Colors.RED
    else:
        xp_color = cb.Colors.WHITE
        xp_suffix = ""
    breakdown_text = f"{split_color}{breakdown_text}{cb.Colors.CYAN}"

    next_level_points = cb._next_level_points(cb.episode_current_level)
    ansi_re = re.compile(r"\x1b\[[0-9;]*m")

    def _visible_len(value: str) -> int:
        return len(ansi_re.sub("", value))

    def _box_line(content: str) -> str:
        line = f"  |  {content}"
        pad = (box_width + 3) - _visible_len(line)
        if pad < 0:
            pad = 0
        return f"{line}{' ' * pad}|"

    xp_value = f"{xp_val:>10,.0f}{xp_suffix}"
    xp_line = _box_line(f"Episode XP: {xp_value}")
    xp_line = xp_line.replace(xp_value, f"{xp_color}{xp_value}{cb.Colors.CYAN}", 1)

    entropy_val = cb.last_entropy if cb.last_entropy is not None else np.log(cb.NUM_ACTIONS)
    if cb.current_episode_length > 0:
        recent_rewards = (cb.episode_rewards[-9:] if len(cb.episode_rewards) >= 9 else list(cb.episode_rewards))
        recent_rewards = recent_rewards + [cb.current_episode_reward]
    else:
        recent_rewards = cb.episode_rewards[-10:]
    avg_recent = float(np.mean(recent_rewards)) if recent_rewards else 0.0
    if cb.avg_reward_ema is None:
        cb.avg_reward_ema = avg_recent
    else:
        alpha = 0.02
        cb.avg_reward_ema = (alpha * avg_recent) + ((1 - alpha) * cb.avg_reward_ema)
    if cb.prev_avg_reward_ema is None:
        cb.prev_avg_reward_ema = cb.avg_reward_ema
    avg_delta_raw = avg_recent - (cb.prev_avg10_heartbeat if cb.prev_avg10_heartbeat is not None else avg_recent)
    if abs(avg_delta_raw) > 0.0001:
        cb.last_avg_delta = avg_delta_raw
        avg_delta = avg_delta_raw
    else:
        avg_delta = cb.last_avg_delta
    avg_sign = "+" if avg_delta >= 0 else ""
    avg_color = cb.Colors.GREEN if avg_delta > 0 else cb.Colors.RED if avg_delta < 0 else cb.Colors.WHITE
    avg_line = _box_line(f"Avg Reward: {avg_recent:>10,.0f} ({avg_sign}{avg_delta:>7,.1f})")
    avg_line = avg_line.replace(f"{avg_sign}{avg_delta:>7,.1f}", f"{avg_color}{avg_sign}{avg_delta:>7,.1f}{cb.Colors.CYAN}", 1)

    progress_index = cb.policy_index
    progress_sign = cb.policy_index_sign
    if progress_sign > 0:
        trend_label = f"{cb.Colors.GREEN}IMPROVING{cb.Colors.CYAN}"
        streak_color = cb.Colors.ELECTRIC if cb.progress_streak >= 200 else cb.Colors.GREEN
    elif progress_sign < 0:
        trend_label = f"{cb.Colors.RED}DAMAGING{cb.Colors.CYAN}"
        streak_color = cb.Colors.FIRE if cb.progress_streak >= 50 else cb.Colors.RED
    else:
        trend_label = f"{cb.Colors.WHITE}STABLE{cb.Colors.CYAN}"
        streak_color = cb.Colors.WHITE

    pi_sign = "+" if progress_index >= 0 else ""
    pi_color = cb.Colors.GREEN if progress_index > 0 else cb.Colors.RED if progress_index < 0 else cb.Colors.WHITE
    pi_text = f"{pi_sign}{progress_index:>6.2f}"
    streak_text = f"{cb.progress_streak:>3}"
    pi_line = _box_line(f"Model Index: {pi_text} ({streak_text})")
    pi_line = pi_line.replace(pi_text, f"{pi_color}{pi_text}{cb.Colors.CYAN}", 1)
    pi_line = pi_line.replace(streak_text, f"{streak_color}{streak_text}{cb.Colors.CYAN}", 1)

    trend_line = _box_line(f"Training Trend: {trend_label}")
    total_index = cb.index_green_count + cb.index_red_count
    ratio = (cb.index_green_count / total_index) if total_index > 0 else 0.0
    ratio_text = f"{cb.index_green_count}:{cb.index_red_count} ({ratio:.2f}x)"
    ratio_line = _box_line(f"Index Ratio: {ratio_text}")
    ratio_line = ratio_line.replace(ratio_text, f"{cb.Colors.WHITE}{ratio_text}{cb.Colors.CYAN}", 1)
    mag_text = f"{cb.index_green_mag + cb.index_red_mag:.1f}"
    mag_line = _box_line(f"Index Magnitude: {mag_text}")
    mag_line = mag_line.replace(mag_text, f"{cb.Colors.WHITE}{mag_text}{cb.Colors.CYAN}", 1)

    gold = cb.split_history.count("gold")
    purple = cb.split_history.count("purple")
    green = cb.split_history.count("green")
    red = cb.split_history.count("red")
    splits_text = f"Splits G:{gold} P:{purple} Gr:{green} R:{red}"
    splits_line = _box_line(splits_text)
    splits_line = splits_line.replace(f"G:{gold}", f"G:{cb.Colors.ELECTRIC}{gold}{cb.Colors.CYAN}", 1)
    splits_line = splits_line.replace(f"P:{purple}", f"P:{cb.Colors.PURPLE}{purple}{cb.Colors.CYAN}", 1)
    splits_line = splits_line.replace(f"Gr:{green}", f"Gr:{cb.Colors.GREEN}{green}{cb.Colors.CYAN}", 1)
    splits_line = splits_line.replace(f"R:{red}", f"R:{cb.Colors.RED}{red}{cb.Colors.CYAN}", 1)

    lines = [
        f"  +{'-' * box_width}+",
        xp_line,
        _box_line(f"Gilly Lv: {cb.episode_current_level} (Ep {len(cb.episode_rewards)})"),
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
        _box_line(lava_status),
        _box_line(f"Points Gained:   {'+' if gain >= 0 else ''}{gain:,.0f}"),
        _box_line(f"Points Lost:     {loss:,.0f}"),
        _box_line(f"Best Moment:     {'+' if best >= 0 else ''}{best:,.0f}"),
        _box_line(f" {breakdown_text}"),
        f"  +{'-' * box_width}+",
    ]

    if cb.heartbeat_printed:
        clear_lines = len(lines) + 6
        sys.stdout.write(f"\033[{clear_lines}A")
        for _ in range(clear_lines):
            sys.stdout.write("\033[2K\r\n")
        sys.stdout.write(f"\033[{clear_lines}A")

    for line in lines:
        sys.stdout.write(f"\033[2K\r{cb.Colors.CYAN}{line}{cb.Colors.RESET}\n")

    cb.last_heartbeat_lines = len(lines)
    cb.prev_avg_reward_ema = cb.avg_reward_ema
    cb.prev_avg10_heartbeat = avg_recent
    cb.heartbeat_printed = True
    sys.stdout.flush()


def print_episode_box(cb, info: dict) -> None:
    """Render the episode completion box for the given callback instance."""
    if cb.heartbeat_printed and cb.last_heartbeat_lines > 0:
        clear_lines = cb.last_heartbeat_lines + 6
        sys.stdout.write(f"\033[{clear_lines}A")
        for _ in range(clear_lines):
            sys.stdout.write("\033[2K\r\n")
        sys.stdout.write(f"\033[{clear_lines}A")
        cb.heartbeat_printed = False

    print()

    ep = len(cb.episode_rewards)
    r = cb.episode_rewards[-1]
    avg10 = np.mean(cb.episode_rewards[-10:]) if cb.episode_rewards else 0
    avg_all = np.mean(cb.episode_rewards) if cb.episode_rewards else 0
    r_delta = r - cb.prev_episode_reward
    avg10_delta = avg10 - cb.prev_avg10
    avg_all_delta = avg_all - cb.prev_avg_all
    lv = cb.episode_current_level

    badges = info.get("badges", 0)
    pokedex = info.get("pokedex_owned", 0)
    best = cb.trainer_stats.best_episode_reward
    total_xp = cb.trainer_stats.total_xp

    entropy_value = cb.logger.name_to_value.get("train/entropy", None) if cb.logger else None
    entropy_loss = cb.logger.name_to_value.get("train/entropy_loss", None) if cb.logger else None
    max_entropy = np.log(cb.NUM_ACTIONS)
    if entropy_value not in (None, 0):
        actual_entropy = min(abs(entropy_value), max_entropy)
    elif entropy_loss not in (None, 0):
        ent_coef = getattr(cb.model, "ent_coef", 0.01) if cb.model else 0.01
        actual_entropy = abs(entropy_loss) / ent_coef if ent_coef > 0 else max_entropy
        actual_entropy = min(actual_entropy, max_entropy)
    else:
        actual_entropy = max_entropy
    cb.last_entropy = actual_entropy
    confidence = cb._entropy_to_confidence(actual_entropy)

    print(f"\n  {cb.Colors.PURPLE}+{'-'*62}+{cb.Colors.RESET}")
    print(f"  {cb.Colors.PURPLE}|{cb.Colors.RESET}  EPISODE {ep} COMPLETE                               {cb.Colors.PURPLE}|{cb.Colors.RESET}")
    print(f"  {cb.Colors.PURPLE}+{'-'*62}+{cb.Colors.RESET}")
    print(f"  {cb.Colors.PURPLE}|{cb.Colors.RESET}  REWARD: {cb.Colors.ELECTRIC}{r:>10,.0f}{cb.Colors.RESET} {cb.Colors.DIM}({r_delta:+.0f}){cb.Colors.RESET}  |  10-EP AVG: {cb.Colors.WHITE}{avg10:>10,.0f}{cb.Colors.RESET} {cb.Colors.DIM}({avg10_delta:+.0f}){cb.Colors.RESET}   {cb.Colors.PURPLE}|{cb.Colors.RESET}")
    print(f"  {cb.Colors.PURPLE}|{cb.Colors.RESET}  LIFETIME AVG: {cb.Colors.WHITE}{avg_all:>10,.0f}{cb.Colors.RESET} {cb.Colors.DIM}({avg_all_delta:+.0f}){cb.Colors.RESET}                          {cb.Colors.PURPLE}|{cb.Colors.RESET}")
    print(f"  {cb.Colors.PURPLE}+{'-'*62}+{cb.Colors.RESET}")
    print(f"  {cb.Colors.PURPLE}|{cb.Colors.RESET}  CHARACTER STATS:                                        {cb.Colors.PURPLE}|{cb.Colors.RESET}")
    print(f"  {cb.Colors.PURPLE}|{cb.Colors.RESET}    Gilly Lv: {cb.Colors.YELLOW}{lv}{cb.Colors.RESET}                                          {cb.Colors.PURPLE}|{cb.Colors.RESET}")
    print(f"  {cb.Colors.PURPLE}|{cb.Colors.RESET}    Badges: {cb.Colors.YELLOW}{badges}/8{cb.Colors.RESET}         Pokedex: {cb.Colors.RED}{pokedex}/151{cb.Colors.RESET}                   {cb.Colors.PURPLE}|{cb.Colors.RESET}")
    print(f"  {cb.Colors.PURPLE}|{cb.Colors.RESET}    Best Score: {cb.Colors.GREEN}{int(best):,}{cb.Colors.RESET}   Total XP: {cb.Colors.WHITE}{int(total_xp):,}{cb.Colors.RESET}                  {cb.Colors.PURPLE}|{cb.Colors.RESET}")
    print(f"  {cb.Colors.PURPLE}+{'-'*62}+{cb.Colors.RESET}")
    print(f"  {cb.Colors.PURPLE}|{cb.Colors.RESET}  LEARNING STATUS:                                        {cb.Colors.PURPLE}|{cb.Colors.RESET}")

    conf_color = cb.Colors.GREEN if confidence > 60 else (cb.Colors.YELLOW if confidence > 30 else cb.Colors.RED)
    conf_diff = confidence - cb.prev_confidence
    trend = ""
    if abs(conf_diff) > 1:
        if conf_diff > 0:
            trend = f" {cb.Colors.GREEN}(UP){cb.Colors.RESET}"
        else:
            trend = f" {cb.Colors.RED}(DOWN){cb.Colors.RESET}"
    print(f"  {cb.Colors.PURPLE}|{cb.Colors.RESET}    Confidence: {conf_color}{confidence:.5f}%{cb.Colors.RESET}{trend}                              {cb.Colors.PURPLE}|{cb.Colors.RESET}")
    print(f"  {cb.Colors.PURPLE}|{cb.Colors.RESET}    {cb.Colors.DIM}(0% = random guessing, 100% = fully confident){cb.Colors.RESET}            {cb.Colors.PURPLE}|{cb.Colors.RESET}")
    print(f"  {cb.Colors.PURPLE}+{'-'*62}+{cb.Colors.RESET}\n")

    cb._record_episode_split(r)
    cb.prev_episode_reward = r
    cb.prev_avg10 = avg10
    cb.prev_avg_all = avg_all

    if cb.episode_return_ema is None:
        cb.episode_return_ema = r
    else:
        alpha = 0.1
        cb.episode_return_ema = (alpha * r) + ((1 - alpha) * cb.episode_return_ema)
    if cb.prev_episode_return_ema is None:
        cb.prev_episode_return_ema = cb.episode_return_ema
    ema_delta = cb.episode_return_ema - cb.prev_episode_return_ema
    progress_index_raw = (ema_delta / max(abs(cb.prev_episode_return_ema), 1.0)) * 100.0
    if abs(progress_index_raw) > 0.01:
        cb.last_progress_index = progress_index_raw
    cb.policy_index = cb.last_progress_index
    cb.policy_index_sign = 1 if cb.policy_index > 0.01 else -1 if cb.policy_index < -0.01 else 0
    if cb.policy_index_sign == 0:
        pass
    elif cb.policy_index_sign != cb.progress_streak_sign:
        cb.progress_streak_sign = cb.policy_index_sign
        cb.progress_streak = 1
    else:
        cb.progress_streak += 1
    if cb.policy_index_sign > 0:
        cb.index_green_count += 1
        cb.index_green_mag += abs(cb.policy_index)
    elif cb.policy_index_sign < 0:
        cb.index_red_count += 1
        cb.index_red_mag += abs(cb.policy_index)
    cb.prev_episode_return_ema = cb.episode_return_ema
