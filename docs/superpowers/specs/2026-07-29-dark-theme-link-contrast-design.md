# Dark-Theme Report Link Contrast

**Date:** 2026-07-29  
**Status:** Approved for implementation  
**App version target:** 1.6.79  
**Depends on:** HealthServer dark report pages (System Connectivity, FlashCopy CGs, siblings)  
**Approach:** Shared content-link CSS `a:not(.btn)` (Approach 1)  
**Base branch:** `feature/contingency-groups`

## Problem

Bare hyperlinks on dark HealthServer pages use the browser default blue, which has poor contrast on `--bg` / panel backgrounds. Operators cannot comfortably read links such as the Firmware **IBM FlashSystem software upgrade matrix** and FlashCopy CG summary **FlashCopy CGs** lede link.

## Goals

- Restyle in-content links (not `.btn` nav buttons) to a light readable blue on dark pages.
- Apply the same rule on every dark report page that shares the LaunchPad HealthServer token set and may contain bare `<a href>`.
- Bump `APP_VERSION` to **1.6.79**.

## Non-goals

- Call Home command fallback for older arrays (slice B).
- Firmware catalog seed auto-load / empty-catalog UX (slice C).
- Webpage Firmware catalog remove/manage (slice D).
- Redesigning `.btn` / `.btn.secondary` button appearance.
- Light-theme pages or CustomTkinter Admin UI.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Scope | All dark HealthServer report HTML using the shared dark tokens |
| Selector | `a:not(.btn)` (and `:hover`) so secondary nav buttons stay unchanged |
| Colors | Default `#9ec1ff`; hover `#c5d9ff`; underline with slight offset |
| Presentation | CSS only — no copy/URL changes |

## Behavior

Add (or merge) into each target page’s `<style>`:

```css
a:not(.btn) {
  color: #9ec1ff;
  text-decoration: underline;
  text-underline-offset: 2px;
}
a:not(.btn):hover { color: #c5d9ff; }
```

**Minimum pages (confirm in implementation by searching bare content links):**
- `launchpad/system_connectivity_page.py` (IBM upgrade matrix)
- `launchpad/fc_consistgrp.py` (FlashCopy CGs lede / empty hints)
- Other dark report modules under `launchpad/` that embed the same token set and unstyled `<a href>` (e.g. contingency-groups / host-volume / volume-find if they have content links)

`.btn` / `.btn.secondary` links must keep existing button colors.

## Tests

- Assert System Connectivity HTML includes the `a:not(.btn)` rule and the IBM matrix URL still present.
- Assert FlashCopy CG page HTML includes the same rule (or equivalent shared snippet).
- Version assert `1.6.79`.

## Follow-up (out of scope)

1. B — Call Home fallback when `lscloudcallhome` is invalid.  
2. C — Easier firmware catalog seed / empty-catalog messaging.  
3. D — Remove catalog versions from the Firmware webpage after upgrade.
