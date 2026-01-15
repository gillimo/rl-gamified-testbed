# Housekeeping Guide

## Why Housekeeping Matters

AI assistants consume tokens for every file they read. Large projects with excessive docs, logs, and completed tickets burn context and cost money. Regular cleanup keeps projects efficient.

## Cleanup Schedule

### After Each Session
- Delete old log files (keep only recent 2-3 if needed)
- Delete `__pycache__`, `build/`, `dist/` folders

### Weekly
- Archive completed tickets (move to archive or delete from TICKETS.md)
- Archive resolved bugs from BUG_LOG.md
- Review docs - archive anything not actively referenced

### Before Handoff
- Run full cleanup
- Ensure FUNCTION_INDEX.md is up to date
- Verify only essential docs remain in /docs

## What to Keep in /docs (Essential)
- `DOCS_INDEX.md` - navigation
- `FUNCTION_INDEX.md` - code reference
- `METRICS.md` - formulas/scoring reference
- `TICKETS.md` - open items only
- `HOUSEKEEPING.md` - this file

## What to Archive
- Completed tickets
- Old state snapshots (CURRENT_STATE_*.md)
- Resolved bug reports
- Old handoff notes
- Historical logbooks
- Checklists that are done

## Folder Structure Goals
```
project/
├── src/              # Source code
├── data/             # Data files
├── docs/             # MINIMAL - only essential docs
├── archive/          # Old docs, completed work
├── logs/             # Keep empty or minimal
└── README.md
```

## FUNCTION_INDEX.md

Every project should have a `docs/FUNCTION_INDEX.md` that maps:
- Function name → file → line number → purpose
- Key constants and their locations
- Entry points

This lets AI assistants find code without searching randomly.

## Anti-Patterns to Avoid
- Keeping all historical tickets visible
- Multiple "CURRENT_STATE" dated files
- Verbose bug logs for fixed issues
- Duplicate documentation
- Logs older than a week
- Build artifacts in repo

## Token Cost Reference
- Each file read costs tokens
- Large JSON caches (10MB+) should stay but not be read
- Aim for <10 active docs in /docs folder
- Archive folder contents are not read unless requested

---
Last updated: 2026-01-11
