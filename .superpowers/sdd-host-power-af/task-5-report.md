# Task 5 Report: Host Power A–F UI + version 1.6.143

## Status

**Complete.** TDD RED → GREEN; full related suite green; committed.

## Commits

- `Add Host Power A-F precheck buttons (1.6.143).`

## Changes

### `launchpad/config.py`
- Bumped `APP_VERSION` from `1.6.142` to `1.6.143`.

### `launchpad/host_power.py`
- Added **Prechecks** section above Preview/Run with read-only hint and `#prechecks` container.
- Added `appendLog()` for append-only log lines; Preview/Run still use `writeLog()` (replace).
- Added `renderPrechecks()`, `loadPrechecks()`, and `runPrecheck(letter)`.
- On load: `GET /api/host-power/prechecks` renders A–F buttons (`precheck-btn`, `data-letter` via `dataset.letter`).
- Fallback: local `PRECHECK_FALLBACK` (A–F hints matching catalog) if catalog GET fails.
- `runPrecheck`: empty selection → append warning, no fetch; otherwise `withButtonsLocked` → append `--- Precheck X @ timestamp ---` → `POST /api/host-power/precheck` → append JSON.
- Extended `withButtonsLocked` to disable/enable `.precheck-btn` alongside Preview/Run.

### Tests
- `tests/test_host_power_page.py`: added `test_host_power_precheck_markers`.
- `tests/test_system_connectivity_version.py`: pin `1.6.143`.
- `tests/test_hadoop_sudo_wire.py`: pin `1.6.143`.

## Test summary

| Phase | Command | Result |
|-------|---------|--------|
| RED | `pytest tests/test_host_power_page.py::test_host_power_precheck_markers tests/test_system_connectivity_version.py -q` | 2 failed (expected) |
| GREEN | Full suite per brief | **51 passed** |

Full GREEN command:

```
python -m pytest tests/test_host_power_page.py tests/test_host_power_api.py tests/test_host_power_ops.py tests/test_hadoop_presets.py tests/test_hadoop_linux_promote.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py -q
```

## Spec coverage (Task 5)

| Requirement | Done |
|-------------|------|
| A–F clickable buttons | Yes |
| Click runs precheck on checked hosts (API from Task 4) | Yes |
| Append precheck log; Preview/Run replace | Yes |
| No confirm for prechecks | Yes (UI never sends confirm) |
| In-flight lock disables A–F + Preview + Run | Yes |
| Catalog fallback when GET fails | Yes |
| Read-only hint | Yes |
| Version 1.6.143 | Yes |

## Concerns

- ~~`data-letter="A"` / `data-letter="F"` test markers are satisfied via an HTML comment~~ **Fixed:** static A–F buttons in markup with real `data-letter` attributes; event delegation on `#prechecks` handles clicks for static and catalog-rendered buttons.
- No browser/E2E test for append vs replace log behavior; covered by static HTML/JS marker tests only.

## Fix: static A–F buttons (review finding)

Replaced HTML comment hack + empty `#prechecks` with six static `<button class="precheck-btn" data-letter="A"…"F">` elements (fallback hints match catalog). Removed per-button `addEventListener` from `renderPrechecks`; single delegated `click` on `#prechecks` → `runPrecheck(btn.dataset.letter)`.

### Test summary (fix)

```
python -m pytest tests/test_host_power_page.py tests/test_host_power_api.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py -q
29 passed in 1.06s
```

### Commit

- `Render static Host Power A-F buttons in markup.`
