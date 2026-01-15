import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from src.engine import compute_ratings, generate_plan, detect_bottlenecks, build_dependency_graph

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "state.json"


def load_state():
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _add_label_block(parent, text):
    ttk.Label(parent, text=text, justify="left").pack(anchor="w", padx=12, pady=12)


def run_app():
    state = load_state()
    root = tk.Tk()
    root.title("<project_name>")
    root.geometry("980x560")

    paned = ttk.Panedwindow(root, orient="horizontal")
    paned.pack(fill="both", expand=True)

    left = ttk.Frame(paned)
    right = ttk.Frame(paned)
    paned.add(left, weight=2)
    paned.add(right, weight=1)

    notebook = ttk.Notebook(left)
    notebook.pack(fill="both", expand=True)

    overview = ttk.Frame(notebook)
    plan = ttk.Frame(notebook)
    deps = ttk.Frame(notebook)
    ratings = ttk.Frame(notebook)
    notes = ttk.Frame(notebook)

    notebook.add(overview, text="Overview")
    notebook.add(plan, text="Plan")
    notebook.add(deps, text="Dependencies")
    notebook.add(ratings, text="Ratings")
    notebook.add(notes, text="Notes")

    account = state.get("account", {})
    skills = state.get("skills", {})
    avg_skill = sum(skills.values()) / max(1, len(skills)) if skills else 0
    overview_text = (
        f"Name: {account.get('name', 'Unknown')}\n"
        f"Mode: {account.get('mode', 'main')}\n"
        f"Avg skill: {avg_skill:.1f}"
    )
    _add_label_block(overview, overview_text)

    plan_data = generate_plan(state)
    plan_lines = []
    for horizon in ["short", "mid", "long"]:
        plan_lines.append(f"{horizon.title()} horizon:")
        items = plan_data.get(horizon, [])
        if not items:
            plan_lines.append("- none")
        for item in items:
            plan_lines.append(f"- {item.get('task')} ({item.get('time')})")
            plan_lines.append(f"  why: {item.get('why')}")
    _add_label_block(plan, "\n".join(plan_lines))

    dep_lines = ["Dependency graph:"]
    graph = build_dependency_graph(state)
    for node, reqs in graph.items():
        dep_lines.append(f"- {node}: {', '.join(reqs)}")
    _add_label_block(deps, "\n".join(dep_lines))

    ratings_data, reasons = compute_ratings(state)
    rating_lines = []
    for k, v in ratings_data.items():
        rating_lines.append(f"{k.replace('_', ' ').title()}: {v}/100")
        for r in reasons.get(k, [])[:3]:
            rating_lines.append(f"- {r}")
    blockers = detect_bottlenecks(state)
    rating_lines.append("")
    rating_lines.append("Top blockers:")
    rating_lines.append("- " + ("\n- ".join(blockers) if blockers else "none"))
    _add_label_block(ratings, "\n".join(rating_lines))

    notes_box = tk.Text(notes, height=10, wrap="word")
    notes_box.insert("end", "Notes...\n")
    notes_box.pack(fill="both", expand=True, padx=12, pady=12)

    chat_frame = ttk.Frame(right)
    chat_frame.pack(fill="both", expand=True, padx=8, pady=8)
    ttk.Label(chat_frame, text="Chat").pack(anchor="w")

    chat_log = tk.Text(chat_frame, height=20, wrap="word", state="disabled")
    chat_log.pack(fill="both", expand=True, pady=(6, 6))

    entry_frame = ttk.Frame(chat_frame)
    entry_frame.pack(fill="x")
    entry = ttk.Entry(entry_frame)
    entry.pack(side="left", fill="x", expand=True)

    def append_message(sender, text):
        chat_log.configure(state="normal")
        chat_log.insert("end", f"{sender}: {text}\n")
        chat_log.configure(state="disabled")
        chat_log.see("end")

    def on_send():
        msg = entry.get().strip()
        if not msg:
            return
        entry.delete(0, "end")
        append_message("You", msg)
        append_message("System", "Placeholder response. Hook a model here.")

    send_btn = ttk.Button(entry_frame, text="Send", command=on_send)
    send_btn.pack(side="right", padx=(6, 0))

    entry.bind("<Return>", lambda _event: on_send())

    root.mainloop()


if __name__ == "__main__":
    run_app()
