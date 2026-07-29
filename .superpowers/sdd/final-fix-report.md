# Final Fix Report — Firmware Catalog Seed

## Important: Seed load writes stale full-catalog snapshot

**Status:** Fixed  
**Date:** 2026-07-29

### Problem

`_firmware_catalog_load_seed` loaded the DB once, merged the seed, and saved that whole result when `inserted > 0`. It did **not** use `merge_catalog_for_admin_save` (the pattern Admin Save uses). Unsaved current-profile UI edits were discarded on seed insert, and concurrent auto-grow on other profiles could be clobbered by writing an older snapshot.

### Fix

`_firmware_catalog_load_seed` now mirrors Save:

1. Stash / read current profile UI list from `_firmware_catalog_map`
2. Reload fresh DB via `load_firmware_catalog(self.db)`
3. Build `base = merge_catalog_for_admin_save(db, current, ui_versions)`
4. `updated, inserted = merge_seed_into_catalog(base, recommended_firmware_seed())`
5. Save when `inserted > 0`
6. Always assign `_firmware_catalog_map` from `updated` and refresh the UI

### Tests

- `test_seed_load_uses_fresh_db_plus_current_ui_like_save` — UI overlay + DB auto-grow preserved; seed inserts; idempotent second merge
- `test_admin_seed_load_reloads_db_before_merge` — source wiring for `merge_catalog_for_admin_save` in the seed handler
- Re-ran: `tests/test_firmware_catalog_admin.py`, `tests/test_firmware_catalog_seed.py`, `tests/test_firmware_catalog.py`, `tests/test_firmware_catalog_auto_grow.py` → **20 passed**
