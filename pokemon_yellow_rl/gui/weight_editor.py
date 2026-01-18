"""Weight Editor GUI - Live tuning of reward weights during training"""
import json
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from typing import Dict, Any

# Weights file path
WEIGHTS_PATH = Path(__file__).parent.parent / "weights.json"
CONSTRAINTS_PATH = Path(__file__).parent.parent / "model_constraints.json"

# Default weights structure
DEFAULT_WEIGHTS = {
    "exploration": {
        "move_bonus": 0.5,
        "new_tile": 3.5,
        "new_tile_distance_bonus_max": 0.5,
        "new_building": 10.0,
        "distance_from_start_bonus": 50.0
    },
    "discovery": {
        "new_map": 50.0,
        "leave_start_map_bonus": 5000.0,
        "leave_start_map_post_level4_multiplier": 0.25,
        "center_hot_cold_step": 200.0,
        "center_hot_cold_backtrack_penalty": 100.0
    },
    "waterfall": {
        "base_bonus": 2.0,
        "step_bonus": 1.0,
        "max_bonus": 20.0
    },
    "battle": {
        "move_selection": 5.0,
        "damage_dealt_per_hp": 0.5,
        "damage_dealt_knockout_bonus": 25.0
    },
    "leveling": {
        "level_up_early": 1500.0,
        "level_up_mid": 1000.0,
        "level_up_late": 750.0,
        "pikachu_bonus": 50.0
    },
    "healing": {
        "near_death_save": 50.0,
        "medium_save": 30.0,
        "normal_heal": 10.0
    },
    "progression": {
        "badge": 50000.0,
        "pokedex_catch": 15000.0
    },
    "economy": {
        "money_earned_multiplier": 0.1,
        "broke_penalty": 20.0
    },
    "penalties": {
        "pokemon_fainted": 50.0,
        "save_menu": 100.0,
        "option_menu": 100.0,
        "exit_menu": 100.0,
    },
    "lava_mode": {
        "trigger_seconds": 30,
        "base_revisit_penalty": 1.0
    },
    "hm_detection": {
        "near_cut_tree": 10.0,
        "near_strength_boulder": 10.0
    }
}

# Default model constraints
DEFAULT_CONSTRAINTS = {
    "learning_rate": 0.005,
    "ent_coef": 0.05,
    "ent_coef_level_1": 0.07,
    "ent_coef_level_2": 0.05,
    "ent_coef_level_3": 0.04,
    "ent_coef_level_4": 0.03,
    "ent_coef_decay_base": 0.05,
    "ent_coef_decay": 0.9,
    "ent_coef_floor": 0.02,
}

# Slider configurations: (min, max, resolution)
SLIDER_CONFIG = {
    # Exploration
    "move_bonus": (0, 5, 0.1),
    "new_tile": (0, 20, 0.5),
    "new_tile_distance_bonus_max": (0, 5, 0.1),
    "new_building": (0, 100, 1),
    "distance_from_start_bonus": (0, 200, 5),
    "new_map": (0, 200, 5),
    "base_bonus": (0, 20, 0.5),
    "step_bonus": (0, 10, 0.5),
    "max_bonus": (0, 50, 1),
    "leave_start_map_bonus": (0, 20000, 500),
    "leave_start_map_post_level4_multiplier": (0.0, 1.0, 0.05),
    "center_hot_cold_step": (0, 500, 10),
    "center_hot_cold_backtrack_penalty": (0, 500, 10),
    # Battle
    "move_selection": (20, 50, 1),
    "damage_dealt_per_hp": (0, 5, 0.1),
    "damage_dealt_knockout_bonus": (0, 100, 1),
    # Leveling
    "level_up_early": (0, 5000, 50),
    "level_up_mid": (0, 5000, 50),
    "level_up_late": (0, 5000, 50),
    "pikachu_bonus": (0, 500, 10),
    # Healing
    "near_death_save": (0, 200, 5),
    "medium_save": (0, 200, 5),
    "normal_heal": (0, 100, 1),
    # Progression
    "badge": (0, 200000, 1000),
    "pokedex_catch": (0, 100000, 500),
    # Economy
    "money_earned_multiplier": (0, 1, 0.01),
    "broke_penalty": (0, 100, 1),
    # Penalties
    "pokemon_fainted": (0, 200, 5),
    "save_menu": (0, 500, 10),
    "option_menu": (0, 500, 10),
    "exit_menu": (0, 500, 10),
    # Lava mode
    "trigger_seconds": (5, 120, 5),
    "base_revisit_penalty": (0, 10, 0.5),
    # HM detection
    "near_cut_tree": (0, 50, 1),
    "near_strength_boulder": (0, 50, 1),
    # Model constraints
    "learning_rate": (0.0001, 0.02, 0.0001),
    "ent_coef": (0.0, 0.2, 0.001),
    "ent_coef_level_1": (0.0, 0.2, 0.001),
    "ent_coef_level_2": (0.0, 0.2, 0.001),
    "ent_coef_level_3": (0.0, 0.2, 0.001),
    "ent_coef_level_4": (0.0, 0.2, 0.001),
    "ent_coef_decay_base": (0.0, 0.2, 0.001),
    "ent_coef_decay": (0.5, 1.0, 0.01),
    "ent_coef_floor": (0.0, 0.1, 0.001),
}


class WeightEditorGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Pokemon Yellow RL - Weight Editor")
        self.root.geometry("480x420")
        self.root.resizable(True, True)

        # Load current weights
        self.weights = self.load_weights()
        self.constraints = self.load_constraints()

        # Store slider/entry widgets
        self.widgets: Dict[str, Dict[str, Any]] = {}

        # Create UI
        self.create_ui()

    def load_weights(self) -> Dict:
        """Load weights from JSON file."""
        try:
            if WEIGHTS_PATH.exists():
                with open(WEIGHTS_PATH) as f:
                    return json.load(f)
        except Exception as e:
            print(f"Failed to load weights: {e}")
        return DEFAULT_WEIGHTS.copy()

    def load_constraints(self) -> Dict:
        """Load model constraints from JSON file."""
        try:
            if CONSTRAINTS_PATH.exists():
                with open(CONSTRAINTS_PATH) as f:
                    return json.load(f)
        except Exception as e:
            print(f"Failed to load constraints: {e}")
        return DEFAULT_CONSTRAINTS.copy()

    def save_weights(self):
        """Save current weights to JSON file."""
        try:
            with open(WEIGHTS_PATH, 'w') as f:
                json.dump(self.weights, f, indent=4)
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save weights: {e}")
            return False

    def save_constraints(self):
        """Save model constraints to JSON file."""
        try:
            with open(CONSTRAINTS_PATH, 'w') as f:
                json.dump(self.constraints, f, indent=4)
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save constraints: {e}")
            return False

    def create_ui(self):
        """Create the main UI."""
        # Main container with scrollbar
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Canvas for scrolling
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Enable mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Pack scrollbar and canvas
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Create sections for each weight category
        row = 0
        for category, values in self.weights.items():
            self.create_category_section(scrollable_frame, category, values, row)
            row += 1

        # Model constraints section
        self.create_category_section(scrollable_frame, "model_constraints", self.constraints, row)

        # Button frame at bottom (outside scroll area)
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        # UPDATE button (prominent)
        update_btn = ttk.Button(
            button_frame,
            text="UPDATE WEIGHTS",
            command=self.update_weights,
            style="Accent.TButton"
        )
        update_btn.pack(side=tk.LEFT, padx=5)

        # Reload from file button
        reload_btn = ttk.Button(
            button_frame,
            text="Reload from File",
            command=self.reload_from_file
        )
        reload_btn.pack(side=tk.LEFT, padx=5)

        # Reset to defaults button
        reset_btn = ttk.Button(
            button_frame,
            text="Reset to Defaults",
            command=self.reset_to_defaults
        )
        reset_btn.pack(side=tk.LEFT, padx=5)

        # Status label
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(button_frame, textvariable=self.status_var)
        status_label.pack(side=tk.RIGHT, padx=5)

        # Style for accent button
        style = ttk.Style()
        style.configure("Accent.TButton", font=('Helvetica', 10, 'bold'))

    def create_category_section(self, parent: ttk.Frame, category: str, values: Dict, row: int):
        """Create a collapsible section for a weight category."""
        # Category label frame
        frame = ttk.LabelFrame(parent, text=category.replace("_", " ").title(), padding=10)
        frame.pack(fill=tk.X, padx=5, pady=5)

        self.widgets[category] = {}

        for i, (key, value) in enumerate(values.items()):
            # Get slider config
            config = SLIDER_CONFIG.get(key, (0, 100, 1))
            min_val, max_val, resolution = config

            # Row frame
            row_frame = ttk.Frame(frame)
            row_frame.pack(fill=tk.X, pady=2)

            # Label
            label_text = key.replace("_", " ").title()
            label = ttk.Label(row_frame, text=label_text, width=25, anchor="w")
            label.pack(side=tk.LEFT, padx=5)

            # Value entry
            var = tk.DoubleVar(value=value)
            entry = ttk.Entry(row_frame, textvariable=var, width=10)
            entry.pack(side=tk.RIGHT, padx=5)

            # Slider
            slider = ttk.Scale(
                row_frame,
                from_=min_val,
                to=max_val,
                variable=var,
                orient=tk.HORIZONTAL,
                length=300
            )
            slider.pack(side=tk.RIGHT, padx=5, fill=tk.X, expand=True)

            # Store widget reference
            self.widgets[category][key] = {
                'var': var,
                'slider': slider,
                'entry': entry
            }

    def update_weights(self):
        """Update weights from UI values and save to file."""
        # Collect values from widgets
        for category, keys in self.widgets.items():
            for key, widget_data in keys.items():
                try:
                    value = widget_data['var'].get()
                    if category == "model_constraints":
                        self.constraints[key] = value
                    else:
                        if category not in self.weights:
                            self.weights[category] = {}
                        self.weights[category][key] = value
                except Exception:
                    pass

        # Save to file
        weights_ok = self.save_weights()
        constraints_ok = self.save_constraints()
        if weights_ok and constraints_ok:
            self.status_var.set("Weights updated! Training will pick up changes automatically.")
            self.root.after(3000, lambda: self.status_var.set("Ready"))

    def reload_from_file(self):
        """Reload weights from file and update UI."""
        self.weights = self.load_weights()
        self.constraints = self.load_constraints()
        self.update_ui_from_weights()
        self.status_var.set("Reloaded from file")
        self.root.after(2000, lambda: self.status_var.set("Ready"))

    def reset_to_defaults(self):
        """Reset all weights to default values."""
        if messagebox.askyesno("Confirm Reset", "Reset all weights to default values?"):
            self.weights = DEFAULT_WEIGHTS.copy()
            self.constraints = DEFAULT_CONSTRAINTS.copy()
            self.update_ui_from_weights()
            self.save_weights()
            self.save_constraints()
            self.status_var.set("Reset to defaults")
            self.root.after(2000, lambda: self.status_var.set("Ready"))

    def update_ui_from_weights(self):
        """Update all UI widgets from current weights."""
        for category, keys in self.widgets.items():
            if category == "model_constraints":
                for key, widget_data in keys.items():
                    if key in self.constraints:
                        widget_data['var'].set(self.constraints[key])
            elif category in self.weights:
                for key, widget_data in keys.items():
                    if key in self.weights[category]:
                        widget_data['var'].set(self.weights[category][key])

    def run(self):
        """Start the GUI main loop."""
        self.root.mainloop()


def main():
    """Entry point for weight editor GUI."""
    app = WeightEditorGUI()
    app.run()


if __name__ == "__main__":
    main()
