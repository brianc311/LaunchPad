# Task 7 Report — Version bump 1.6.73

## Changes
- `launchpad/config.py`: `APP_VERSION = "1.6.73"`
- `tests/test_system_connectivity_version.py`: `test_app_version_1673` asserts `1.6.73`

## Tests
- Focused suite: **28 passed** in 0.62s
- Command: `python -m pytest tests/test_firmware_catalog.py tests/test_system_connectivity_firmware.py tests/test_system_connectivity_firmware_api.py tests/test_system_connectivity_export.py tests/test_system_connectivity_page.py tests/test_firmware_catalog_admin.py tests/test_system_connectivity_version.py tests/test_system_connectivity.py -q`

## Commit
- `9e25b35` — Bump LaunchPad to 1.6.73 for System Connectivity Firmware.

## Concerns
- None.

## Final-review Important fixes (post Task 7)

### Fixes
1. **Preserve parser Status for non-yes firmware rows** — `_enrich_scanned_firmware_row` now accepts parser `status` and passes it through to `enrich_firmware_row` (`error` overrides to `""error""`). SVC/HPE/DS scanners no longer discard `_status` / `_fw_status`. Auto current/behind/unknown still only when status empty and configured is yes.
2. **Normalize SVC `code_level` build suffix** — `normalize_svc_code_level` strips trailing `(build …)` so Current / catalog exact-match use release level (e.g. `8.6.0.0`).
3. **Optional** — removed unused `_firmware_list_buttons` from Admin Firmware catalog UI.

### Tests
- `python -m pytest tests/test_system_connectivity_firmware.py tests/test_system_connectivity_firmware_api.py tests/test_system_connectivity.py -q`
- **17 passed** in 0.69s
- Added: `test_ds_firmware_na_preserves_status`, `test_svc_normalized_current_matches_catalog`; updated `test_parse_svc_firmware_code_level` expected Current.

### Version
- Unchanged: `APP_VERSION` remains **1.6.73**
