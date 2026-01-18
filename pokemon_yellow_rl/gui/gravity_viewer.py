"""Gravity Map Viewer - Live view of gravity values per room."""
import json
import time
from pathlib import Path
import tkinter as tk

from src.gravity_map import GravityMap

STATE_PATH = Path(__file__).parent.parent.parent / "data" / "emulator_state.json"


class GravityViewer:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Pokemon Yellow RL - Gravity Map")
        self.root.geometry("640x720")

        self.header = tk.Label(self.root, text="Gravity Map", font=("Consolas", 12, "bold"))
        self.header.pack(anchor="w", padx=8, pady=(8, 4))

        self.text = tk.Text(self.root, width=80, height=40, font=("Consolas", 8))
        self.text.pack(fill="both", expand=True, padx=8, pady=8)

        self.gravity = GravityMap()
        self.prev_state = None

        self.root.after(200, self._tick)

    def _read_state(self):
        try:
            if STATE_PATH.exists():
                with open(STATE_PATH, "r") as f:
                    return json.load(f)
        except Exception:
            return None
        return None

    def _format_grid(self, grid, player_pos):
        lines = []
        for y, row in enumerate(grid):
            parts = []
            for x, val in enumerate(row):
                if (x, y) == player_pos:
                    parts.append("##")
                else:
                    parts.append(f"{int(val):02d}")
            lines.append(" ".join(parts))
        return "\n".join(lines)

    def _tick(self):
        state = self._read_state()
        if state:
            if self.prev_state:
                self.gravity.update(self.prev_state, state)
            else:
                self.gravity.update(state, state)
            self.prev_state = state

            map_id = state.get("map", 0)
            map_width = state.get("map_width", 0)
            map_height = state.get("map_height", 0)
            width = max(1, int(map_width) * 2)
            height = max(1, int(map_height) * 2)
            width = min(width, 40)
            height = min(height, 36)

            grid = self.gravity.get_grid_values(map_id, width, height)
            player_pos = (state.get("x", 0), state.get("y", 0))

            header = (
                f"Map: {map_id}  Pos: {player_pos}  Size: {width}x{height}  "
                f"Doors: {len(self.gravity.doors_per_map.get(map_id, []))}  "
                f"POIs: {len(self.gravity.pois_per_map.get(map_id, {}))}"
            )

            self.text.delete("1.0", tk.END)
            self.text.insert(tk.END, header + "\n\n")
            self.text.insert(tk.END, self._format_grid(grid, player_pos))

        self.root.after(200, self._tick)


def main():
    app = GravityViewer()
    app.root.mainloop()


if __name__ == "__main__":
    main()
