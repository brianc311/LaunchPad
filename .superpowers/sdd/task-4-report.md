# Task 4 Report: HealthServer scan, cache, routes

**Status:** DONE
**Branch:** `feature/storage-inventory`
**Commit:** `a7ed3ab` — Wire Storage Inventory live scan, cache, and export APIs.

## Summary

Wired `launchpad/health_server.py` for Storage Inventory: live scan across SVC/HPE/DS8884 cards, fleet cache, xlsx export, page route, and the `/api/storage-inventory/*` API family. TDD flow: wrote the brief's 4 API tests (failing on missing methods) → implemented → all green, plus added optional HPE `showrcopy` fixture coverage flagged by the Task 1 reviewer.

## Files changed

| File | Change |
|------|--------|
| `launchpad/health_server.py` | Imports for `storage_inventory` / `storage_inventory_page`; `STORAGE_INVENTORY_PATH` route + `/api/storage-inventory/cache`, `/live`, `/export` handlers; `_storage_inventory_cache` field; per-vendor scan helpers (`_scan_storage_inventory_svc_card`, `_scan_storage_inventory_hpe_card`, `_scan_storage_inventory_ds_card`, `_parse_hpe_showsys_identity`, `_storage_inventory_health_issues`); `scan_storage_inventory_live`, `get_storage_inventory_cache`, `set_storage_inventory_cache`, `export_storage_inventory_bytes`, `open_storage_inventory`, `storage_inventory_url` |
| `tests/test_storage_inventory_api.py` | New — brief's 4 tests verbatim |
| `tests/test_storage_inventory.py` | Added 4 fixture tests for `parse_hpe_showrcopy_protection` (empty/not-configured/configured/unrecognized) per Task 1 reviewer note |

## Interfaces delivered

- `scan_storage_inventory_live(*, card_id=None) -> dict` — unlock-gated; iterates `is_system_connectivity_eligible` cards, branches SVC (`_lun_run_command` + `lssystem`/`lscloudcallhome`/`lsdnsserver`/`lsemailserver`/`lsrcrelationship`), HPE (`run_ssh_auth_hpe_commands` with `showsys`/`shownet`/`showrcopy`), DS8884 (`_lun_run_command` + `dscli showsp`/`lsnetworkport`); builds one row per card via `build_inventory_row`; total per-card failure falls back to an `unknown`-tuple row with `extra_errors=[str(exc)]`; sorts by site; caches and returns payload.
- `get_storage_inventory_cache` / `set_storage_inventory_cache` — same defensive-copy pattern as System Connectivity.
- `export_storage_inventory_bytes()` — raises `LookupError` when cache empty; otherwise returns `(xlsx_bytes, "LaunchPad_Storage_Inventory_<stamp>.xlsx", spreadsheet content-type)`.
- `open_storage_inventory()` / `storage_inventory_url` — mirrors `open_system_connectivity` / `system_connectivity_url`.
- Routes: `GET /storage-inventory` (HTML), `GET /api/storage-inventory/cache`, `GET /api/storage-inventory/live` (403 on lock, optional `?card_id=`), `GET /api/storage-inventory/export?format=xlsx&open=1`.

## Design notes / decisions

- **Data Protection cell**: SVC `lsrcrelationship` and HPE `showrcopy` return `(configured, status, details)`, but the "details" (relationship/group names) are deliberately dropped when building the row so the cell renders as a plain `"Yes"` / `"No — Not configured"`, matching Task 1/2/3 fixtures and the brief's `row["data_protection"].lower().startswith("yes")` assertion.
- **Identity fallback**: if a vendor path doesn't yield a model/serial (DS8884 has no identity command in v1; any parse comes back empty), falls back to `DEVICE_PROFILES` display name and the card's stored `serial_number`.
- **HPE identity parsing**: no existing `showsys` parser existed in the codebase, so added a small local `_parse_hpe_showsys_identity` (colon-line scan for `*model*`/`*serial*` tokens) — not exercised by the brief's pytest but harmless/conservative (returns empty strings on no match, falls back per above).
- **Health issues**: pulled via `analyze_health(card.name, card.command_results, card.metrics)["issues"]` when `command_results` exist (same call `HealthCard.to_api()` makes), else `[]`.
- **Total-card-failure semantics**: wrapped the whole per-card scan call in one try/except (not per-topic like System Connectivity) per the brief's literal wording — simpler and still produces one row with the card's name/host/ip and the exception message in `extra_errors`.

## Test results

```
python -m pytest tests/test_storage_inventory_api.py tests/test_storage_inventory.py tests/test_storage_inventory_page.py -v
10 passed... (9 in test_storage_inventory.py + 4 in api + 1 page = 14 total across the 3 files)

python -m pytest tests/ -q
934 passed, 1 failed (test_capacity_report_site.py::test_capacity_site_select_in_hero_actions —
pre-existing failure, confirmed via `git stash` unrelated to this change)
```

## Self-review

1. **Scope respected** — no `APP_VERSION` bump, no dashboard button added (both explicitly deferred to Task 5).
2. **Cache route** — System Connectivity has no analogous `/cache` GET endpoint (its page calls `/live` directly), so `/api/storage-inventory/cache` was modeled after the `/api/site-lookup/cache` pattern instead, matching the brief and the Task 3 page's `loadCache()` JS.
3. **Optional Task 1 follow-up done** — added 4 `parse_hpe_showrcopy_protection` fixture tests (empty/not-configured/configured/unrecognized) covering the previously-flagged untested heuristic surface.
4. **Not covered by tests**: HPE and DS8884 scan paths (only SVC happy path is in the brief's pytest); the per-card total-failure fallback branch; `open_storage_inventory`/`storage_inventory_url`. These follow established SysConn patterns closely and are low-risk, but a reviewer may want targeted HPE/DS fixture tests in a follow-up.
5. **Concern for reviewer**: the `_scan_storage_inventory_hpe_card` "smtp"/"call_home" cells are hardcoded `n/a` tuples rather than routed through `inventory_commands_for_profile`'s empty-list convention explicitly — behaviorally equivalent (empty command list per brief also means `n/a`) but worth confirming intent matches the brief's item 4.

## Next task

Task 5: bump `APP_VERSION`, add dashboard button/nav wiring.

## Review findings fix-up (post Task 4 review)

**Commit:** see `git log -1` on `feature/storage-inventory` after this note (new commit, not amended) — "Fix Storage Inventory health_issues key and export imports."

1. **`_storage_inventory_health_issues` wrong key** — was reading `analysis.get("issues")`, but `analyze_health` / `HealthCard.to_api` return the list under `"health_issues"`. Fixed to `analysis.get("health_issues")`. This was silently returning `[]` for every card since `analyze_health`'s payload never had an `"issues"` key.
2. **`scan_storage_inventory_live` total-card-failure fallback hardcoded `health_issues=[]`** — dropped any real health issues on the floor whenever the vendor scan raised. Fixed to call `self._storage_inventory_health_issues(card)` in the except branch (same helper the happy path uses) so cached health issues still surface in `issues`, alongside the exception text via `extra_errors=[err]`.
3. **Inline imports in the export route** — `TEMP_DIR` was redundantly re-imported inline even though it's already imported at module scope (line ~43); removed the redundant inline import. `open_exported_workbook` genuinely cannot be imported at module top: `capacity_export -> monitor -> health_server` is a real circular import (verified by reproducing `ImportError: cannot import name 'get_health_server' from partially initialized module 'launchpad.health_server'` when attempted). Kept `open_exported_workbook`'s inline import, added an explanatory comment matching the existing documented pattern used by the other export routes in this same file (per the `no-inline-imports` rule's documented-circular-dependency exception).
4. **Tests** — added `test_scan_storage_inventory_success_includes_health_issue` (happy-path row carries a monkeypatched `_storage_inventory_health_issues` message into `row["issues"]`) and `test_scan_storage_inventory_failure_retains_health_issue` (forces `_scan_storage_inventory_card` to raise; asserts the fallback row's `issues` contains both the cached health issue message and the exception text) in `tests/test_storage_inventory_api.py`.

### Test results

```
python -m pytest tests/test_storage_inventory_api.py tests/test_storage_inventory.py -v
15 passed
```

Also spot-checked the wider surface: `python -m pytest tests/ -k "health_server or capacity_export or storage_inventory" -q` → 109 passed.
