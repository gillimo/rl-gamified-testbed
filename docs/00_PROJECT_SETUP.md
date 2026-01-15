# 00_PROJECT_SETUP

Read this first.

## Start a new project
1) Unzip the template.
2) Rename the folder to your project name.
3) Run bootstrap:
   - `scripts\bootstrap.ps1 -ProjectName <name> -Domain <domain>`
4) Validate:
   - `scripts\validate_template.ps1`
5) Open `docs/DOCS_INDEX.md` and follow the reference order.

## First actions
- Add your handle to `docs/LOGBOOK.md`.
- Review `docs/TICKETS.md` and set your first tasks.
- Read `docs/HOUSEKEEPING.md` - keep the project clean from day one.
- Update `FUNCTION_INDEX.md` as you add code.

## Token Efficiency
AI assistants burn tokens reading files. Keep docs minimal:
- Archive completed tickets immediately
- Delete old logs after each session
- Keep /docs folder small (<10 files)
- Use FUNCTION_INDEX.md so AI can find code without searching

## Notes
- Keep work within the project folder.
- Do not store secrets in the repo.
- Morality: This project prioritizes learning and growth. We are trusted actors and will not use outputs for harmful or unethical purposes.
