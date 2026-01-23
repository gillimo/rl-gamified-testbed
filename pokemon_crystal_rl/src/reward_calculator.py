"""Reward Calculator - Pokemon Crystal RL with Floor is Lava, Battle Rewards, HM Detection"""
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, Set, Tuple, Optional

from src.gravity_map import GravityMap

# ANSI color codes for console output
class C:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    FIRE = '\033[38;5;208m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

# Known Pokemon Center locations: (map_id, x, y)
POKEMON_CENTERS = [
    (41, 7, 4),   # Viridian City
    (58, 7, 4),   # Pewter City
    (64, 7, 4),   # Cerulean City
    (68, 7, 4),   # Lavender Town
    (89, 7, 4),   # Vermilion City
    (133, 7, 4),  # Celadon City
    (154, 7, 4),  # Fuchsia City
    (166, 7, 4),  # Saffron City
    (174, 7, 4),  # Cinnabar Island
    (178, 7, 4),  # Indigo Plateau
]

# HM tile detection - Tile IDs for cuttable trees and strength boulders
# These may vary by tileset, so we track (tileset, tile_id) pairs
CUT_TREE_TILES = {
    (0, 0x3D),   # Overworld tileset
    (0, 0x50),   # Alternate
    (7, 0x3D),   # Gym tileset (if applicable)
}
STRENGTH_BOULDER_TILES = {
    (0, 0x34),   # Overworld boulder
    # Add more as discovered
}

# HM move IDs in Pokemon Crystal
HM_MOVES = {
    "cut": 15,       # HM01 Cut
    "fly": 19,       # HM02 Fly
    "surf": 57,      # HM03 Surf
    "strength": 70,  # HM04 Strength
    "flash": 148,    # HM05 Flash
}

# Weights file path (relative to this module)
WEIGHTS_PATH = Path(__file__).parent.parent / "weights.json"
REWARD_LOG_PATH = Path(__file__).parent.parent / "logs" / "reward_trace.jsonl"
WALK_AUDIT_PATH = Path(__file__).parent.parent / "logs" / "walk_audit.jsonl"


def load_weights() -> Dict:
    """Load weights from JSON file."""
    default_weights = {
        "exploration": {"new_tile": 3.5, "new_tile_distance_bonus_max": 0.5, "new_building": 10.0},
        "battle": {"move_selection": 5.0, "damage_dealt_per_hp": 0.5, "damage_dealt_knockout_bonus": 25.0},
        "leveling": {"level_up_early": 1500.0, "level_up_mid": 1000.0, "level_up_late": 750.0, "pikachu_bonus": 50.0},
        "healing": {"near_death_save": 50.0, "medium_save": 30.0, "normal_heal": 10.0},
        "progression": {"badge": 50000.0, "pokedex_catch": 15000.0},
        "economy": {"money_earned_multiplier": 0.1, "broke_penalty": 20.0},
        "penalties": {"pokemon_fainted": 50.0, "save_menu": 100.0, "option_menu": 100.0, "exit_menu": 100.0,
                      "character_menu": 5.0, "stuck_100_frames": 10.0, "stuck_500_frames": 50.0, "stuck_1000_frames": 200.0},
        "lava_mode": {"trigger_seconds": 30, "base_revisit_penalty": 1.0, "penalty_multiplier": 1.5},
        "noise_curriculum": {"enabled": True, "full_noise_level": 6, "min_scale": 0.2},
        "hm_detection": {"near_cut_tree": 10.0, "near_strength_boulder": 10.0},
    }
    try:
        if WEIGHTS_PATH.exists():
            with open(WEIGHTS_PATH) as f:
                return json.load(f)
    except Exception as e:
        print(f"  [WARN] Failed to load weights.json: {e}, using defaults")
    return default_weights


class RewardCalculator:
    def __init__(self):
        # Load weights from config
        self.weights = load_weights()
        self.weights_mtime = WEIGHTS_PATH.stat().st_mtime if WEIGHTS_PATH.exists() else 0
        self.gravity_map = GravityMap()
        self.first_grass_reached = False
        self.left_start_map = False

        # Exploration tracking
        self.visited_tiles: Set[Tuple[object, int, int]] = set()  # (map_key, x, y)
        self.visited_buildings: Set[int] = set()  # map IDs

        # Dialogue tracking
        self.dialogue_active_prev = False

        # Pokemon tracking
        self.max_pokedex_owned = None  # None = not initialized yet

        # Progression tracking
        self.max_party_levels = [0] * 6
        self.max_badges = None  # None = not initialized yet
        self.max_money = 0
        self.initialized = False

        # HM usage tracking (anti-spam)
        self.last_hm_tile: Optional[Tuple[int, int, int, int]] = None  # (map, x, y, tile_ahead)

        # Walk audit tracking
        self.step_index = 0

        # === HM HOT/COLD TRACKING ===
        # Track active HM targets for "hot/cold" pursuit game
        # Structure: {target_key: {"map": m, "target_x": x, "target_y": y, "hm_type": type, "reward": r, "last_dist": d, "claimed_tiles": set()}}
        self.hm_targets: Dict[str, Dict] = {}
        self.hm_abandon_distance = 20  # Tiles away to consider target abandoned

        # Stuck detection
        self.stuck_position: Optional[Tuple[int, int, int]] = None
        self.stuck_frames = 0

        # === FLOOR IS LAVA MODE ===
        self.last_positive_reward_time = time.time()
        self.lava_mode_active = False
        self.lava_tile_visits: Dict[Tuple[int, int, int], int] = {}  # (map, x, y) -> visit count
        self.last_gravity_metrics: Optional[Dict] = None

        # === BATTLE TRACKING ===
        self.prev_enemy_hp = 0
        self.prev_player_move = 0
        self.prev_in_battle = 0

        # === BATTLE HEALING HOT/COLD ===
        # Track lowest HP reached during battle for each party slot
        # The lower it gets, the "hotter" - more reward for healing
        self.battle_lowest_hp: Dict[int, float] = {}  # slot -> lowest HP ratio seen
        # Track status conditions - reward curing them
        self.battle_status_turns: Dict[int, int] = {}  # slot -> turns with status condition

    def reload_weights(self):
        """Reload weights from JSON if file changed."""
        try:
            if WEIGHTS_PATH.exists():
                current_mtime = WEIGHTS_PATH.stat().st_mtime
                if current_mtime > self.weights_mtime:
                    self.weights = load_weights()
                    self.weights_mtime = current_mtime
                    print(f"  {C.CYAN}[WEIGHTS]{C.RESET} Reloaded weights.json")
        except Exception:
            pass  # Silently ignore reload errors

    def initialize_from_state(self, state: Dict):
        """Initialize baseline values from first VALID state read."""
        if self.initialized:
            return

        badges = state.get('badges', 0)
        pokedex = state.get('pokedex_owned', 0)

        self.max_badges = badges
        self.max_pokedex_owned = pokedex

        map_key = self._map_key(state)
        self.visited_buildings.add(map_key)
        curr_map, curr_x, curr_y = self._sanitize_position(state)
        curr_pos = (map_key, curr_x, curr_y)
        self.visited_tiles.add(curr_pos)
        self.initialized = True
        self.last_positive_reward_time = time.time()
        print(f"  {C.CYAN}[INIT]{C.RESET} Baseline: {C.YELLOW}{self.max_badges} badges{C.RESET}, {C.RED}{self.max_pokedex_owned} pokedex{C.RESET}")

    def _distance_to_nearest_center(self, map_id: int, x: int, y: int) -> float:
        """Calculate distance to nearest known Pokemon Center."""
        min_dist = float('inf')
        for center_map, cx, cy in POKEMON_CENTERS:
            if center_map == map_id:
                dist = abs(x - cx) + abs(y - cy)
            else:
                dist = abs(map_id - center_map) * 10 + abs(x - cx) + abs(y - cy)
            min_dist = min(min_dist, dist)
        return min_dist if min_dist != float('inf') else 50.0

    def _map_key(self, state: Dict):
        """Use stable map identifiers when available to avoid map-id jitter."""
        map_group = state.get("map_group")
        map_number = state.get("map_number")
        if isinstance(map_group, int) and isinstance(map_number, int):
            return (map_group, map_number)
        return int(state.get("map", 0))

    def _sanitize_position(self, state: Dict) -> Tuple[int, int, int]:
        """Clamp position to map bounds when available to avoid runaway rewards."""
        map_id = int(state.get("map", 0))
        x = int(state.get("x", 0))
        y = int(state.get("y", 0))
        width = state.get("map_width")
        height = state.get("map_height")
        if isinstance(width, int) and isinstance(height, int) and 0 < width <= 100 and 0 < height <= 100:
            x = max(0, min(x, width - 1))
            y = max(0, min(y, height - 1))
        return map_id, x, y

    def _is_garbage_state(self, state: Dict) -> bool:
        """Check if state looks like garbage memory."""
        badges = state.get('badges', 0)
        pokedex = state.get('pokedex_owned', 0)
        party_count = state.get('party_count', 0)
        map_group = state.get('map_group')
        map_number = state.get('map_number')
        map_id = state.get('map', 0)
        x = state.get('x', 0)
        y = state.get('y', 0)
        width = state.get('map_width')
        height = state.get('map_height')

        if party_count < 0 or party_count > 6:
            return True
        if badges > 8 or pokedex > 151:
            return True
        if party_count > 0 and pokedex > party_count + 10:
            return True
        # Map identifiers should not drop to zero in a valid room.
        if isinstance(map_group, int) and isinstance(map_number, int):
            if map_group == 0 and map_number == 0:
                return True
        elif map_id == 0:
            return True
        # Coordinates should stay within the reported map bounds.
        if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
            if x < 0 or y < 0 or x >= width or y >= height:
                return True
        return False

    def _party_has_move(self, state: Dict, move_id: int) -> bool:
        """Check if any Pokemon in the party knows a specific move."""
        party = state.get('party', [])
        party_count = state.get('party_count', 0)

        for i in range(min(6, party_count)):
            mon = party[i] if i < len(party) else None
            if mon:
                # Check all 4 move slots
                if mon.get('move_1') == move_id:
                    return True
                if mon.get('move_2') == move_id:
                    return True
                if mon.get('move_3') == move_id:
                    return True
                if mon.get('move_4') == move_id:
                    return True
        return False

    def calculate_reward(self, prev_state: Dict, curr_state: Dict, return_breakdown: bool = False, episode_level: Optional[int] = None, action: Optional[int] = None):
        """Calculate reward from state transition.

        Args:
            prev_state: Previous game state
            curr_state: Current game state
            return_breakdown: If True, returns (total_reward, breakdown_dict)

        Returns:
            float: Total reward (if return_breakdown=False)
            tuple: (total_reward, breakdown_dict) (if return_breakdown=True)
        """
        # Check for weights update
        self.reload_weights()

        # Step audit counter
        self.step_index += 1

        # Initialize breakdown dict for PPO decomposed rewards
        breakdown = {
            'exploration': 0.0,
            'battle': 0.0,
            'progression': 0.0,
            'penalties': 0.0,
            'lava': 0.0,
        }

        # Skip if either state looks like garbage memory
        if self._is_garbage_state(prev_state) or self._is_garbage_state(curr_state):
            try:
                WALK_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
                payload = {
                    "step": self.step_index,
                    "reward_total": 0.0,
                    "new_tile_awarded": False,
                    "new_tile_value": 0.0,
                    "reason": "garbage_state",
                    "map_group": curr_state.get("map_group"),
                    "map_number": curr_state.get("map_number"),
                    "map": curr_state.get("map"),
                    "x": curr_state.get("x"),
                    "y": curr_state.get("y"),
                    "width": curr_state.get("map_width"),
                    "height": curr_state.get("map_height"),
                }
                with open(WALK_AUDIT_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps(payload, ensure_ascii=True) + "\n")
            except Exception:
                pass
            if return_breakdown:
                return 0.0, breakdown
            return 0.0

        # Initialize baseline from first state
        if not self.initialized:
            self.initialize_from_state(prev_state)
            if not self.initialized:
                if return_breakdown:
                    return 0.0, breakdown
                return 0.0

        # Gravity is permanently disabled for this training run.
        gravity_enabled = False
        if gravity_enabled and self.gravity_map.config.get("enabled", False):
            self.gravity_map.update(prev_state, curr_state, action=action)
            gravity_reward = self.gravity_map.compute_reward(prev_state, curr_state)

            prev_map = prev_state.get("map", 0)
            curr_map = curr_state.get("map", 0)
            prev_x = prev_state.get("x", 0)
            prev_y = prev_state.get("y", 0)
            curr_x = curr_state.get("x", 0)
            curr_y = curr_state.get("y", 0)
            prev_value = self.gravity_map.compute_position_value(prev_map, prev_x, prev_y)
            curr_value = self.gravity_map.compute_position_value(curr_map, curr_x, curr_y)
            self.last_gravity_metrics = {
                "prev_value": prev_value,
                "curr_value": curr_value,
                "reward": gravity_reward,
                "door_count": len(self.gravity_map.doors_per_map.get(curr_map, [])),
                "poi_count": len(self.gravity_map.pois_per_map.get(curr_map, {})),
            }
            self.lava_mode_active = self.gravity_map.lava_mode_active
            self.last_positive_reward_time = self.gravity_map.last_positive_time
            breakdown['exploration'] += gravity_reward

        w = self.weights
        noise_cfg = w.get("noise_curriculum", {})
        if noise_cfg.get("enabled", True) and episode_level is not None:
            full_level = max(1, int(noise_cfg.get("full_noise_level", 6)))
            min_scale = float(noise_cfg.get("min_scale", 0.2))
            noise_scale = max(min_scale, min(1.0, float(episode_level) / float(full_level)))
        else:
            noise_scale = 1.0
        reward = 0.0

        # === FLOOR IS LAVA MODE CHECK ===
        lava_cfg = w.get('lava_mode', {})
        trigger_seconds = lava_cfg.get('trigger_seconds', 30)

        # Lava mode permanently disabled.
        self.lava_mode_active = False

        curr_map, curr_x, curr_y = self._sanitize_position(curr_state)
        curr_pos = (self._map_key(curr_state), curr_x, curr_y)

        # === EXPLORATION ===
        exp_cfg = w.get('exploration', {})
        new_tile_awarded = False
        new_tile_value = 0.0
        if curr_pos not in self.visited_tiles:
            base_reward = exp_cfg.get('new_tile', 3.5)
            distance = self._distance_to_nearest_center(curr_map, curr_x, curr_y)
            distance_bonus = min(distance * 0.01, exp_cfg.get('new_tile_distance_bonus_max', 0.5))
            exp_reward = base_reward + distance_bonus
            reward += exp_reward
            breakdown['exploration'] += exp_reward
            self.visited_tiles.add(curr_pos)
            new_tile_awarded = True
            new_tile_value = exp_reward

        if self._map_key(curr_state) not in self.visited_buildings:
            building_reward = exp_cfg.get('new_building', 10.0)
            reward += building_reward
            breakdown['exploration'] += building_reward
            self.visited_buildings.add(self._map_key(curr_state))

        # === FLOOR IS LAVA PENALTY (when in lava mode) ===
        if self.lava_mode_active:
            # Track visit count for this tile
            if curr_pos in self.lava_tile_visits:
                self.lava_tile_visits[curr_pos] += 1
            else:
                self.lava_tile_visits[curr_pos] = 1

            visit_count = self.lava_tile_visits[curr_pos]
            if visit_count > 1:
                # Escalating penalty: base * multiplier^(visits-1)
                base_penalty = lava_cfg.get('base_revisit_penalty', 1.0)
                multiplier = lava_cfg.get('penalty_multiplier', 1.5)
                penalty = base_penalty * (multiplier ** (visit_count - 1))
                penalty *= noise_scale
                reward -= penalty
                breakdown['lava'] -= penalty

        # === MENU / DIALOGUE MANAGEMENT ===
        penalties_cfg = w.get('penalties', {})
        menu_item = curr_state.get('menu_item', 0)
        dialogue_active = curr_state.get('text_box_id', 0) > 0

        # Disable penalties until level 10 for clear early signal.
        penalties_enabled = episode_level is None or episode_level >= 10
        if penalties_enabled and dialogue_active:
            menu_penalty = 0.0
            if menu_item == 4:  # Save
                menu_penalty = penalties_cfg.get('save_menu', 100.0)
            elif menu_item == 5:  # Option
                menu_penalty = penalties_cfg.get('option_menu', 100.0)
            elif menu_item == 6:  # Exit
                menu_penalty = penalties_cfg.get('exit_menu', 100.0)
            elif menu_item == 3:  # Character
                menu_penalty = penalties_cfg.get('character_menu', 5.0)
            if menu_penalty > 0:
                menu_penalty *= noise_scale
                reward -= menu_penalty
                breakdown['penalties'] -= menu_penalty

        self.dialogue_active_prev = dialogue_active

        # === BATTLE REWARDS ===
        battle_cfg = w.get('battle', {})
        in_battle = curr_state.get('in_battle', 0)
        enemy_hp = curr_state.get('enemy_hp', 0)
        player_move = curr_state.get('player_move', 0)

        if in_battle > 0:
            # Reward for selecting a move (move changed = selected a new move)
            if player_move != self.prev_player_move and player_move > 0:
                move_reward = battle_cfg.get('move_selection', 5.0)
                reward += move_reward
                breakdown['battle'] += move_reward

            # Reward for damage dealt
            if self.prev_enemy_hp > 0 and enemy_hp < self.prev_enemy_hp:
                damage = self.prev_enemy_hp - enemy_hp
                damage_reward = damage * battle_cfg.get('damage_dealt_per_hp', 0.5)
                reward += damage_reward
                breakdown['battle'] += damage_reward

                # Bonus for knockout
                if enemy_hp == 0:
                    ko_reward = battle_cfg.get('damage_dealt_knockout_bonus', 25.0)
                    reward += ko_reward
                    breakdown['battle'] += ko_reward

            self.prev_enemy_hp = enemy_hp
            self.prev_player_move = player_move

            # === BATTLE HEALING HOT/COLD ===
            # Track HP drops and reward healing proportionally
            party = curr_state.get('party', [])
            prev_party = prev_state.get('party', [])
            for slot in range(min(6, curr_state.get('party_count', 0))):
                curr_mon = party[slot] if slot < len(party) else None
                prev_mon = prev_party[slot] if slot < len(prev_party) else None
                if not curr_mon or not prev_mon:
                    continue

                max_hp = max(curr_mon.get('max_hp', 1), 1)
                curr_hp_ratio = curr_mon.get('hp', 0) / max_hp
                prev_hp_ratio = prev_mon.get('hp', 0) / max_hp

                # Track lowest HP ratio (getting "hotter")
                if slot not in self.battle_lowest_hp:
                    self.battle_lowest_hp[slot] = curr_hp_ratio
                if curr_hp_ratio < self.battle_lowest_hp[slot]:
                    self.battle_lowest_hp[slot] = curr_hp_ratio
                    if curr_hp_ratio < 0.5:
                        print(f"  {C.FIRE}[HOT/COLD]{C.RESET} Pokemon {slot+1} HP dropping! {C.RED}({int(curr_hp_ratio*100)}%){C.RESET} - Healing reward {C.FIRE}increasing!{C.RESET}")

                # Reward healing based on how "hot" it was (how low HP got)
                if curr_hp_ratio > prev_hp_ratio:  # Healed!
                    lowest = self.battle_lowest_hp.get(slot, 1.0)
                    # Scale: lower HP = higher multiplier (1.0 at full, up to 5.0 at near-death)
                    heat_multiplier = max(1.0, 5.0 - (lowest * 4.0))
                    heal_amount = curr_hp_ratio - prev_hp_ratio
                    heal_reward = heal_amount * 100 * heat_multiplier
                    reward += heal_reward
                    breakdown['battle'] += heal_reward
                    print(f"  {C.GREEN}[HEALED]{C.RESET} Pokemon {slot+1} healed! Heat: {C.FIRE}{heat_multiplier:.1f}x{C.RESET}, Reward: {C.GREEN}+{heal_reward:.1f}{C.RESET}")
                    # Reset lowest HP tracking after healing
                    self.battle_lowest_hp[slot] = curr_hp_ratio

                # === STATUS CONDITION HOT/COLD ===
                # Track turns with status, reward curing
                curr_status = curr_mon.get('status', 0)
                prev_status = prev_mon.get('status', 0)

                if prev_status > 0:
                    # Had a status condition - track turns
                    if slot not in self.battle_status_turns:
                        self.battle_status_turns[slot] = 0
                    self.battle_status_turns[slot] += 1

                    if curr_status == 0:
                        # Status cured! Reward based on how long they suffered
                        turns_suffered = self.battle_status_turns.get(slot, 1)
                        status_cure_reward = 10.0 + (turns_suffered * 5.0)  # Base + per-turn bonus
                        reward += status_cure_reward
                        breakdown['battle'] += status_cure_reward
                        status_names = {1: "Sleep", 2: "Poison", 4: "Burn", 8: "Freeze", 16: "Paralysis"}
                        status_name = status_names.get(prev_status, f"Status {prev_status}")
                        print(f"  {C.GREEN}[CURED]{C.RESET} Pokemon {slot+1} cured of {C.YELLOW}{status_name}{C.RESET}! Suffered {turns_suffered} turns, Reward: {C.GREEN}+{status_cure_reward:.1f}{C.RESET}")
                        del self.battle_status_turns[slot]
                elif curr_status > 0 and prev_status == 0:
                    # Just got afflicted
                    self.battle_status_turns[slot] = 0
                    status_names = {1: "Sleep", 2: "Poison", 4: "Burn", 8: "Freeze", 16: "Paralysis"}
                    status_name = status_names.get(curr_status, f"Status {curr_status}")
                    print(f"  {C.YELLOW}[STATUS]{C.RESET} Pokemon {slot+1} afflicted with {C.RED}{status_name}{C.RESET}! Cure reward building...")

        else:
            # Reset battle tracking when not in battle
            if self.prev_in_battle > 0:
                self.prev_enemy_hp = 0
                self.prev_player_move = 0
                self.battle_lowest_hp.clear()  # Reset hot/cold tracking

        self.prev_in_battle = in_battle

        # === HM TILE DETECTION ===
        hm_cfg = w.get('hm_detection', {})
        tile_ahead = curr_state.get('tile_ahead', 0)
        map_tileset = curr_state.get('map_tileset', 0)
        current_hm_tile = (curr_state['map'], curr_state['x'], curr_state['y'], tile_ahead)

        # Only check once per unique position/tile combination
        if current_hm_tile != self.last_hm_tile:
            tile_key = (map_tileset, tile_ahead)

            if tile_key in CUT_TREE_TILES:
                has_cut = self._party_has_move(curr_state, HM_MOVES["cut"])
                if has_cut:
                    # Party has Cut - give reward for being near cuttable tree
                    hm_reward = hm_cfg.get('near_cut_tree', 10.0)
                    reward += hm_reward
                    breakdown['exploration'] += hm_reward
                    print(f"  {C.GREEN}[HM CUT]{C.RESET} Tree ahead! {C.GREEN}+{hm_reward}{C.RESET}")
                else:
                    # No Cut - show potential gain but no reward (not exploitable)
                    print(f"  {C.DIM}[HM CUT]{C.RESET} Tree ahead - {C.YELLOW}POTENTIAL +{hm_cfg.get('near_cut_tree', 10.0)}{C.RESET} {C.DIM}(need Cut){C.RESET}")

            elif tile_key in STRENGTH_BOULDER_TILES:
                has_strength = self._party_has_move(curr_state, HM_MOVES["strength"])
                if has_strength:
                    # Party has Strength - give reward
                    hm_reward = hm_cfg.get('near_strength_boulder', 10.0)
                    reward += hm_reward
                    breakdown['exploration'] += hm_reward
                    print(f"  {C.GREEN}[HM STRENGTH]{C.RESET} Boulder ahead! {C.GREEN}+{hm_reward}{C.RESET}")
                else:
                    # No Strength - show potential gain but no reward
                    print(f"  {C.DIM}[HM STRENGTH]{C.RESET} Boulder ahead - {C.YELLOW}POTENTIAL +{hm_cfg.get('near_strength_boulder', 10.0)}{C.RESET} {C.DIM}(need Strength){C.RESET}")

            self.last_hm_tile = current_hm_tile

        # === PARTY POKEMON ===
        leveling_cfg = w.get('leveling', {})
        healing_cfg = w.get('healing', {})

        for i in range(min(6, curr_state.get('party_count', 0))):
            prev_mon = prev_state.get('party', [None] * 6)[i]
            curr_mon = curr_state.get('party', [None] * 6)[i]
            if not prev_mon or not curr_mon:
                continue

            # Level up
            if curr_mon['level'] > prev_mon['level']:
                level_reward = 0.0
                if curr_mon['level'] <= 20:
                    level_reward = leveling_cfg.get('level_up_early', 1500.0)
                elif curr_mon['level'] <= 40:
                    level_reward = leveling_cfg.get('level_up_mid', 1000.0)
                else:
                    level_reward = leveling_cfg.get('level_up_late', 750.0)
                # Bonus for Pikachu (species 25)
                if curr_mon['species'] == 25:
                    level_reward += leveling_cfg.get('pikachu_bonus', 50.0)
                reward += level_reward
                breakdown['progression'] += level_reward
                self.max_party_levels[i] = max(self.max_party_levels[i], curr_mon['level'])

            # Healing (outside of battle)
            prev_hp_ratio = prev_mon['hp'] / max(prev_mon['max_hp'], 1)
            if curr_mon['hp'] > prev_mon['hp']:
                heal_reward = 0.0
                if prev_hp_ratio < 0.2:
                    heal_reward = healing_cfg.get('near_death_save', 50.0)
                elif prev_hp_ratio < 0.5:
                    heal_reward = healing_cfg.get('medium_save', 30.0)
                else:
                    heal_reward = healing_cfg.get('normal_heal', 10.0)
                reward += heal_reward
                breakdown['progression'] += heal_reward

            # Pokemon fainted (penalty)
            if penalties_enabled and prev_mon['hp'] > 0 and curr_mon['hp'] == 0:
                faint_penalty = penalties_cfg.get('pokemon_fainted', 50.0)
                faint_penalty *= noise_scale
                reward -= faint_penalty
                breakdown['penalties'] -= faint_penalty

        # === POKEDEX ===
        prog_cfg = w.get('progression', {})
        if curr_state['pokedex_owned'] > self.max_pokedex_owned:
            new_caught = curr_state['pokedex_owned'] - self.max_pokedex_owned

            # Skip reward for the very first Pokemon (Starter)
            if self.max_pokedex_owned == 0:
                pass
            else:
                catch_reward = prog_cfg.get('pokedex_catch', 15000.0) * new_caught
                reward += catch_reward
                breakdown['progression'] += catch_reward

            self.max_pokedex_owned = curr_state['pokedex_owned']

        # === BADGES ===
        if curr_state['badges'] > self.max_badges:
            new_badges = curr_state['badges'] - self.max_badges
            badge_reward = prog_cfg.get('badge', 50000.0) * new_badges
            reward += badge_reward
            breakdown['progression'] += badge_reward
            self.max_badges = curr_state['badges']

        # === ECONOMY ===
        econ_cfg = w.get('economy', {})
        curr_money = curr_state.get('money', 0)
        prev_money = prev_state.get('money', 0)
        if curr_money > prev_money:
            money_reward = (curr_money - prev_money) * econ_cfg.get('money_earned_multiplier', 0.1)
            reward += money_reward
            breakdown['progression'] += money_reward
        if penalties_enabled and curr_money == 0 and prev_money > 0:
            broke_penalty = econ_cfg.get('broke_penalty', 20.0)
            broke_penalty *= noise_scale
            reward -= broke_penalty
            breakdown['penalties'] -= broke_penalty

        # === STUCK DETECTION ===
        if curr_pos == self.stuck_position:
            self.stuck_frames += 1
            stuck_penalty = 0.0
            if self.stuck_frames == 100:
                stuck_penalty = penalties_cfg.get('stuck_100_frames', 10.0)
            elif self.stuck_frames == 500:
                stuck_penalty = penalties_cfg.get('stuck_500_frames', 50.0)
            elif self.stuck_frames >= 1000:
                stuck_penalty = penalties_cfg.get('stuck_1000_frames', 200.0)
            if penalties_enabled and stuck_penalty > 0:
                stuck_penalty *= noise_scale
                reward -= stuck_penalty
                breakdown['penalties'] -= stuck_penalty
        else:
            self.stuck_position = curr_pos
            self.stuck_frames = 0

        # === EXIT LAVA MODE ON POSITIVE REWARD ===
        if reward > 0:
            self.last_positive_reward_time = time.time()
            if self.lava_mode_active:
                print(f"  {C.GREEN}{C.BOLD}[LAVA MODE] Deactivated{C.RESET}{C.GREEN} - Positive reward gained!{C.RESET}")
                self.lava_mode_active = False
                self.lava_tile_visits.clear()

        # Log reward trace for debugging.
        try:
            REWARD_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            breakdown_serialized = {k: float(v) for k, v in breakdown.items()}
            reward_hash = hashlib.md5(
                json.dumps(breakdown_serialized, sort_keys=True, ensure_ascii=True).encode("utf-8")
            ).hexdigest()[:10]
            payload = {
                "ts": time.time(),
                "reward": float(reward),
                "hash": reward_hash,
                "breakdown": breakdown_serialized,
                "map_group": curr_state.get("map_group"),
                "map_number": curr_state.get("map_number"),
                "map": curr_state.get("map"),
                "x": curr_state.get("x"),
                "y": curr_state.get("y"),
                "width": curr_state.get("map_width"),
                "height": curr_state.get("map_height"),
                "text_box_id": curr_state.get("text_box_id"),
            }
            with open(REWARD_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=True) + "\n")
        except Exception:
            pass

        # Walk audit log (per step)
        try:
            WALK_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "step": self.step_index,
                "reward_total": float(reward),
                "new_tile_awarded": bool(new_tile_awarded),
                "new_tile_value": float(new_tile_value),
                "reason": "new_tile" if new_tile_awarded else "repeat_tile",
                "map_key": self._map_key(curr_state),
                "map_group": curr_state.get("map_group"),
                "map_number": curr_state.get("map_number"),
                "map": curr_state.get("map"),
                "x": curr_state.get("x"),
                "y": curr_state.get("y"),
                "width": curr_state.get("map_width"),
                "height": curr_state.get("map_height"),
            }
            with open(WALK_AUDIT_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=True) + "\n")
        except Exception:
            pass

        if return_breakdown:
            return reward, breakdown
        return reward

    def reset(self):
        """Full reset for new episode (Roguelite Mode - hard reset)."""
        # Reset all tracking
        self.dialogue_active_prev = False
        self.stuck_position = None
        self.stuck_frames = 0
        self.last_hm_tile = None

        # Reset exploration
        self.visited_tiles.clear()
        self.visited_buildings.clear()

        # Reset progression baselines (will re-init from fresh game state)
        self.initialized = False
        self.max_badges = None
        self.max_pokedex_owned = None
        self.max_party_levels = [0] * 6

        # Reset lava mode
        self.last_positive_reward_time = time.time()
        self.lava_mode_active = False
        self.lava_tile_visits.clear()

        # Reset battle tracking
        self.prev_enemy_hp = 0
        self.prev_player_move = 0
        self.prev_in_battle = 0
        self.battle_lowest_hp.clear()
        self.battle_status_turns.clear()

        # Reset HM targets
        self.hm_targets.clear()

        # Reset dynamic gravity curriculum
        self.gravity_map.reset()
        self.first_grass_reached = False
        self.left_start_map = False
        self.dialogue_after_grass_seen = False
        self.full_rewards_enabled = False
        self.full_rewards_enabled = False

