"""Hierarchical Goal Manager using Phi3 for Pokemon Yellow."""
import json
from typing import Dict, Any, Optional
from agent_core.models import Executor


class GoalManager:
    """Manages short-term tactical and medium-term strategic goals."""

    def __init__(self, executor_model: str = "phi3", timeout: float = 30.0):
        self.executor = Executor(model=executor_model, timeout=timeout)
        # NO hardcoded goals - Phi3 sets them on first observation
        self.medium_term_goal = None
        self.short_term_goal = None
        self.context_history = []
        self.steps_since_goal_update = 0
        self.goal_update_frequency = 1  # Update goals EVERY step initially until set

    def update_goals(self, game_state: Dict, ocr_text: str,
                     visual_obs: str, last_action: Optional[str]) -> None:
        """Update goals based on current context using Phi3.

        Args:
            game_state: Dict with 'map', 'pos', 'battle'
            ocr_text: Text extracted via OCR
            visual_obs: Visual description from Moondream
            last_action: Last button pressed
        """
        # Build context
        context = {
            "map": game_state.get("map"),
            "position": game_state.get("pos"),
            "battle": game_state.get("battle"),
            "text_on_screen": ocr_text,
            "visual": visual_obs,
            "last_action": last_action
        }
        self.context_history.append(context)

        # Keep last 5 contexts for progress tracking
        if len(self.context_history) > 5:
            self.context_history.pop(0)

        # ALWAYS update if goals not set yet (first run)
        if self.medium_term_goal is None or self.short_term_goal is None:
            self.steps_since_goal_update = 0
        else:
            # Only update goals every N steps to save time (once goals exist)
            self.steps_since_goal_update += 1
            if self.steps_since_goal_update < self.goal_update_frequency:
                return
            self.steps_since_goal_update = 0
            # After first goals set, reduce update frequency
            self.goal_update_frequency = 3

        # Ask Phi3 to analyze progress and set/update goals
        if self.medium_term_goal is None:
            task_instruction = """TASK: This is the first observation. Set initial goals based on what you see.
1. What should the SHORT-TERM goal be? (specific next action)
2. What should the MEDIUM-TERM goal be? (strategic objective for Pokemon Yellow)

Respond in this format:
SHORT_TERM: <specific next action goal>
MEDIUM_TERM: <strategic objective>
REASONING: <why these goals>"""
        else:
            task_instruction = f"""CURRENT GOALS:
- Medium-term: {self.medium_term_goal}
- Short-term: {self.short_term_goal}

TASK: Update goals based on progress.
1. Has the short-term goal been achieved? If yes, what's the next short-term goal?
2. Is the medium-term goal still relevant? If not, what's the new medium-term goal?

Respond in this format:
SHORT_TERM: <specific next action goal>
MEDIUM_TERM: <strategic objective>
REASONING: <why these goals>"""

        prompt = f"""You are tracking goals for Pokemon Yellow agent.

CURRENT SITUATION:
- Map: {context['map']}, Position: {context['position']}
- Text on screen: "{ocr_text}"
- Visual: {visual_obs[:100]}...
- Last action: {last_action}

RECENT HISTORY (last {len(self.context_history)} steps):
{json.dumps(self.context_history, indent=2)}

{task_instruction}"""

        response = self.executor.decide(context=prompt,
                                       options=["analyze"],
                                       goal="Update goals")

        # Parse response
        lines = response.split('\n')
        for line in lines:
            if line.startswith("SHORT_TERM:"):
                self.short_term_goal = line.replace("SHORT_TERM:", "").strip()
            elif line.startswith("MEDIUM_TERM:"):
                self.medium_term_goal = line.replace("MEDIUM_TERM:", "").strip()

    def get_goal_context(self) -> str:
        """Get formatted goal context for Executor."""
        if self.medium_term_goal is None or self.short_term_goal is None:
            return "CURRENT GOALS: Not yet set (analyzing first observation...)"
        return f"""CURRENT GOALS:
Medium-term: {self.medium_term_goal}
Short-term: {self.short_term_goal}"""

    def is_stuck(self) -> bool:
        """Detect if agent is stuck (same position, no text changes)."""
        if len(self.context_history) < 3:
            return False

        # Check last 3 positions
        recent = self.context_history[-3:]
        positions = [c.get("position") for c in recent]
        texts = [c.get("text_on_screen", "").strip() for c in recent]

        # Stuck if position unchanged AND text unchanged
        return (len(set(positions)) == 1 and len(set(texts)) == 1)

    def has_question_mark(self, ocr_text: str) -> bool:
        """Simple check: does text contain a question mark?"""
        return "?" in ocr_text

    def get_unstuck_action(self) -> str:
        """Suggest action to get unstuck."""
        # If dialogue isn't advancing, mash A
        recent_text = [c.get("text_on_screen", "") for c in self.context_history[-3:]]
        if any("?" in t or "!" in t for t in recent_text):
            return "A"  # Dialogue likely needs confirmation

        # Otherwise try B to back out or START for menu
        return "B"
