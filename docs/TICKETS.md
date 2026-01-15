# Ticket Log
## Foundations
- [ ] Define end-state goals and success criteria (what "agent plays" means). (OSRS: `docs/END_STATE.md`)
- [ ] Add project overview + constraints in `docs/PROJECT_VISION.md`. (OSRS: `docs/PROJECT_VISION.md`)
- [ ] Maintain decision trace + behavior policy docs (short and practical). (OSRS: `docs/MODEL_OUTPUT_SCHEMA.md`, `docs/DECISION_TRACE_SCHEMA.md`, `src/model_output.py::validate_decision_trace`)
- [ ] Establish safe-stop rules + manual takeover procedure. (OSRS: `docs/PERMISSIONS.md`, `src/actions.py::policy_check`)

## Agent Core Roadmap Alignment
- [x] Integrate agent_core capture + input with fallbacks. (agent_core v0.1.1)
- [ ] Wire agent_core color detection for UI signals (menus, HP bar, Pikachu). (agent_core v0.1.1)
- [ ] Expose agent_core version/availability in CLI status output. (agent_core v0.1.1)
- [ ] Add timing profile hooks for humanized input. (agent_core v0.2.0)
- [ ] Add OCR-backed UI state detection. (agent_core v0.1.1)
- [ ] Add template matching for sprites/icons. (agent_core v0.3.0)

## Emulator + Bridge Reliability
- [ ] Confirm BizHawk core + Lua bridge reliability (Lua console running + JSON updates every frame). (OSRS: `src/perception.py::capture_frame`)
- [ ] Add bridge health heartbeat (timestamp + status file). (OSRS: `src/actions.py::apply_interrupt_pause`)
- [ ] Add automatic retry/reload instructions for bridge failure. (OSRS: `src/actions.py::execute_with_retry`, `src/actions.py::default_backoff_ms`)
- [ ] Add stale-bridge recovery: detect frozen `emulator_state.json` and prompt to reload Lua script or auto-retry. (Use `tools/bizhawk/bridge_status.txt` + timestamp delta)
- [ ] Normalize window capture to game viewport bounds (avoid menu bar). (OSRS: `src/perception.py::capture_frame`, `src/perception.py::_get_window_bounds`)
- [x] Add active window verification before actions. (OSRS: `src/perception.py::is_window_focused`, `src/actions.py::focus_recovery_needed`)
- [x] Confirm emulator is running/unpaused before input (detect pause). (OSRS: `src/actions.py::pre_action_gate`, `src/actions.py::post_action_verify`)
## Current Findings (2026-01-15)
- [ ] Bridge not running: `data/emulator_state.json` timestamp frozen at `2026-01-15T03:03:31Z`.
- [ ] BizHawk window focus false during smoke test; inputs likely ignored until focus restored.

## State Perception (No Hand-Holding)
- [x] Build state delta tracker (map/pos/direction changes). (OSRS: `src/runelite_data.py::get_player_position`, `src/runelite_data.py::get_tutorial_phase`)
- [x] Detect "stuck" state (no movement after N actions). (OSRS: `src/interrupts.py::should_pause_on_unexpected_ui`, `src/actions.py::detect_ui_change`)
- [ ] Detect battle/menu/dialog states from memory flags. (OSRS: `src/ui_state.py::extract_hover_text`, `src/ui_detector.py::detect_ui`)
- [ ] Add screen-based fallback state (screenshot hash + OCR). (OSRS: `src/ocr.py::run_ocr`, `src/text_matcher.py::match_text`)
- [x] Add input-to-outcome correlation (action result logging). (OSRS: `src/action_context.py::log_action_context`, `src/actions.py::post_action_verify`)
- [ ] Add "scene confidence" score (memory + screen agree). (OSRS: `src/actions.py::requires_confidence_gate`)

## Action Layer + Human-Like Timing
- [ ] Port minimal action policy from AgentOSRS (spacing, retries, focus checks). (OSRS: `src/actions.py::execute_with_policy`, `src/action_context.py::ActionContext`)
- [x] Add action gating (only send input when emulation is running). (OSRS: `src/actions.py::pre_action_gate`, `src/actions.py::post_action_verify`)
- [ ] Add timing profiles for exploration vs. menu navigation. (OSRS: `src/timing.py::sample_reaction_ms`, `src/rhythm.py::sample_burst_actions`, `src/pacing.py::adjusted_action_delay`)
- [x] Add backoff strategy when no state change occurs. (OSRS: `src/actions.py::execute_with_retry`, `src/actions.py::default_backoff_ms`)
- [x] Add input focus recovery (refocus before retry). (OSRS: `src/actions.py::build_focus_recovery_intent`, `src/perception.py::focus_window`)

## Learning Loop (Human-Like)
- [ ] Short-term memory buffer (recent actions + outcomes). (OSRS: `src/decision_consume.py::latest_payload`, `src/model_output.py::log_decision`)
- [ ] Long-term notes summarizer (periodic compress to `data/agent_notes.md`). (OSRS: `docs/LOGBOOK.md`)
- [ ] Curiosity heuristic (prefer actions that change state). (OSRS: `src/actions.py::detect_ui_change`)
- [ ] Simple goal-free exploration loop (no hard-coded routes). (OSRS: `src/agent_loop.py::run_loop`)
- [ ] Local "question list" generator (unknowns to investigate). (OSRS: `docs/QUESTION_LOG.md`)

## Logging + Telemetry
- [x] Standardize log schema (action, state before/after, result). (OSRS: `docs/AUDIT_LOG_SPEC.md`, `src/action_context.py::log_action_context`)
- [x] Record non-battle OCR text to `logs/ocr_text.jsonl`. (agent_core v0.1.1)
- [ ] Snapshot cadence policy + cleanup (retain last N). (OSRS: `src/agent_runner.py::save_snapshot`)
- [ ] Add run metadata file (session start/end, seed, emulator build). (OSRS: `src/randomness.py::seed_session`, `docs/LOGBOOK.md`)
- [ ] Add replay viewer for action/state logs. (OSRS: `scripts/replay_viewer.py`)
- [ ] Add "emulator health" log (bridge heartbeat + focus). (OSRS: `src/actions.py::focus_recovery_needed`)

## Minimal UX / Controls
- [ ] Add CLI flags for exploration intensity + max runtime. (OSRS: `src/app_cli.py::_sleep_ms`)
- [ ] Add pause/resume hotkeys for the agent loop. (OSRS: `src/interrupts.py::should_pause_on_unexpected_ui`)
- [ ] Add safe-stop if window focus is lost. (OSRS: `src/perception.py::is_window_focused`, `src/actions.py::focus_recovery_needed`)
- [ ] Add "resume from notes" hint in CLI output. (OSRS: `docs/LOGBOOK.md`)
- [ ] Add save/load state workflow for BizHawk (script + CLI). (store in `data/`, expose CLI flags)

## Tests / Validation
- [ ] Smoke test: focus + screenshot + memory read. (OSRS: `scripts/validate_template.ps1`, `src/perception.py::capture_frame`)
- [ ] Smoke test: verify input changes memory state. (OSRS: `src/actions.py::post_action_verify`)
- [ ] Regression: emulator state log and snapshots generated. (OSRS: `scripts/replay_viewer.py`)
- [ ] Manual checklist for "gameplay start" readiness. (OSRS: `docs/HOW_TO_OPERATE.md`, `docs/LOG_CHECKLIST.md`)
