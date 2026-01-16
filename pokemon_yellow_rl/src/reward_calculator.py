"""Reward Calculator - 91 reward events for Pokemon Yellow RL"""
from typing import Dict, Set, Tuple, Optional

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


class RewardCalculator:
    def __init__(self):
        # Exploration tracking
        self.visited_tiles: Set[Tuple[int, int, int]] = set()  # (map, x, y)
        self.visited_buildings: Set[int] = set()  # map IDs

        # Dialogue tracking (diminishing returns)
        self.npc_talk_count: Dict[Tuple[int, int], int] = {}  # (map, npc_id) -> count
        self.dialogue_active_prev = False

        # Pokemon tracking
        self.best_stats_per_species: Dict[int, Dict] = {}  # species -> {attack, defense, etc}
        self.max_pokedex_owned = None  # None = not initialized yet

        # Progression tracking
        self.max_party_levels = [0] * 6
        self.max_badges = None  # None = not initialized yet
        self.max_money = 0
        self.initialized = False

        # HM usage tracking (anti-spam)
        self.last_hm_use: Dict[str, Tuple[int, int, int, int]] = {}  # hm -> (map, x, y, frame)

        # Stuck detection
        self.stuck_position: Optional[Tuple[int, int, int]] = None
        self.stuck_frames = 0

    def initialize_from_state(self, state: Dict):
        """Initialize baseline values from first VALID state read."""
        if self.initialized:
            return

        # State already validated by _is_garbage_state before calling this
        badges = state.get('badges', 0)
        pokedex = state.get('pokedex_owned', 0)

        self.max_badges = badges
        self.max_pokedex_owned = pokedex

        self.visited_buildings.add(state.get('map', 0))
        curr_pos = (state.get('map', 0), state.get('x', 0), state.get('y', 0))
        self.visited_tiles.add(curr_pos)
        self.initialized = True
        print(f"  [INIT] Baseline: {self.max_badges} badges, {self.max_pokedex_owned} pokedex")

    def _distance_to_nearest_center(self, map_id: int, x: int, y: int) -> float:
        """Calculate distance to nearest known Pokemon Center."""
        min_dist = float('inf')
        for center_map, cx, cy in POKEMON_CENTERS:
            if center_map == map_id:
                # Same map - direct distance
                dist = abs(x - cx) + abs(y - cy)
            else:
                # Different map - use map difference as proxy (rough estimate)
                dist = abs(map_id - center_map) * 10 + abs(x - cx) + abs(y - cy)
            min_dist = min(min_dist, dist)
        return min_dist if min_dist != float('inf') else 50.0

    def _is_garbage_state(self, state: Dict) -> bool:
        """Check if state looks like garbage memory."""
        badges = state.get('badges', 0)
        pokedex = state.get('pokedex_owned', 0)
        party_count = state.get('party_count', 0)

        # Garbage: invalid party count (0 is valid for intro)
        if party_count < 0 or party_count > 6:
            return True
        # Garbage: impossible values
        if badges > 8 or pokedex > 151:
            return True
        # Garbage: pokedex way higher than party (can't have 20 pokedex with 1 pokemon early game)
        # Exception: 0 party (intro) but small pokedex is fine
        if party_count > 0 and pokedex > party_count + 10:
            return True
        return False

    def calculate_reward(self, prev_state: Dict, curr_state: Dict) -> float:
        """Calculate reward from state transition."""
        # Skip if either state looks like garbage memory
        if self._is_garbage_state(prev_state) or self._is_garbage_state(curr_state):
            return 0.0

        # Initialize baseline from first state
        if not self.initialized:
            self.initialize_from_state(prev_state)
            if not self.initialized:
                # Still waiting for valid game state
                return 0.0

        reward = 0.0

        # === EXPLORATION ===
        curr_pos = (curr_state['map'], curr_state['x'], curr_state['y'])
        if curr_pos not in self.visited_tiles:
            # Base reward for new tile
            base_reward = 3.5
            # Distance bonus: slight increase the farther from any Pokemon Center
            distance = self._distance_to_nearest_center(curr_state['map'], curr_state['x'], curr_state['y'])
            distance_bonus = min(distance * 0.01, 0.5)  # Cap at 0.5 extra
            reward += base_reward + distance_bonus
            self.visited_tiles.add(curr_pos)
        # No reward for revisiting - only new exploration matters

        if curr_state['map'] not in self.visited_buildings:
            reward += 10.0  # New building/area
            self.visited_buildings.add(curr_state['map'])

        # === MENU / DIALOGUE MANAGEMENT ===
        # Removed generic dialogue rewards to prevent "Save Game" farming.
        
        # Penalize wasting time in useless menus
        # Start Menu Layout:
        # 0: Pokedex (Also "Yes" in dialogs - DO NOT PENALIZE)
        # 1: Pokemon (Allowed)
        # 2: Item (Allowed)
        # 3: Character (Penalize)
        # 4: Save (Penalize)
        # 5: Option (Penalize)
        # 6: Exit (Allowed)
        
        menu_item = curr_state.get('menu_item', 0)
        dialogue_active = curr_state.get('text_box_id', 0) > 0
        
        # Only penalize if we are in a menu/dialogue context
        if dialogue_active:
            # EXTREME penalty for "Save" (4), "Option" (5), and "Exit" (6)
            # User calls Exit "Quit" - forcing use of 'B' button to close menu is faster/better
            if menu_item in [4, 5, 6]:
                reward -= 100.0
            
            # Penalize Character (3)
            elif menu_item == 3:
                reward -= 5.0
            
            # Small penalty for just sitting in a menu/dialogue to encourage closing it
            # (unless it's a useful one, but hard to tell)
            # reward -= 0.1 

        self.dialogue_active_prev = dialogue_active

        # === PARTY POKEMON ===
        for i in range(min(6, curr_state.get('party_count', 0))):
            prev_mon = prev_state.get('party', [None] * 6)[i]
            curr_mon = curr_state.get('party', [None] * 6)[i]
            if not prev_mon or not curr_mon:
                continue

            # Level up (VERY HIGH)
            if curr_mon['level'] > prev_mon['level']:
                if curr_mon['level'] <= 20:
                    reward += 150.0  # Early game critical
                elif curr_mon['level'] <= 40:
                    reward += 100.0  # Mid game
                else:
                    reward += 75.0   # Late game
                # Bonus for Pikachu (species 25)
                if curr_mon['species'] == 25:
                    reward += 50.0
                self.max_party_levels[i] = max(self.max_party_levels[i], curr_mon['level'])

            # Healing (HIGH priority for weak Pokemon)
            prev_hp_ratio = prev_mon['hp'] / max(prev_mon['max_hp'], 1)
            curr_hp_ratio = curr_mon['hp'] / max(curr_mon['max_hp'], 1)
            if curr_mon['hp'] > prev_mon['hp']:
                if prev_hp_ratio < 0.2:
                    reward += 50.0  # Near-death save (HIGH)
                elif prev_hp_ratio < 0.5:
                    reward += 30.0  # Medium save
                else:
                    reward += 10.0  # Normal heal

            # Pokemon fainted (penalty)
            if prev_mon['hp'] > 0 and curr_mon['hp'] == 0:
                reward -= 50.0

        # === POKEDEX (EXTREME reward for new species) ===
        if curr_state['pokedex_owned'] > self.max_pokedex_owned:
            new_caught = curr_state['pokedex_owned'] - self.max_pokedex_owned
            
            # Skip reward for the very first Pokemon (Starter)
            # We assume going from 0 -> 1 is the starter being loaded
            if self.max_pokedex_owned == 0:
                pass
            else:
                reward += 1500.0 * new_caught  # EXTREME
            
            self.max_pokedex_owned = curr_state['pokedex_owned']

        # === BADGES (MASSIVE pull toward progression) ===
        if curr_state['badges'] > self.max_badges:
            new_badges = curr_state['badges'] - self.max_badges
            reward += 5000.0 * new_badges  # MASSIVE
            self.max_badges = curr_state['badges']

        # === ECONOMY ===
        curr_money = curr_state.get('money', 0)
        prev_money = prev_state.get('money', 0)
        if curr_money > prev_money:
            reward += (curr_money - prev_money) * 0.1  # Money earned
        if curr_money == 0 and prev_money > 0:
            reward -= 20.0  # Went broke penalty (don't penalize starting with 0)

        # === STUCK DETECTION ===
        if curr_pos == self.stuck_position:
            self.stuck_frames += 1
            if self.stuck_frames == 100:
                reward -= 10.0
            elif self.stuck_frames == 500:
                reward -= 50.0
            elif self.stuck_frames >= 1000:
                reward -= 200.0  # Episode timeout
        else:
            self.stuck_position = curr_pos
            self.stuck_frames = 0

        return reward

    def reset(self):
        """Full reset for new episode (Roguelite Mode - hard reset)."""
        # Reset all tracking
        self.dialogue_active_prev = False
        self.stuck_position = None
        self.stuck_frames = 0
        self.last_hm_use.clear()

        # Reset exploration
        self.visited_tiles.clear()
        self.visited_buildings.clear()
        self.npc_talk_count.clear()

        # Reset progression baselines (will re-init from fresh game state)
        self.initialized = False
        self.max_badges = None
        self.max_pokedex_owned = None
        self.max_party_levels = [0] * 6
