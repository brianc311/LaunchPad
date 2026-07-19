# LUN Builder Section Header Counts

**Date:** 2026-07-19  
**Status:** Approved for implementation  
**Version target:** 1.6.35

## Problem

Hosts and LUN specs section titles do not show how many rows exist or how many are marked Done. When sections are collapsed, progress is invisible. LUN Plan already has a detailed summary bar; Hosts and LUN specs need a compact count in the heading itself.

## Goal

Show live progress in the Hosts and LUN specs section headings:

- `Hosts (3/5 done)`
- `LUN specs (2/4 done)`

Zero state: `Hosts (0/0 done)` and `LUN specs (0/0 done)`.

## Scope

**In scope**

- Update the `h2` text inside `#section-hosts` and `#section-luns` summaries during `render()`.
- Count Done from each row's existing `done` boolean.
- Counts update on add, remove, and Done checkbox changes (same render path as today).
- Bump `APP_VERSION` to `1.6.35`.

**Out of scope**

- Changing LUN Plan summary behavior (already shipped).
- Persisting any new fields (counts are derived).
- Adding totals bars under Hosts / LUN specs (heading text only).
- Command checklist header counts.

## Behavior

| Section | Numerator | Denominator |
|---------|-----------|-------------|
| Hosts | Hosts with `done === true` | `build.hosts.length` |
| LUN specs | LUN rows with `done === true` | `build.luns.length` |

Format is always `(done/total done)` including zeros. No pluralization changes beyond the existing static titles.

## UI

Keep existing summary structure and Add buttons. Only the `h2` text changes, e.g. wrap or replace the heading text with a span that `render()` updates:

```html
<summary class="section-head">
  <h2 id="hosts-heading">Hosts (0/0 done)</h2>
  <button ...>Add host</button>
</summary>
```

Style stays the same orange section heading; no new badge chrome.

## Testing

- Page smoke / string assertions that Hosts and LUN specs headings include the progress pattern after render helpers exist, or update existing page tests if they assert exact `Hosts` / `LUN specs` heading text.
- Manual check: add rows, toggle Done, collapse section — heading still shows counts.

## Non-goals

- Per-purpose breakdown (`root`, `sps`, …) on Hosts / LUN specs headings (that stays on LUN Plan).
- Mapping counts on these headings.
