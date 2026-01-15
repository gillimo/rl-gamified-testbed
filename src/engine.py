import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SCHEMA_PATH = DATA_DIR / "schema.json"
REF_PATH = DATA_DIR / "reference.json"


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def get_reference():
    return load_json(REF_PATH, {})


def validate_state(state):
    errors = []
    if not isinstance(state, dict):
        return ["state must be a JSON object"]
    if "version" not in state:
        errors.append("missing version")
    for key in ["account", "skills", "goals"]:
        if key not in state:
            errors.append(f"missing {key}")
    return errors


def migrate_state(state):
    if not isinstance(state, dict):
        return state
    version = state.get("version", 0)
    if version == 0:
        state["version"] = 1
    return state


def compute_ratings(state):
    skills = state.get("skills", {})
    skill_avg = sum(skills.values()) / max(1, len(skills)) if skills else 0
    ratings = {
        "readiness": min(100, int(skill_avg * 1.1)),
        "progress": min(100, int(len(state.get("goals", {}).get("short", [])) * 10)),
    }
    reasons = {
        "readiness": ["average skill level", "core requirements", "resources"],
        "progress": ["goals defined", "dependencies", "timeline"],
    }
    return ratings, reasons


def detect_bottlenecks(_state):
    return ["missing reference data", "goals not refined"]


def build_dependency_graph(_state):
    ref = get_reference()
    deps = ref.get("dependencies", [])
    graph = defaultdict(list)
    for d in deps:
        name = d.get("name")
        for req in d.get("requires", []):
            graph[name].append(req)
    return graph


def generate_plan(state):
    goals = state.get("goals", {})
    plan = {"short": [], "mid": [], "long": []}
    for g in goals.get("short", []):
        plan["short"].append({"task": g, "why": "priority goal", "time": "tbd", "prereqs": []})
    return plan


def compare_paths(_state):
    return [
        {"path": "fast", "tradeoff": "higher cost", "notes": "buy inputs"},
        {"path": "cheap", "tradeoff": "slower", "notes": "self produce"},
    ]


def risk_score(_state):
    return 50
