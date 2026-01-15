# End State (<project_name>)

This describes the target outcome for the <project_name> project.

## Product Scope
- One local-first system with optional front-ends:
  - Optional overlay/plugin (if applicable).
  - Optional GUI for dashboards and notes.
- No automation; guidance only.

## Data Model (Authoritative)
- `data/state.json` is the source of truth and is versioned.
- Required state sections (example):
  - account: name, mode, members, stats, resources.
  - skills: relevant domain skills (levels only).
  - goals: short, mid, long.
- Reference data:
  - dependencies, unlocks, and method tables as needed.

## Ratings and Scoring (Explainable)
- Ratings are 0-100 with 3+ explicit reasons each.
- Core ratings:
  - Combat Readiness, Quest Readiness, Skilling Readiness, Money Pathing.
- Secondary ratings:
  - Risk, Efficiency, Bottlenecks, Unlock Density.
- Delta reporting:
  - Show which missing items/levels most improve score.
- Time estimates:
  - Each plan item has a time range and dependency list.

## Planning Engine
- Generate a 3-horizon plan:
  - Short: next 1-2 sessions.
  - Mid: 1-2 weeks.
  - Long: 1-2 months.
- Plan output includes:
  - Why this step matters.
  - Required prereqs.
  - Estimated time.
  - Alternatives (faster, cheaper, safer).
- Dependency tree:
  - Shortest unlock path + optional paths.

## GUI (Optional)
- Split view (2:1 ratio) recommended for dashboard + chat.
- Tabs and panels are domain-specific.

## Optional Overlay (Local Plugin)
- On-screen overlay panel:
  - Top plan steps, ratings, blockers.
- Reads local snapshot only.

## Distribution
- Local install docs for GUI and optional plugin.
- Versioned releases and changelog template.



