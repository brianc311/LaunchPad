# Final Fix Report — Firmware Catalog Auto-Grow

## Important: Admin Save clobber of auto-grown versions

**Status:** Fixed  
**Date:** 2026-07-29

### Problem

Admin’s in-memory `_firmware_catalog_map` was loaded once at Firmware catalog panel build. Live Refresh (auto-add on) wrote grown versions to the DB independently. A later Admin **Save** wrote the stale map and silently dropped those new versions.

### Fix

- Added `merge_catalog_for_admin_save(db_catalog, current_profile, current_versions)` in `launchpad/firmware_catalog.py`.
- `_firmware_catalog_save` now stashes the current profile’s UI list, reloads from `load_firmware_catalog(self.db)`, and saves `{**db_catalog, current_profile: ui_list}` so other profiles keep DB auto-grow while the current profile keeps unsaved edits.

### Tests

- `test_merge_catalog_for_admin_save_keeps_db_auto_grow_and_current_edits`
- `test_admin_save_reloads_db_before_write` (source wiring)
- Re-ran: `tests/test_firmware_catalog_admin.py`, `tests/test_firmware_catalog_auto_grow.py`, `tests/test_firmware_catalog_auto_grow_scan.py` → **13 passed**
