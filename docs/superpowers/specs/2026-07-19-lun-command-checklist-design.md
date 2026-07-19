# LUN Command Checklist Design

## Goal

Make dry-run output easy to paste into an external SSH session and easy to track while executing commands manually.

## User experience

After Preview / Dry-run, the existing collapsed CLI area becomes a command checklist. Warnings appear in a separate warning block and are never included in copied command text.

Commands are grouped into one row per volume. Each row contains:

- Volume name
- Create command
- All mapping commands for that volume
- **Copy** button that copies only that row's executable commands
- **Done** checkbox that turns the complete row green

A **Copy All Remaining** button copies executable commands from unfinished rows in their displayed order. This supports pasting a clean batch into an SSH session without `[ready]` labels, descriptions, or warnings.

The existing result modal may retain the detailed diagnostic text, while the checklist is the primary manual-execution interface.

## Grouping and data flow

The preview API continues returning ordered step objects and adds an explicit `volume_name` field to each generated step. The browser groups adjacent steps by that field:

1. A create step begins a volume group.
2. Following map steps for the same volume join that group.
3. Any step without a `volume_name` is shown as its own group so no command is lost.

The checklist uses `volume_name` for grouping and the step `cmd` values for copying. It does not parse labels or reconstruct storage commands.

## Completion persistence

Completed checklist rows are stored in the build as a map keyed by a stable command-group signature derived from the volume name and commands. A changed preview command therefore appears unfinished instead of inheriting an obsolete completion state.

Completion is informational only. It does not affect Preview, Run Create, command generation, exports, or validation.

## Safety and error handling

- Copy buttons never include warnings, labels, command output, or errors.
- Clipboard success/failure is reported next to the checklist.
- Copy All Remaining is disabled when no unfinished executable commands exist.
- Skipped and plan-only steps remain visibly labeled; only steps with a non-empty `cmd` are copyable.
- A new preview replaces the displayed checklist but preserves completion only for unchanged command-group signatures.

## Testing

- Verify create and map steps are grouped by volume in order.
- Verify row Copy contains only that row's commands.
- Verify Copy All Remaining excludes completed rows and non-command text.
- Verify Done state turns a row green and survives save/reload.
- Verify changed commands do not inherit stale completion.
- Verify warnings remain visible but are never copied.
- Run existing LUN Builder tests to ensure Preview/Run behavior is unchanged.
