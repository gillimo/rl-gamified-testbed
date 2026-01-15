from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Tuple


def _clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, value))


def sample_gaussian(mean: float, stdev: float, bounds: Tuple[float, float]) -> float:
    if stdev <= 0:
        return _clamp(mean, bounds[0], bounds[1])
    value = random.gauss(mean, stdev)
    return _clamp(value, bounds[0], bounds[1])


@dataclass(frozen=True)
class TimingProfile:
    reaction_ms: Tuple[float, float, float, float] = (200, 60, 80, 500)
    dwell_ms: Tuple[float, float, float, float] = (80, 25, 20, 200)
    hover_dwell_ms: Tuple[float, float, float, float] = (120, 35, 40, 260)
    jitter_ms: Tuple[float, float, float, float] = (30, 10, 5, 80)
    click_down_up_ms: Tuple[float, float, float, float] = (90, 25, 30, 220)
    long_press_ms: Tuple[float, float, float, float] = (350, 80, 200, 800)
    settle_ms: Tuple[float, float, float, float] = (60, 20, 20, 140)
    think_pause_ms: Tuple[float, float, float, float] = (150, 50, 60, 400)
    handoff_ms: Tuple[float, float, float, float] = (120, 40, 40, 260)
    inter_action_ms: Tuple[float, float, float, float] = (180, 60, 60, 420)
    confirmation_ms: Tuple[float, float, float, float] = (140, 40, 50, 320)
    click_cadence_banking_ms: Tuple[float, float, float, float] = (110, 30, 40, 220)
    click_cadence_skilling_ms: Tuple[float, float, float, float] = (160, 45, 60, 320)
    double_click_gap_ms: Tuple[float, float, float, float] = (120, 35, 50, 260)
    click_pressure_click_ms: Tuple[float, float, float, float] = (90, 25, 30, 220)
    click_pressure_drag_ms: Tuple[float, float, float, float] = (160, 45, 60, 320)
    drag_start_hesitation_ms: Tuple[float, float, float, float] = (80, 25, 20, 200)


# Profile presets
TimingProfile.NORMAL = TimingProfile()
TimingProfile.FAST = TimingProfile(
    reaction_ms=(150, 40, 60, 350),
    dwell_ms=(60, 20, 15, 150),
    inter_action_ms=(120, 40, 40, 280),
)
TimingProfile.SLOW = TimingProfile(
    reaction_ms=(300, 80, 120, 700),
    dwell_ms=(120, 35, 40, 300),
    inter_action_ms=(280, 80, 100, 600),
)
TimingProfile.CAREFUL = TimingProfile(
    reaction_ms=(350, 100, 150, 800),
    dwell_ms=(150, 45, 50, 350),
    think_pause_ms=(250, 80, 100, 600),
    inter_action_ms=(350, 100, 120, 700),
)
TimingProfile.AGGRESSIVE = TimingProfile(
    reaction_ms=(120, 30, 50, 280),
    dwell_ms=(50, 15, 12, 120),
    inter_action_ms=(100, 30, 30, 220),
)
TimingProfile.CAUTIOUS = TimingProfile.CAREFUL  # Alias


def sample_reaction_ms(profile: TimingProfile) -> float:
    mean, stdev, min_val, max_val = profile.reaction_ms
    return sample_gaussian(mean, stdev, (min_val, max_val))


def sample_dwell_ms(profile: TimingProfile) -> float:
    mean, stdev, min_val, max_val = profile.dwell_ms
    return sample_gaussian(mean, stdev, (min_val, max_val))


def sample_hover_dwell_ms(profile: TimingProfile) -> float:
    mean, stdev, min_val, max_val = profile.hover_dwell_ms
    return sample_gaussian(mean, stdev, (min_val, max_val))


def sample_jitter_ms(profile: TimingProfile) -> float:
    mean, stdev, min_val, max_val = profile.jitter_ms
    return sample_gaussian(mean, stdev, (min_val, max_val))


def sample_click_down_up_ms(profile: TimingProfile) -> float:
    mean, stdev, min_val, max_val = profile.click_down_up_ms
    return sample_gaussian(mean, stdev, (min_val, max_val))


def sample_long_press_ms(profile: TimingProfile) -> float:
    mean, stdev, min_val, max_val = profile.long_press_ms
    return sample_gaussian(mean, stdev, (min_val, max_val))


def sample_settle_ms(profile: TimingProfile) -> float:
    mean, stdev, min_val, max_val = profile.settle_ms
    return sample_gaussian(mean, stdev, (min_val, max_val))


def sample_think_pause_ms(profile: TimingProfile) -> float:
    mean, stdev, min_val, max_val = profile.think_pause_ms
    return sample_gaussian(mean, stdev, (min_val, max_val))


def sample_handoff_ms(profile: TimingProfile) -> float:
    mean, stdev, min_val, max_val = profile.handoff_ms
    return sample_gaussian(mean, stdev, (min_val, max_val))


def sample_inter_action_ms(profile: TimingProfile, complexity: str = "normal") -> float:
    mean, stdev, min_val, max_val = profile.inter_action_ms
    base = sample_gaussian(mean, stdev, (min_val, max_val))
    if complexity == "complex":
        return base * 1.3
    if complexity == "simple":
        return base * 0.8
    return base


def sample_confirmation_ms(profile: TimingProfile) -> float:
    mean, stdev, min_val, max_val = profile.confirmation_ms
    return sample_gaussian(mean, stdev, (min_val, max_val))


def sample_reaction_ms_for_action(profile: TimingProfile, action_type: str) -> float:
    base = sample_reaction_ms(profile)
    if action_type in {"click", "drag"}:
        return base * 0.9
    if action_type in {"type", "camera"}:
        return base * 1.2
    return base


def sample_click_cadence_ms(profile: TimingProfile, context: str = "default") -> float:
    if context == "banking":
        mean, stdev, min_val, max_val = profile.click_cadence_banking_ms
    elif context == "skilling":
        mean, stdev, min_val, max_val = profile.click_cadence_skilling_ms
    else:
        mean, stdev, min_val, max_val = profile.dwell_ms
    return sample_gaussian(mean, stdev, (min_val, max_val))


def sample_double_click_gap_ms(profile: TimingProfile) -> float:
    mean, stdev, min_val, max_val = profile.double_click_gap_ms
    return sample_gaussian(mean, stdev, (min_val, max_val))


def sample_click_pressure_ms(profile: TimingProfile, action_type: str = "click") -> float:
    if action_type == "drag":
        mean, stdev, min_val, max_val = profile.click_pressure_drag_ms
    else:
        mean, stdev, min_val, max_val = profile.click_pressure_click_ms
    return sample_gaussian(mean, stdev, (min_val, max_val))


def sample_drag_start_hesitation_ms(profile: TimingProfile) -> float:
    mean, stdev, min_val, max_val = profile.drag_start_hesitation_ms
    return sample_gaussian(mean, stdev, (min_val, max_val))
