# Dashboard Alert Popups Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persisted **Alert popups** switch on the connection dashboard so operators can stop floating critical windows (and their beep) without hiding on-card overlays, shipping as **1.6.185**.

**Architecture:** A small default-On helper reads `alert_popups_enabled` from LaunchPad settings. The dashboard toggle saves `"true"` / `"false"`. When Off, health-alert polling and card overlays still run; the desktop `HealthAlertDialog` and `play_health_alert_beep` are skipped, and an already-open dialog is closed.

**Tech Stack:** Python, CustomTkinter, existing `Database.get_setting` / `set_setting`, pytest.

**Spec:** `docs/superpowers/specs/2026-08-19-dashboard-alert-popups-toggle-design.md`

## Global Constraints

- APP_VERSION bump to **1.6.185** only in the final version task. Do not bump in Tasks 1–2.
- Hide only the floating desktop critical window and its beep. On-card overlays stay.
- Health Dashboard browser modals and the browser “show alerts” checkbox are unchanged.
- Admin per-card Alerts (`alarm_muted` / `set_alarm`) still works independently. Do not mute all sites via `set_alarm`.
- Switch label exactly **Alert popups**. Placement: toggle row after Mouse jiggler, before the selection count.
- Default **On**. Missing/empty setting means On. Only the persisted string `false` turns popups off.
- Setting key: `alert_popups_enabled` with values `"true"` / `"false"`.
- Do not change Monitor SSH, stats collection, or Stats Snapshot windows.
- Place imports at the top of modules (no inline imports).
- Windows PowerShell commits (`git commit -m "..."`); commit at each task commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch, `LaunchPad-Install/`, or install zips.
- Work on branch `feature/dashboard-alert-popups-toggle` (already exists from the spec commit). Do not start from `main` without that spec.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/health_alert_state.py` | `SETTING_ALERT_POPUPS`, `desktop_alert_popups_enabled` |
| `tests/test_health_alert_state.py` | Default On / Off helper tests |
| `launchpad/ui/dashboard_view.py` | Switch, persist, skip dialog + beep, close dialog on Off |
| `tests/test_dashboard_health_alerts.py` | Source contracts for switch and gates |
| `launchpad/config.py` + version pins | **1.6.185** (Task 3 only) |

---

### Task 1: Default-On alert-popups setting helper

**Files:**
- Modify: `launchpad/health_alert_state.py`
- Modify: `tests/test_health_alert_state.py`

**Interfaces:**
- Consumes: none (pure string helper)
- Produces:
  - `SETTING_ALERT_POPUPS = "alert_popups_enabled"`
  - `desktop_alert_popups_enabled(value: str | None) -> bool` — `False` only when the stripped lowercased value is `"false"`; missing, `""`, `"true"`, and any other value → `True`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_health_alert_state.py` (keep existing imports; add the new names):

```python
from launchpad.health_alert_state import (
    SETTING_ALERT_POPUPS,
    desktop_alert_popups_enabled,
)


def test_desktop_alert_popups_enabled_defaults_on():
    assert SETTING_ALERT_POPUPS == "alert_popups_enabled"
    assert desktop_alert_popups_enabled(None) is True
    assert desktop_alert_popups_enabled("") is True
    assert desktop_alert_popups_enabled("true") is True
    assert desktop_alert_popups_enabled("TRUE") is True
    assert desktop_alert_popups_enabled("false") is False
    assert desktop_alert_popups_enabled("FALSE") is False
    assert desktop_alert_popups_enabled(" false ") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_health_alert_state.py::test_desktop_alert_popups_enabled_defaults_on -v`

Expected: FAIL (import error or `desktop_alert_popups_enabled` missing)

- [ ] **Step 3: Write minimal implementation**

In `launchpad/health_alert_state.py`, next to `HEALTH_ALERT_SETTING`:

```python
SETTING_ALERT_POPUPS = "alert_popups_enabled"


def desktop_alert_popups_enabled(value: str | None) -> bool:
    """Return whether desktop critical popups should open.

    Missing or empty setting means On. Only the string ``false`` (any case,
    surrounding whitespace ignored) turns popups off.
    """
    return str(value or "").strip().lower() != "false"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_health_alert_state.py::test_desktop_alert_popups_enabled_defaults_on tests/test_health_alert_state.py -q`

Expected: PASS (new test plus existing health_alert_state tests)

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_alert_state.py tests/test_health_alert_state.py
git commit -m "Add default-On helper for desktop Alert popups setting."
```

---

### Task 2: Dashboard switch, skip dialog and beep when Off

**Files:**
- Modify: `launchpad/ui/dashboard_view.py`
- Modify: `tests/test_dashboard_health_alerts.py`

**Interfaces:**
- Consumes: `SETTING_ALERT_POPUPS`, `desktop_alert_popups_enabled` from `launchpad.health_alert_state`
- Produces:
  - Dashboard field `_alert_popups_enabled: bool` loaded from `db.get_setting(SETTING_ALERT_POPUPS, "")`
  - Switch `self.alert_popups_switch` with text `"Alert popups"`, grid column 3; selection label moves to column 4; `toggles.grid_columnconfigure(4, weight=1)`
  - `_toggle_alert_popups()` saves `"true"` / `"false"` and calls `_force_close_health_alert_dialog()` when turning Off
  - `_apply_health_alert_payload` still calls `_sync_health_alert_overlays`; skips `play_health_alert_beep` and `_show_next_health_alert` when `_alert_popups_enabled` is False

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_dashboard_health_alerts.py`:

```python
def test_dashboard_has_alert_popups_toggle():
    assert 'text="Alert popups"' in DASH
    assert "SETTING_ALERT_POPUPS" in DASH
    assert "desktop_alert_popups_enabled" in DASH
    assert "_toggle_alert_popups" in DASH
    assert "alert_popups_switch" in DASH
    assert "grid_columnconfigure(4, weight=1)" in DASH


def test_dashboard_skips_dialog_and_beep_when_alert_popups_off():
    apply = DASH.split("    def _apply_health_alert_payload", 1)[1].split(
        "    def _health_alert_group_key", 1
    )[0]
    assert "self._alert_popups_enabled" in apply
    assert "play_health_alert_beep" in apply
    assert "_sync_health_alert_overlays" in apply
    assert "_show_next_health_alert" in apply
    toggle = DASH.split("    def _toggle_alert_popups", 1)[1].split("    def ", 1)[0]
    assert "_force_close_health_alert_dialog" in toggle
    assert 'set_setting(SETTING_ALERT_POPUPS, "true"' in DASH or (
        'SETTING_ALERT_POPUPS, "true"' in toggle
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dashboard_health_alerts.py::test_dashboard_has_alert_popups_toggle tests/test_dashboard_health_alerts.py::test_dashboard_skips_dialog_and_beep_when_alert_popups_off -v`

Expected: FAIL (missing `"Alert popups"` / `_toggle_alert_popups`)

- [ ] **Step 3: Write minimal implementation**

In `launchpad/ui/dashboard_view.py` imports, add `SETTING_ALERT_POPUPS` and `desktop_alert_popups_enabled` to the existing `health_alert_state` import (today it only imports `same_health_alert_card_id`).

In `DashboardView.__init__`, after `_mouse_jiggler_enabled`:

```python
        self._alert_popups_enabled = desktop_alert_popups_enabled(
            self.db.get_setting(SETTING_ALERT_POPUPS, "")
        )
```

In `_build_filters` toggle row, after `mouse_jiggler_switch` (column 2) and **before** `selection_label`:

- Change `toggles.grid_columnconfigure(3, weight=1)` to `toggles.grid_columnconfigure(4, weight=1)`
- Add:

```python
        self.alert_popups_switch = ctk.CTkSwitch(
            toggles,
            text="Alert popups",
            command=self._toggle_alert_popups,
        )
        if self._alert_popups_enabled:
            self.alert_popups_switch.select()
        self.alert_popups_switch.grid(row=0, column=3, padx=(0, 12))
```

- Move `selection_label` to `column=4` (keep `sticky="e"`).

Add method next to `_toggle_mouse_jiggler`:

```python
    def _toggle_alert_popups(self) -> None:
        enabled = bool(self.alert_popups_switch.get())
        self._alert_popups_enabled = enabled
        self.db.set_setting(SETTING_ALERT_POPUPS, "true" if enabled else "false")
        if not enabled:
            self._force_close_health_alert_dialog()
```

In `_apply_health_alert_payload`, wrap the beep loop so it only runs when popups are enabled, and skip showing the dialog when Off. Keep overlay sync always:

```python
        self._health_alert_cards_meta = payload.get("cards") or {}
        self._sync_health_alarm_muted_indicators()
        groups = group_health_alerts(alerts)
        self._sync_health_alert_overlays(groups)

        if not self._alert_popups_enabled:
            return

        if self._health_alert_dialog is not None:
            return

        self._health_alert_queue = groups
        self._health_alert_queue_index = 0
        self._show_next_health_alert()
```

Move the existing beep-on-new-fingerprint loop to **after** the `if not self._alert_popups_enabled: return` check, **or** guard it with `if self._alert_popups_enabled:` so Off never calls `play_health_alert_beep`. Overlays must still run before that return.

Keep `_health_alert_beeped` pruning (`self._health_alert_beeped &= active_fingerprints`) even when Off so turning the switch back On does not replay stale beeps incorrectly — prune still happens; skip only new beeps and dialog open.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dashboard_health_alerts.py -q`

Expected: PASS (including existing overlay/dialog contracts)

- [ ] **Step 5: Commit**

```powershell
git add launchpad/ui/dashboard_view.py tests/test_dashboard_health_alerts.py
git commit -m "Add dashboard Alert popups switch that skips the floating critical window."
```

---

### Task 3: Bump APP_VERSION to 1.6.185

**Files:**
- Modify: `launchpad/config.py`
- Modify: `tests/test_capacity_unit_js.py`
- Modify: `tests/test_hadoop_sudo_wire.py`
- Modify: `tests/test_system_connectivity_version.py`

**Interfaces:**
- Consumes: none
- Produces: `APP_VERSION = "1.6.185"`

- [ ] **Step 1: Write the failing pin updates**

Set the three version assertions to `"1.6.185"` (they currently expect `1.6.184`). Do not change `config.py` yet.

- [ ] **Step 2: Run pins to verify they fail**

Run: `python -m pytest tests/test_capacity_unit_js.py::test_app_version_153 tests/test_hadoop_sudo_wire.py::test_version_174 tests/test_system_connectivity_version.py -v`

Expected: FAIL (`1.6.184` != `1.6.185`)

- [ ] **Step 3: Bump config**

In `launchpad/config.py`: `APP_VERSION = "1.6.185"`

- [ ] **Step 4: Run pins to verify they pass**

Run: `python -m pytest tests/test_capacity_unit_js.py::test_app_version_153 tests/test_hadoop_sudo_wire.py::test_version_174 tests/test_system_connectivity_version.py tests/test_health_alert_state.py::test_desktop_alert_popups_enabled_defaults_on tests/test_dashboard_health_alerts.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/config.py tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py tests/test_system_connectivity_version.py
git commit -m "Bump version to 1.6.185 for dashboard Alert popups toggle."
```

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| Switch **Alert popups** after Mouse jiggler, before selection count | 2 |
| Default On; missing setting On | 1, 2 |
| Off: no floating window, no beep, overlays stay, poll continues | 2 |
| Persist `alert_popups_enabled` true/false; survives restart | 1, 2 |
| Close open dialog when turning Off | 2 |
| Turn On: next poll can show window | 2 |
| Admin per-card mute unchanged | 2 (no `set_alarm` all-cards) |
| Health Dashboard browser unchanged | (no `health_server.py` HTML) |
| APP_VERSION 1.6.185 | 3 |
