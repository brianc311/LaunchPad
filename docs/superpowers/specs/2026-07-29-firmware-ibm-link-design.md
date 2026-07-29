# Firmware Tab IBM Upgrade Matrix Link

**Date:** 2026-07-29  
**Status:** Approved for implementation  
**App version target:** 1.6.77  
**Depends on:** System Connectivity Firmware tab (1.6.73+)  
**Approach:** Hint-line link on Firmware panel only (Approach 1)  
**Base branch:** `feature/contingency-groups`

## Problem

Operators reviewing Firmware on System Connectivity have no in-app pointer to IBM’s published FlashSystem / Spectrum Virtualize software upgrade matrix.

## Goals

- On System Connectivity → **Firmware**, show a clear link to the IBM upgrade matrix.
- Open in a new browser tab.
- Bump `APP_VERSION` to **1.6.77**.

## Non-goals

- Changing Firmware collectors, catalogs, Latest / Versions behind math.
- Excel / CSV export changes.
- Admin UI changes.
- Per-site Available Update Versions (slice A — later).
- License Key tab (slice C — later).
- HPE or DS8884 vendor-specific upgrade links (this URL is IBM-only).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Placement | Firmware panel only (not hero / all tabs) |
| Presentation | Hint-line HTML link under the Firmware heading |
| Link text | `IBM FlashSystem software upgrade matrix` |
| URL | `https://www.ibm.com/support/pages/node/5692850` |
| Open behavior | `target="_blank"` with `rel="noopener noreferrer"` |

## Behavior

Keep the existing Firmware hint about the Admin catalog. Add a second hint line (or equivalent adjacent paragraph) containing only the IBM link as described above.

No live-scan or unlock changes. Link is static HTML in `system_connectivity_page.py`.

## Tests

- Assert Firmware panel HTML contains the exact URL and link text (or URL + `target="_blank"`).
- Bump version assertion to `1.6.77`.

## Follow-up (out of scope)

1. License Key tab — live date / time / key generation date.
2. Per-site Available Update Versions catalogs.
