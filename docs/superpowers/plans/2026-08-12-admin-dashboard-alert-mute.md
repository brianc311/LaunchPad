# Admin + Dashboard Alert Mute Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let operators turn critical health alert popups off per card from Admin Connections and from an always-visible dashboard monitor-row control, using the existing Alarm mute state (v**1.6.160**).

**Architecture:** Reuse `health_alert_state.set_alarm` / `alarm_muted` and `/api/health-alerts/alarm`. Extend `GlowCard` monitor row to always show Alerts on/off; add the same control to Admin card form, reading/writing the shared `health_alert_state` setting.

**Tech Stack:** Python, CustomTkinter, pytest.

**Spec:** `docs/superpowers/specs/2026-08-12-admin-dashboard-alert-mute-design.md`

## Global Constraints

- APP_VERSION is currently `1.6.159`; bump to `1.6.160` only in the final version task.
- Mute semantics must remain identical to popup **Alarm off** (`alarm_muted`); do not add a second mute store or card DB column.
- Surfaces: Admin Connections form + dashboard monitor row + existing popup Alarm control (keep in sync).
- When muted: no critical dialog, no health-alert overlay, no beep for that card (`list_popup_alerts` already gates this).
- Windows PowerShell commits (`git commit -m "..."`); commit at each task commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch or install zips.
- Dell HPE report fix is out of scope (Project 2).

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/ui/card_widget.py` | Always-visible Alerts on/off on monitor row |
| `launchpad/ui/dashboard_view.py` | Wire toggle callback; sync label from poll |
| `tests/test_dashboard_health_alerts.py` | Contract tests for always-visible control |
| `launchpad/ui/admin_view.py` | Alerts On/Off on Connections card form |
| `tests/test_admin_alert_mute.py` (new) | Admin form + mute persistence contracts |
| `launchpad/config.py` + version pins | `1.6.160` |

---

### Task 1: Always-visible dashboard Alerts on/off

**Files:**
- Modify: `launchpad/ui/card_widget.py` (`set_health_alarm_muted` and related)
- Modify: `launchpad/ui/dashboard_view.py` (`_sync_health_alarm_muted_indicators`, toggle wiring)
- Modify: `tests/test_dashboard_health_alerts.py`

**Interfaces:**
- Consumes: existing `_toggle_health_alarm_for_card` / `_set_health_alarm` / poll `alarm_muted`
- Produces: monitor-row control always present when `monitor_row` exists; text **Alerts on** when not muted, **Alerts off** when muted; click toggles mute via existing dashboard handlers

- [ ] **Step 1: Write failing contract tests**

Add to `tests/test_dashboard_health_alerts.py`:

```python
def test_card_widget_exposes_always_visible_alerts_toggle():
    source = Path("launchpad/ui/card_widget.py").read_text(encoding="utf-8")
    assert "Alerts on" in source
    assert "Alerts off" in source
    assert "set_health_alarm_muted" in source


def test_dashboard_wires_alerts_toggle_to_health_alarm():
    assert "_toggle_health_alarm_for_card" in DASH
    assert "set_health_alarm_muted" in DASH
```

(Adjust assertions to match the exact strings you implement if you use a switch with different labels — but prefer **Alerts on** / **Alerts off** per spec.)

- [ ] **Step 2: Run — expect FAIL**

```powershell
cd C:\Users\BrianColley\LaunchPad
python -m pytest tests/test_dashboard_health_alerts.py::test_card_widget_exposes_always_visible_alerts_toggle -v
```

- [ ] **Step 3: Implement**

1. Change `GlowCard.set_health_alarm_muted` so that when `monitor_row` exists it **always** shows a control (not only when muted):
   - Not muted: button/switch text **Alerts on** (or checked switch); clicking calls `on_alarm_on` callback — note the callback name may become `on_toggle`; keep wiring so dashboard passes `_toggle_health_alarm_for_card`.
   - Muted: text **Alerts off**; same toggle callback; keep muted hint text (update to `Alerts off — no health popups` for consistency, or keep existing “Alarm muted…” if you prefer minimal copy churn — **prefer** `Alerts off — no health popups`).
2. Ensure unmuted state restores the normal monitor hint (`On — stats refresh allowed` / `Off — no background SSH`).
3. In `dashboard_view._sync_health_alarm_muted_indicators`, always call `set_health_alarm_muted` with the toggle callback for every SSH/monitor card that has a monitor row (including unmuted cards).
4. Do not change `set_alarm` / API semantics.

- [ ] **Step 4: Run dashboard health alert tests — PASS**

```powershell
python -m pytest tests/test_dashboard_health_alerts.py -q
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/ui/card_widget.py launchpad/ui/dashboard_view.py tests/test_dashboard_health_alerts.py
git commit -m "Show always-visible Alerts on/off on dashboard cards."
```

---

### Task 2: Admin Connections Alerts toggle

**Files:**
- Modify: `launchpad/ui/admin_view.py`
- Create: `tests/test_admin_alert_mute.py`

**Interfaces:**
- Consumes: `launchpad.health_alert_state` — `HEALTH_ALERT_SETTING`, `load_state`, `dump_state`, `set_alarm`, `normalize_state` (or whatever the module exports for load/save)
- Produces: Alerts control on card form; load mute when `_load_card`; changing control immediately persists mute via DB setting (same JSON as HealthServer)

- [ ] **Step 1: Failing tests**

```python
from pathlib import Path

from launchpad.health_alert_state import (
    HEALTH_ALERT_SETTING,
    dump_state,
    empty_state,
    load_state,
    set_alarm,
)


def test_admin_view_has_alerts_mute_control():
    source = Path("launchpad/ui/admin_view.py").read_text(encoding="utf-8")
    assert "Alerts" in source
    assert "set_alarm" in source or "health_alert" in source.lower()
    assert "_on_card_alerts_toggle" in source or "_persist_card_alert_mute" in source


def test_set_alarm_round_trip_in_setting_blob():
    state = empty_state()
    state = set_alarm(state, 42, True)
    blob = dump_state(state)
    loaded = load_state(blob)
    assert loaded["alarm_muted"].get("42") is True
    state = set_alarm(loaded, 42, False)
    assert "42" not in state["alarm_muted"]
```

(If `empty_state` / `dump_state` / `load_state` names differ, use the public helpers already used by `health_server.py`.)

- [ ] **Step 2: Run — expect FAIL**

```powershell
python -m pytest tests/test_admin_alert_mute.py -v
```

- [ ] **Step 3: Implement Admin UI**

1. In `_build_card_form`, after Monitor-related fields (or near device profile), add:
   - Label **Alerts**
   - `CTkSwitch` or segmented **On/Off** (`self.card_alerts_var`), default On.
2. Add helpers:
   - `_load_health_alert_state()` / `_save_health_alert_state(state)` using `self.db.get_setting(HEALTH_ALERT_SETTING, "")` and `set_setting`.
   - `_card_alerts_muted(card_id) -> bool`
   - `_persist_card_alert_mute(card_id, muted: bool)` → `set_alarm` + save.
3. On `_load_card(card_id)`: set switch to Off if muted else On (without firing a spurious persist if possible).
4. On toggle command: if editing an existing card id, persist immediately; if “new card” with no id yet, remember pending mute and apply after successful `_save_card` creates the id (or disable the switch until saved — **prefer** disable until the card has an id, with hint “Save card first”).
5. On `_clear_form` / new card: Alerts On.

- [ ] **Step 4: PASS**

```powershell
python -m pytest tests/test_admin_alert_mute.py tests/test_health_alert_state.py tests/test_dashboard_health_alerts.py -q
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/ui/admin_view.py tests/test_admin_alert_mute.py
git commit -m "Add Admin Connections Alerts on/off mute control."
```

---

### Task 3: Bump APP_VERSION to 1.6.160

**Files:**
- `launchpad/config.py`
- `tests/test_system_connectivity_version.py`
- `tests/test_capacity_unit_js.py`
- `tests/test_hadoop_sudo_wire.py` (`test_version_159` → `test_version_160`)

- [ ] **Step 1:** Update pins to `1.6.160` (fail).
- [ ] **Step 2:** Set `APP_VERSION = "1.6.160"`.
- [ ] **Step 3:** Run version + alert mute suites — PASS.
- [ ] **Step 4: Commit**

```powershell
git add launchpad/config.py tests/test_system_connectivity_version.py tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py
git commit -m "Bump version to 1.6.160 for admin and dashboard alert mute."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Always-visible dashboard Alerts on/off | Task 1 |
| Admin Connections Alerts toggle | Task 2 |
| Shared `alarm_muted` / Alarm off semantics | Tasks 1–2 |
| Popup Alarm remains | (unchanged; sync via same state) |
| Version 1.6.160 | Task 3 |
| Dell HPE out of scope | — |
