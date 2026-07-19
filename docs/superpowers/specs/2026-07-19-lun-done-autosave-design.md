# LUN Builder Done Auto-Save

**Date:** 2026-07-19  
**Status:** Approved for implementation  
**Version target:** 1.6.37

## Problem

Done checkboxes for LUN Plan (`plan_done`), Hosts/LUN specs (`done`), and the command checklist (`command_done`) update in-memory state only. They do not write to `localStorage` or the LaunchPad API. On page refresh, `load()` replaces the working copy with the last saved server (or browser) build, so green rows and checkmarks disappear.

## Goal

Persist every Done toggle immediately enough that a page refresh keeps the same completion state, without requiring a separate Save click for progress tracking.

## Behavior

When the user toggles any of:

- LUN Plan Done
- Hosts or LUN specs Done
- Command checklist Done

the builder must:

1. Update the existing in-memory fields as today (including `syncCompletionFromPlan` after LUN Plan changes).
2. Call `saveLocal()` immediately so browser-only mode survives refresh.
3. If LaunchPad persistence is unlocked (`persisted === true`) and the active build has a non-empty `id` and is not a template, schedule a debounced server save (~400ms) of that build via the existing `POST /api/lun-builds` path used by Save.
4. After a successful server save, refresh the in-memory `builds` list from the response and call `saveLocal()` again, matching current Save behavior.
5. On server failure, keep the local state and show a short status that completion was saved locally only.

Debouncing applies only to the server write. Local writes are immediate.

## Non-goals

- Changing the Hosts / LUN specs “all volumes Done” completion rule.
- Showing partial volume progress in section headings.
- Auto-saving non-Done field edits (purpose, size, hosts, etc.) — those still require Save.
- Changing Preview / Run gating.
- New persisted schema fields.

## UI / status

Keep checkbox UX unchanged. Optional quiet status text on successful auto-save is allowed (`Completion saved.` / local-only message) but must not open modals or interrupt clicking.

## Testing

- Page contracts assert a helper such as `persistCompletionState` / `scheduleCompletionSave` exists and is called from the Done handlers (LUN Plan, host/lun `done`, command checklist).
- Prefer an executable check that the LUN Plan handler calls `saveLocal` (or the shared persist helper) after updating `plan_done`.
- Full `tests` suite must pass.
- Manual: check LUN Plan Done → refresh → checkmarks and green rows remain when unlocked and the build was already saved once with an id.

## Version

Bump `APP_VERSION` to `1.6.37`.
