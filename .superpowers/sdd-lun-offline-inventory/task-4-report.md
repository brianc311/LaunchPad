# Task 4 Report: Version bump + smoke

**Status:** DONE  
**Commit:** `aff4f86` — Bump LaunchPad to 1.6.90 for LUN offline inventory.

## Version Bump

| File | Change |
|------|--------|
| `launchpad/config.py` | `APP_VERSION = "1.6.90"` (was `1.6.89`) |

No version assertion tests referenced `1.6.89` or `APP_VERSION`; no test updates required.

## Smoke Tests

```powershell
python -m pytest tests/test_lun_offline_inventory.py tests/test_lun_offline_inventory_api.py tests/test_lun_builder_offline_ui.py -v
# 12 passed in 0.67s

python -c "from launchpad.config import APP_VERSION; assert APP_VERSION == '1.6.90'"
# OK
```

## Spec Coverage

- Version 1.6.90 requirement satisfied.
- Sync/Pull/Export paths unchanged (no edits in this task).

## Concerns

None.

---

## Task 4 Important Finding Fix

**Status:** DONE  
**Issue:** `tests/test_system_connectivity_version.py` still asserted `APP_VERSION == "1.6.88"` and used function name `test_app_version_1688`.

**Fix:**
- Renamed `test_app_version_1688` → `test_app_version_1690`
- Updated assertion to `APP_VERSION == "1.6.90"`

**Tests:**

```powershell
python -m pytest tests/test_system_connectivity_version.py tests/test_lun_offline_inventory.py tests/test_lun_offline_inventory_api.py tests/test_lun_builder_offline_ui.py -v
# 13 passed in 0.66s
```
