# How To Operate (<project_name>)

This project is a planning and analysis tool. It does not automate actions.

## Reference Order
1) `PERMISSIONS.md`
2) This file
3) `CAPABILITIES.md`
4) `DEPENDENCIES.md`
5) `METRICS.md`
6) `PROJECT_VISION.md`
7) `TICKETS.md` / `BUG_LOG.md`
8) `SIGNING_OFF.md`

## CLI Flow
- `python run_app.py status` to see the current snapshot.
- `python run_app.py plan` to generate a next-steps plan.
- `python run_app.py ratings` to view ratings.
- `python run_app.py deps` to view dependency graph.
- `python run_app.py risk` for risk and blockers.
- `python run_app.py gui` to open the GUI.

## Data Sources
- Local JSON in `data/` is the source of truth.

## Logging
- Record changes in `docs/LOGBOOK.md` with handle + date.
- Log bugs in `docs/BUG_LOG.md` before code edits.
