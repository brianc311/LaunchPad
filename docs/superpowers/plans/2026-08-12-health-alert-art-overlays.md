# Health Alert Art Overlays + I/O Intel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Match critical alerts to site/array PNG art, show Suppress/Snooze/Alarm/Close on card overlay + dialog + Health modal, and add I/O (FC) / power-aware canister wording (v**1.6.156**).

**Architecture:** New `health_alert_art` resolver maps card names to bundled PNGs under `BRANDING_DIR/health-alerts` (seeded from packaged resources). Desktop and browser reuse existing `health_alert_state` actions with new labels and art backgrounds. Detection extends `flashsystem_health` for FC ports and operator-facing issue titles.

**Tech Stack:** Python, CustomTkinter, HealthServer HTML/JS, pytest, Pillow/CTkImage as already used for branding images.

**Spec:** `docs/superpowers/specs/2026-08-12-health-alert-art-overlays-design.md`

## Global Constraints

- APP_VERSION is currently `1.6.155`; bump to `1.6.156` only in the final version task.
- Do **not** change acknowledge / pause / mute semantics — only UI labels and art.
- Button labels must be: **Suppress**, **Snooze 5/10/15/20**, **Alarm off/on**, **Close**.
- Surfaces: Connection Dashboard card overlay + topmost dialog + Health Dashboard modal.
- Art: bundled PNGs matched by normalized card name; styled fallback when no match.
- Critical-only popups remain.
- Windows PowerShell commits (`git commit -m "..."`); commit at each task commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch or install zips.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/health_alert_art.py` | Name normalize + resolve PNG path |
| `launchpad/resources/health-alerts/` | Packaged PNG seeds (copy from operator assets) |
| `tests/test_health_alert_art.py` | Matching / fallback tests |
| `launchpad/flashsystem_health.py` | FC/I/O critical issues; operator wording |
| `tests/test_flashsystem_health_alerts.py` | Extend detection tests |
| `launchpad/ui/health_alert_dialog.py` | Art background + new labels |
| `launchpad/ui/card_widget.py` | Card overlay with art + buttons |
| `launchpad/ui/dashboard_view.py` | Wire overlay when alerts open for visible cards |
| `launchpad/health_server.py` | Serve art; modal CSS/JS labels + background |
| `tests/test_health_dashboard_alert_popup.py` | Label + art contract tests |
| `tests/test_dashboard_health_alerts.py` | Desktop label contracts |
| `launchpad/config.py` + version pins | `1.6.156` |

---

### Task 1: Art resolver + packaged assets

**Files:**
- Create: `launchpad/health_alert_art.py`
- Create: `launchpad/resources/health-alerts/` (copy the operator PNGs into this folder; keep filenames)
- Create: `tests/test_health_alert_art.py`

**Interfaces:**
- Consumes: `BRANDING_DIR` from `launchpad.config`
- Produces:
  - `HEALTH_ALERTS_SUBDIR = "health-alerts"`
  - `normalize_alert_art_key(name: str) -> str`
  - `ensure_health_alert_art_dir() -> Path`  # creates `BRANDING_DIR/health-alerts`, seeds from package resources if empty
  - `resolve_health_alert_art(card_name: str, *, art_dir: Path | None = None) -> Path | None`

- [ ] **Step 1: Write failing tests**

```python
from pathlib import Path
from launchpad.health_alert_art import normalize_alert_art_key, resolve_health_alert_art


def test_normalize_strips_distribution_center_suffix():
    assert "VALPARAISO" in normalize_alert_art_key("Valparaiso, IN Distribution Center")
    assert "DISTRIBUTION" not in normalize_alert_art_key("Valparaiso, IN Distribution Center")


def test_resolve_matches_valparaiso_filename(tmp_path: Path):
    png = tmp_path / "VALPARAISO__IN-e901bfef.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n")
    hit = resolve_health_alert_art("Valparaiso, IN", art_dir=tmp_path)
    assert hit == png


def test_resolve_missing_returns_none(tmp_path: Path):
    assert resolve_health_alert_art("Unknown Site, ZZ", art_dir=tmp_path) is None
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
cd C:\Users\BrianColley\LaunchPad
python -m pytest tests/test_health_alert_art.py -v
```

- [ ] **Step 3: Implement `health_alert_art.py`**

Normalize: uppercase; remove trailing phrases `DISTRIBUTION CENTER`, `DISTRIBUTION`, `DIST CENTER` (case-insensitive); replace non `[A-Z0-9]` with `_`; collapse `__+` to `__` then trim `_`.

Resolve: list `*.png` / `*.PNG` in art_dir; compare normalized filename stem (strip UUID-like trailing `-hex` segments optionally by matching longest prefix of normalized card key against normalized stem). Prefer exact equality of normalized stem prefix to card key; else longest stem that starts with card key or card key that starts with stem core (site part).

`ensure_health_alert_art_dir`: if branding dir missing images, copy from `Path(__file__).resolve().parent / "resources" / "health-alerts"`.

Copy the provided alert PNGs into `launchpad/resources/health-alerts/` (from Cursor assets / operator files). Do not rename unless required for matching tests.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_alert_art.py launchpad/resources/health-alerts tests/test_health_alert_art.py
git commit -m "Add health alert art name matching and packaged PNGs."
```

---

### Task 2: I/O (FC) detection + operator wording

**Files:**
- Modify: `launchpad/flashsystem_health.py`
- Modify: `tests/test_flashsystem_health_alerts.py`
- Modify: `launchpad/health_alert_state.py` only if operator titles need a small classifier used by popup candidates (prefer doing wording in analyze_health so Active Issues match)

**Interfaces:**
- Consumes: `parse_fc_ports` / `_analyze_status_table` / `_BAD_STATUS`
- Produces: critical issues category `io` (or `fc`) with message like `I/O card failed (port 1)`; canister/power short titles when classifiable

- [ ] **Step 1: Failing tests**

```python
def test_lsportfc_offline_is_io_critical():
    output = "id:fc_io_port_id:status\n0:1:offline\n1:2:active\n"
    result = analyze_health(
        "Site",
        [{"label": "FC - Ports WWPN", "command": "svcinfo lsportfc -delim :", "output": output, "error": None}],
    )
    ios = [i for i in result["health_issues"] if i.get("category") in ("io", "fc")]
    assert ios
    assert all(i["severity"] == "critical" for i in ios)
    assert any("I/O" in i["message"] or "I/O card" in i["message"] for i in ios)


def test_power_alert_with_offline_canister_wording():
    # Use realistic analyze_health inputs: offline canister + alert description containing power
    ...
```

Fill the second test with the real `analyze_health` command_results shape used in Task 1 of 1.6.155.

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement** `_analyze_fc_ports` (or status table + rewrite message) called from `analyze_health` when `lsportfc` output present. Add helper to rewrite node/controller/drive/connectivity messages to operator short titles when unambiguous; for power, if any alert message contains power/psu/ups/battery tokens and a canister/node is offline, set message `Canister lost power` (keep fingerprint stable via category+message).

- [ ] **Step 4: PASS + commit**

```powershell
git add launchpad/flashsystem_health.py tests/test_flashsystem_health_alerts.py
git commit -m "Detect FC I/O failures and clarify canister power alert text."
```

---

### Task 3: Desktop dialog labels + art + card overlay

**Files:**
- Modify: `launchpad/ui/health_alert_dialog.py`
- Modify: `launchpad/ui/card_widget.py`
- Modify: `launchpad/ui/dashboard_view.py`
- Modify: `tests/test_dashboard_health_alerts.py`

**Interfaces:**
- Consumes: `resolve_health_alert_art`, `ensure_health_alert_art_dir`, existing acknowledge/pause/alarm handlers
- Produces: dialog + overlay UI with Suppress / Snooze / Alarm / Close and PNG background when resolved

- [ ] **Step 1: Failing contract tests** asserting `Suppress`, `Snooze 5 min`, `Alarm off`, `Close` strings in `health_alert_dialog.py` / dashboard wiring; assert overlay helper or method name exists on card widget.

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**
  - Rename button texts in `HealthAlertDialog`.
  - Load CTkImage from resolved path as dialog background (or place image label behind content); if None, keep dark styled fallback with large ALERT header.
  - Add card overlay frame (place/pack over card) when dashboard has open alerts for that `card_id`; buttons call same handlers as dialog; dismiss overlay on Suppress/Snooze/Close as appropriate.
  - Call `ensure_health_alert_art_dir()` once on dashboard start / first alert poll.

- [ ] **Step 4: PASS + commit**

```powershell
git add launchpad/ui/health_alert_dialog.py launchpad/ui/card_widget.py launchpad/ui/dashboard_view.py tests/test_dashboard_health_alerts.py
git commit -m "Style desktop health alerts with art, Suppress, and Snooze labels."
```

---

### Task 4: Health Dashboard art modal + art API

**Files:**
- Modify: `launchpad/health_server.py`
- Modify: `tests/test_health_dashboard_alert_popup.py`
- Modify: `tests/test_health_alert_api.py` (optional art field)

**Interfaces:**
- Consumes: `resolve_health_alert_art`, card name from alerts
- Produces:
  - `GET /api/health-alerts` includes `art_url` per card group or alert when art exists (e.g. `/api/health-alerts/art?card_id=N`)
  - `GET /api/health-alerts/art?card_id=N` returns image bytes or 404
  - Modal buttons: Suppress, Snooze…, Alarm off/on, Close
  - Modal CSS uses `background-image` when `art_url` present

- [ ] **Step 1: Failing tests** for button label strings and art route / `art_url` field.

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement** routes + JS label renames + background styling; Close still does not acknowledge.

- [ ] **Step 4: PASS + commit**

```powershell
git add launchpad/health_server.py tests/test_health_dashboard_alert_popup.py tests/test_health_alert_api.py
git commit -m "Add Health Dashboard alert art backgrounds and Suppress labels."
```

---

### Task 5: Bump APP_VERSION to 1.6.156

**Files:**
- `launchpad/config.py`
- `tests/test_system_connectivity_version.py`
- `tests/test_capacity_unit_js.py`
- `tests/test_hadoop_sudo_wire.py` (`test_version_155` → `test_version_156`)

- [ ] **Step 1:** Update pins to `1.6.156` (fail).
- [ ] **Step 2:** Set `APP_VERSION = "1.6.156"`.
- [ ] **Step 3:** Run version + alert-focused suites — PASS.
- [ ] **Step 4: Commit**

```powershell
git add launchpad/config.py tests/test_system_connectivity_version.py tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py
git commit -m "Bump version to 1.6.156 for health alert art overlays."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| PNG name matching + seed dir | Task 1 |
| I/O FC critical + power wording | Task 2 |
| Desktop overlay + dialog art/labels | Task 3 |
| Browser modal art/labels + art API | Task 4 |
| Version 1.6.156 | Task 5 |
| Unchanged ack/pause/mute semantics | Tasks 3–4 (labels only) |
