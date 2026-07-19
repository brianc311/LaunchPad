# LUN Plan Completion Synchronization

**Date:** 2026-07-19  
**Status:** Approved for implementation  
**Version target:** 1.6.36

## Problem

Completion is currently tracked independently:

- Hosts use `host.done`.
- LUN specs use `lun.done`.
- Expanded LUN Plan rows use `build.plan_done[volume_name]`.

Marking an expanded volume Done in LUN Plan therefore does not turn its
source LUN spec or mapped Hosts green, and the collapsed section progress
counts do not reflect work completed from LUN Plan.

## Goal

Make LUN Plan the upward synchronization trigger for completion:

- A LUN spec is Done when all of its expanded volumes are Done.
- A Host is Done when all expanded volumes mapped to it are Done.
- Host and LUN specs rows, checkboxes, and collapsed heading counts update
  immediately after a LUN Plan checkbox changes.

## Behavior

### LUN specs

For every LUN spec:

1. Expand its volume names with the existing `expandLunBatch(lun)` helper.
2. Set `lun.done = true` only when every expanded name is present and true in
   `build.plan_done`.
3. Set `lun.done = false` when any expanded volume is not Done.

The existing expansion helper always produces at least one volume, so an
empty-list completion case is not needed.

### Hosts

For every Host with a non-empty `lpar_name`:

1. Find every LUN spec whose `host_names` contains that LPAR name.
2. Compare names after trimming whitespace and normalizing case, so
   `PCONSPS3` and `pconsps3` refer to the same host.
3. Expand all matching LUN specs into volume names.
4. If at least one expanded volume is mapped to the Host, set `host.done`
   to whether every mapped volume is true in `build.plan_done`.
5. If no expanded volumes are mapped to the Host, leave its existing manual
   `done` value unchanged.

### LUN Plan checkbox flow

When a LUN Plan checkbox changes:

1. Add or remove its volume name in `build.plan_done` as today.
2. Recalculate all LUN spec and mapped Host `done` values.
3. Re-render the builder.

The re-render updates:

- LUN Plan row green state.
- LUN specs row green state and Done checkbox.
- Hosts row green state and Done checkbox.
- `Hosts (N/M done)` and `LUN specs (N/M done)` headings.
- Existing LUN Plan summary.

Unchecking a LUN Plan row reverses completion for every affected LUN spec and
Host whose full set is no longer complete.

## Manual completion interaction

Hosts and LUN specs Done checkboxes remain available for manual use.

The next LUN Plan checkbox change recalculates all LUN specs and all Hosts
that have mapped volumes. This may replace a manual Done value with the state
derived from LUN Plan. Unmapped Hosts retain their manual state.

This synchronization is intentionally one-way:

- LUN Plan changes update Hosts and LUN specs.
- Manually changing a Host or LUN spec does not mark LUN Plan volumes Done.

This avoids a Host checkbox unexpectedly completing many volumes across
multiple LUN specs.

## Data and persistence

No new fields are required. Synchronization uses and updates the existing:

- `build.plan_done`
- `build.luns[].done`
- `build.hosts[].done`

Existing Save behavior persists all three states.

## Implementation boundary

Add a focused JavaScript helper in `launchpad/lun_builder.py`, for example:

```javascript
function syncCompletionFromPlan(build) {
  // Derive LUN spec and mapped Host completion from build.plan_done.
}
```

Call it only from the LUN Plan checkbox change handler before `render()`.
Do not call it during every render, because loading or editing a build should
not erase manual completion values until the user changes LUN Plan.

## Testing

Add focused, executable tests for the synchronization rules rather than only
checking that helper names appear in the HTML:

- All expanded volumes Done marks the source LUN spec Done.
- One incomplete expanded volume keeps the source LUN spec incomplete.
- All mapped volumes Done marks a Host Done.
- One incomplete mapped volume keeps a Host incomplete.
- Host-name matching is trimmed and case-insensitive.
- An unmapped Host retains its manual Done value.
- Unchecking a plan row reverses affected completion.
- The plan change handler synchronizes before rendering.

Run the complete `tests` suite after implementation.

## Out of scope

- Downward synchronization from Hosts or LUN specs to LUN Plan.
- Disabling the existing manual Done checkboxes.
- Changing command checklist completion.
- Changing volume naming, mapping generation, or LUN Plan summary counts.
- Adding new persisted completion fields.
