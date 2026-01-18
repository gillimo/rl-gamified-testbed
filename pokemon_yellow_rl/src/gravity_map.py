"""Dynamic gravity map curriculum for pre-grass navigation."""
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

GRAVITY_CONFIG_PATH = Path(__file__).parent.parent / "gravity_ratings.json"


def _load_config() -> Dict:
    default_config = {
        "enabled": True,
        "new_tile_reward": 1.0,
        "repeat_penalty": 0.5,
        "door_min_reward": 1.0,
        "door_max_reward": 40.0,
        "door_distance_max": 30.0,
        "poi_min_reward": 1.0,
        "poi_max_reward": 10.0,
        "poi_distance_max": 15.0,
        "entry_negative_steps": 200,
        "entry_negative_scale": 1.0,
        "poi_cooldown_seconds": 300.0,
        "pc_text_ids": [],
        "pc_cooldown_seconds": 300.0,
        "gravity_delta_scale": 1.0,
    }
    try:
        if GRAVITY_CONFIG_PATH.exists():
            with open(GRAVITY_CONFIG_PATH, "r") as f:
                data = json.load(f)
                default_config.update(data)
    except Exception:
        pass
    return default_config


class GravityMap:
    """Track dynamic doors/POIs and compute gravity-based rewards."""

    def __init__(self) -> None:
        self.config = _load_config()
        self.config_mtime = GRAVITY_CONFIG_PATH.stat().st_mtime if GRAVITY_CONFIG_PATH.exists() else 0
        self.doors_per_map: Dict[int, Set[Tuple[int, int]]] = {}
        self.pois_per_map: Dict[int, Dict[Tuple[int, int], float]] = {}
        self.visited_tiles: Dict[int, Set[Tuple[int, int]]] = {}
        self.current_map_id: Optional[int] = None
        self.entry_door_pos: Optional[Tuple[int, int]] = None
        self.steps_in_room = 0
        self.lava_mode_active = False
        self.last_positive_time = time.time()

    def reset(self) -> None:
        self.doors_per_map.clear()
        self.pois_per_map.clear()
        self.visited_tiles.clear()
        self.current_map_id = None
        self.entry_door_pos = None
        self.steps_in_room = 0
        self.lava_mode_active = False
        self.last_positive_time = time.time()

    def reload_config(self) -> None:
        try:
            if GRAVITY_CONFIG_PATH.exists():
                current_mtime = GRAVITY_CONFIG_PATH.stat().st_mtime
                if current_mtime > self.config_mtime:
                    self.config = _load_config()
                    self.config_mtime = current_mtime
        except Exception:
            pass

    def update(self, prev_state: Dict, curr_state: Dict) -> None:
        """Update door/POI discovery based on state transition."""
        self.reload_config()
        prev_map = prev_state.get("map", 0)
        curr_map = curr_state.get("map", 0)
        prev_pos = (prev_state.get("x", 0), prev_state.get("y", 0))
        curr_pos = (curr_state.get("x", 0), curr_state.get("y", 0))

        if self.current_map_id != curr_map:
            self.current_map_id = curr_map
            self.steps_in_room = 0
            self.entry_door_pos = curr_pos

        if prev_map != curr_map:
            self._add_door(prev_map, prev_pos)
            self._add_door(curr_map, curr_pos)
        else:
            self.steps_in_room += 1

        prev_text = prev_state.get("text_box_id", 0)
        curr_text = curr_state.get("text_box_id", 0)
        if curr_text > 0 and curr_text != prev_text:
            self._add_poi(curr_map, curr_pos, curr_text)

    def _add_door(self, map_id: int, pos: Tuple[int, int]) -> None:
        if map_id not in self.doors_per_map:
            self.doors_per_map[map_id] = set()
        self.doors_per_map[map_id].add(pos)

    def _add_poi(self, map_id: int, pos: Tuple[int, int], text_id: int) -> None:
        if map_id not in self.pois_per_map:
            self.pois_per_map[map_id] = {}
        if pos not in self.pois_per_map[map_id]:
            self.pois_per_map[map_id][pos] = 0.0
        # Store last seen time for cooldown.
        self.pois_per_map[map_id][pos] = time.time()

    def _value_from_distance(self, dist: float, min_val: float, max_val: float, max_dist: float) -> float:
        if max_dist <= 0:
            return max_val
        step = (max_val - min_val) / max_dist
        return max(min_val, max_val - dist * step)

    def _entry_negative_active(self, map_id: int) -> bool:
        if self.entry_door_pos is None:
            return False
        door_count = len(self.doors_per_map.get(map_id, set()))
        if door_count <= 1:
            return self.steps_in_room < int(self.config.get("entry_negative_steps", 200))
        return True

    def _poi_cooldown_active(self, map_id: int, pos: Tuple[int, int]) -> bool:
        last = self.pois_per_map.get(map_id, {}).get(pos)
        if not last:
            return False
        cooldown = float(self.config.get("poi_cooldown_seconds", 300.0))
        return (time.time() - last) < cooldown

    def compute_position_value(self, map_id: int, x: int, y: int) -> float:
        door_min = float(self.config.get("door_min_reward", 1.0))
        door_max = float(self.config.get("door_max_reward", 40.0))
        door_dist_max = float(self.config.get("door_distance_max", 30.0))
        poi_min = float(self.config.get("poi_min_reward", 1.0))
        poi_max = float(self.config.get("poi_max_reward", 10.0))
        poi_dist_max = float(self.config.get("poi_distance_max", 15.0))

        best_value = 0.0

        for door in self.doors_per_map.get(map_id, set()):
            dist = abs(x - door[0]) + abs(y - door[1])
            value = self._value_from_distance(dist, door_min, door_max, door_dist_max)
            best_value = max(best_value, value)

        for poi in self.pois_per_map.get(map_id, {}):
            if self._poi_cooldown_active(map_id, poi):
                continue
            dist = abs(x - poi[0]) + abs(y - poi[1])
            value = self._value_from_distance(dist, poi_min, poi_max, poi_dist_max)
            best_value = max(best_value, value)

        if self._entry_negative_active(map_id) and self.entry_door_pos is not None:
            dist = abs(x - self.entry_door_pos[0]) + abs(y - self.entry_door_pos[1])
            penalty = self._value_from_distance(dist, door_min, door_max, door_dist_max)
            best_value -= penalty * float(self.config.get("entry_negative_scale", 1.0))

        return best_value

    def compute_reward(self, prev_state: Dict, curr_state: Dict) -> float:
        if not self.config.get("enabled", True):
            return 0.0

        prev_map = prev_state.get("map", 0)
        curr_map = curr_state.get("map", 0)
        prev_x = prev_state.get("x", 0)
        prev_y = prev_state.get("y", 0)
        curr_x = curr_state.get("x", 0)
        curr_y = curr_state.get("y", 0)

        prev_value = self.compute_position_value(prev_map, prev_x, prev_y)
        curr_value = self.compute_position_value(curr_map, curr_x, curr_y)

        reward = (curr_value - prev_value) * float(self.config.get("gravity_delta_scale", 1.0))

        new_tile_reward = float(self.config.get("new_tile_reward", 0.0))
        repeat_penalty = float(self.config.get("repeat_penalty", 0.0))
        curr_pos = (curr_x, curr_y)
        if curr_map not in self.visited_tiles:
            self.visited_tiles[curr_map] = set()
        if curr_pos not in self.visited_tiles[curr_map]:
            self.visited_tiles[curr_map].add(curr_pos)
            reward += new_tile_reward
        else:
            # Apply repeat penalty only when lava mode is active.
            if self.lava_mode_active:
                reward -= repeat_penalty

        # Update lava mode trigger based on last positive reward.
        if reward > 0:
            self.last_positive_time = time.time()
            self.lava_mode_active = False
        else:
            trigger_seconds = float(self.config.get("lava_trigger_seconds", 10.0))
            if (time.time() - self.last_positive_time) >= trigger_seconds:
                self.lava_mode_active = True

        return reward

    def get_grid_values(self, map_id: int, width: int, height: int) -> List[List[float]]:
        grid = []
        for y in range(height):
            row = []
            for x in range(width):
                row.append(self.compute_position_value(map_id, x, y))
            grid.append(row)
        return grid
