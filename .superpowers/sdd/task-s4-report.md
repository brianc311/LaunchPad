# Task S4 Report: Tempe-style Site Lookup page

## Status: DONE

## Summary

Replaced the Site Lookup stub with a responsive, Tempe-adapted single-page interface.
The page loads registered cards, provides search suggestions, paints cached FC/pool
data on selection, and refreshes full inventory in place through the existing API.

## TDD Evidence

### RED

Command:
```powershell
py -3.13 -m pytest tests/test_site_lookup_page.py -v
```

Result: **2 failed** because the stub lacked the cards API, refresh wiring, tabs,
version placeholder, cache fields, empty states, and refresh status markers.

### GREEN

Command:
```powershell
py -3.13 -m pytest tests/test_site_lookup_page.py tests/test_site_lookup_api.py tests/test_site_lookup_data.py -v
```

Result: **14 passed in 0.92s**.

Additional verification:
- Embedded JavaScript passed `node --check`.
- IDE lint diagnostics reported no errors in the changed files.

## Changes

- `launchpad/site_lookup.py`
  - Added Tempe-derived dark layout, search suggestions, header statistics, tabs,
    result filtering, tables, and pool utilization cards.
  - Paints `fc_hosts`, `fc_mappings`, and `pools` from card cache immediately.
  - Posts selected card IDs to `/api/site-lookup/refresh`, disables refresh while
    in flight, and preserves rendered data if refresh fails.
  - Shows last-updated/source status and required empty-profile messages.
  - Includes `{{APP_VERSION}}`; no sample site dataset is embedded.
- `tests/test_site_lookup_page.py`
  - Added static page contract coverage for the route, APIs, tabs, cache fields,
    refresh behavior, empty states, version replacement marker, and sample-data ban.

## Commit

`2513415` — Add Tempe-style Site Lookup page with Live Refresh wiring.

## Concerns

- Page behavior is contract- and syntax-tested; no browser automation was run.
- `APP_VERSION` was intentionally not changed.

## Review Finding Fixes

- Consistency Groups rendering no longer depends on `device_profile`; API/cache
  rows, including Contingency Group fallback rows, remain visible on non-SVC cards.
  An empty result now renders `No rows`.
- Live Refresh captures the requested card ID and tracks in-flight refreshes by
  card. Selecting another card enables its refresh action, while stale success
  and error responses are ignored and cannot replace the selected card's paint.
- Added static JavaScript contract tests for both regressions. Browser automation
  was not added because the page script is embedded HTML and the existing page
  tests validate its generated contract.

### Review Fix TDD Evidence

- RED: `py -3.13 -m pytest tests/test_site_lookup_page.py -v` produced
  **2 failed, 2 passed** before the implementation changes.
- GREEN: `py -3.13 -m pytest tests/test_site_lookup_page.py
  tests/test_site_lookup_api.py tests/test_site_lookup_data.py -v` produced
  **16 passed in 1.05s**.
- IDE lint diagnostics reported no errors in the changed Python files.
