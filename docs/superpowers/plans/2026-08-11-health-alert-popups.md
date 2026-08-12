# Critical Health Alert Popups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Popup critical health alerts (with card name) on desktop and Health Dashboard, with Acknowledge / Pause / per-card Alarm off, plus drive detection and fixed Active Issues alert text (v**1.6.155**).

**Architecture:** New `health_alert_state` module owns fingerprints, acknowledgements, pause, and mute. Health Server exposes GET/POST APIs. Browser and desktop poll and show the same actions. Detection improves via alert message fallbacks, `lsdrive`, and canister command fix.

**Tech Stack:** Python, HealthServer HTTP, CustomTkinter, pytest.

**Spec:** `docs/superpowers/specs/2026-08-11-health-alert-popups-design.md`

## Global Constraints

- APP_VERSION is currently `1.6.154`; bump to `1.6.155` only in the final version task. Do not bump earlier.
- Popups are **critical only**. Warn stays in Active Issues without popup.
- Acknowledge = suppress fingerprint until issue clears; re-alert if it returns.
- Alarm off = mute popups/sound for **one card** until Alarm on; Active Issues still show.
- Pause options exactly: **5, 10, 15, 20** minutes (per card).
- Shared server-side state (setting key `health_alert_state`) so desktop and browser stay in sync.
- Close dismisses UI only (does not acknowledge).
- No email/SMS, no Windows Action Center, no FC-port popups, no collapsible Active Issues, no Excel export in this plan.
- Windows PowerShell commits (`git commit -m "..."`); commit at each task’s commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch or install zips.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/flashsystem_health.py` | Alert message fallbacks; drive analysis; promote offline/degraded drives |
| `launchpad/storage_presets.py` | `Health - Drives` (`lsdrive`); Controllers → `lsnodecanister` |
| `tests/test_flashsystem_health_alerts.py` (new or extend existing) | Alert text + drive critical tests |
| `launchpad/health_alert_state.py` | Fingerprints, ack/pause/mute, list open popup alerts |
| `tests/test_health_alert_state.py` | State machine tests |
| `launchpad/health_server.py` | API routes + browser modal/poll JS |
| `tests/test_health_alert_api.py` | API contract tests |
| `launchpad/ui/dashboard_view.py` | Desktop poll, dialog, beep |
| `tests/test_*` for dashboard wiring if pattern exists | Desktop smoke / string contracts |
| `launchpad/config.py` + version pin tests | `1.6.155` |

---

### Task 1: Alert text + drives + canister preset

**Files:**
- Modify: `launchpad/flashsystem_health.py`
- Modify: `launchpad/storage_presets.py`
- Create or modify: `tests/test_flashsystem_health_alerts.py` (if a closer existing test file exists for `_analyze_alerts`, extend it instead)

**Interfaces:**
- Consumes: `_table_rows`, `_row_map`, `_status_issue`, `_BAD_STATUS`
- Produces: `_analyze_alerts` non-empty messages; `_analyze_drives` (or status table on `lsdrive`) with category `drive` critical for offline/degraded; preset commands updated

- [ ] **Step 1: Write failing tests**

```python
from launchpad.flashsystem_health import analyze_health


def test_analyze_alerts_uses_description_when_message_empty():
    output = (
        "id:message:description:object_name\n"
        "1::Battery fault:node1\n"
    )
    result = analyze_health(
        "Valparaiso, IN",
        [{"label": "Health - Alerts", "command": "svcinfo lseventlog -alert yes -delim :", "output": output, "error": None}],
    )
    messages = [i["message"] for i in result["health_issues"] if i.get("category") == "alert" or "Battery" in str(i.get("message"))]
    assert any("Battery" in m for m in (i["message"] for i in result["health_issues"]))
    assert not any(i.get("message") in ("", None) for i in result["health_issues"] if i.get("category") in ("alert", "nvme", "cpu", "memory"))


def test_analyze_drives_offline_is_critical():
    output = (
        "id:status:use\n"
        "0:offline:member\n"
        "1:degraded:member\n"
        "2:online:member\n"
    )
    result = analyze_health(
        "Valparaiso, IN",
        [{"label": "Health - Drives", "command": "svcinfo lsdrive -delim :", "output": output, "error": None}],
    )
    drive_issues = [i for i in result["health_issues"] if i.get("category") == "drive"]
    assert len(drive_issues) >= 2
    assert all(i["severity"] == "critical" for i in drive_issues)
```

Adjust `analyze_health` call signature to match the real function (read `flashsystem_health.analyze_health` / `analyze_flashsystem_health` before writing). Prefer the public entry used by Health Server.

Also add a preset test if one exists for `SVC_COMMANDS`; otherwise assert in a small `tests/test_storage_presets_drives.py`:

```python
from launchpad.storage_presets import SVC_COMMANDS

def test_svc_commands_include_lsdrive_and_lsnodecanister():
    cmds = {label: cmd for label, cmd in SVC_COMMANDS}
    assert "lsdrive" in cmds["Health - Drives"]
    assert "lsnodecanister" in cmds["Health - Controllers"]
```

- [ ] **Step 2: Run tests — expect FAIL**

```powershell
cd C:\Users\BrianColley\LaunchPad
python -m pytest tests/test_flashsystem_health_alerts.py tests/test_storage_presets_drives.py -v
```

- [ ] **Step 3: Implement**

In `_analyze_alerts`, replace message selection with:

```python
def _first_text(*values: str) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""

message = _first_text(
    record.get("message"),
    record.get("description"),
    " ".join(p for p in (_first_text(record.get("event_id")), _first_text(record.get("object_name"))) if p),
    record.get("object_name"),
) or "Alert"
```

Add drive analysis after existing disk/nvme blocks: find result containing `lsdrive` / `Health - Drives`, call `_analyze_status_table` with `category="drive"`, `item_label="Drive"`. Force severity critical when status lowercased is in `_BAD_STATUS` or contains `degraded` (extend `_status_issue` or post-process drive issues to set `severity="critical"` for offline/degraded).

In `storage_presets.py` `SVC_COMMANDS`:
- Change `Health - Controllers` command to `svcinfo lsnodecanister -delim :`
- Add `("Health - Drives", "svcinfo lsdrive -delim :")` near other Health commands

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```powershell
git add launchpad/flashsystem_health.py launchpad/storage_presets.py tests/test_flashsystem_health_alerts.py tests/test_storage_presets_drives.py
git commit -m "Fix health alert text and detect offline FlashSystem drives."
```

---

### Task 2: `health_alert_state` module

**Files:**
- Create: `launchpad/health_alert_state.py`
- Create: `tests/test_health_alert_state.py`

**Interfaces:**
- Consumes: card dicts with `id`, `name`, `error`, `health_issues`, monitor flag
- Produces:
  - `HEALTH_ALERT_SETTING = "health_alert_state"`
  - `issue_fingerprint(card_id: int | str, category: str, message: str) -> str`
  - `empty_state() -> dict`
  - `load_state(raw: str | None) -> dict`
  - `dump_state(state: dict) -> str`
  - `acknowledge(state, fingerprint: str) -> dict`
  - `pause_card(state, card_id, minutes: int, *, now: float) -> dict`  # minutes in {5,10,15,20}
  - `set_alarm(state, card_id, muted: bool) -> dict`
  - `prune_acknowledgements(state, active_fingerprints: set[str]) -> dict`
  - `collect_critical_candidates(card: dict, *, monitor_on: bool) -> list[dict]`  # each has fingerprint, card_id, card_name, category, message, severity
  - `list_popup_alerts(cards: list[dict], monitor_states: dict, state: dict, *, now: float) -> list[dict]`

- [ ] **Step 1: Write failing tests** covering: warn excluded; connectivity from error; drive degraded included; acknowledge suppresses then clears when gone; pause windows; alarm mute one card; Close is not part of state (N/A).

```python
from launchpad.health_alert_state import (
    acknowledge,
    collect_critical_candidates,
    empty_state,
    issue_fingerprint,
    list_popup_alerts,
    pause_card,
    prune_acknowledgements,
    set_alarm,
)

def test_warn_not_popup_candidate():
    card = {"id": 1, "name": "Site", "error": None, "health_issues": [
        {"severity": "warn", "category": "capacity", "message": "Pool X is 81% full", "server": "Site"}
    ]}
    assert collect_critical_candidates(card, monitor_on=True) == []

def test_unreachable_is_connectivity_critical():
    card = {"id": 2, "name": "Valparaiso, IN", "error": "SSH timeout", "health_issues": [], "metrics": None}
    items = collect_critical_candidates(card, monitor_on=True)
    assert len(items) == 1
    assert items[0]["category"] == "connectivity"
    assert "Valparaiso" in items[0]["card_name"]

def test_acknowledge_until_clear():
    state = empty_state()
    fp = issue_fingerprint(1, "drive", "Drive 0 is offline")
    state = acknowledge(state, fp)
    card = {"id": 1, "name": "A", "error": None, "health_issues": [
        {"severity": "critical", "category": "drive", "message": "Drive 0 is offline", "server": "A"}
    ]}
    open_ = list_popup_alerts([card], {1: True}, state, now=1000.0)
    assert open_ == []
    state = prune_acknowledgements(state, set())  # issue cleared
    card_clear = {"id": 1, "name": "A", "error": None, "health_issues": []}
    assert list_popup_alerts([card_clear], {1: True}, state, now=1000.0) == []
    # return
    open2 = list_popup_alerts([card], {1: True}, state, now=1000.0)
    assert len(open2) == 1

def test_pause_and_alarm_mute():
    state = empty_state()
    card = {"id": 3, "name": "B", "error": None, "health_issues": [
        {"severity": "critical", "category": "node", "message": "Node n1 is offline", "server": "B"}
    ]}
    state = pause_card(state, 3, 10, now=1000.0)
    assert list_popup_alerts([card], {3: True}, state, now=1000.0) == []
    assert len(list_popup_alerts([card], {3: True}, state, now=1000.0 + 10 * 60 + 1)) == 1
    state = set_alarm(empty_state(), 3, True)
    assert list_popup_alerts([card], {3: True}, state, now=5000.0) == []
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement module** per interfaces. Use wall-clock `time.time()` for pause `paused_until`. State shape:

```python
{
  "acknowledged": ["fp1", ...],
  "alarm_muted": {"3": True},
  "paused_until": {"3": 1710000000.0},
}
```

`collect_critical_candidates`: if not monitor_on → []. If error and no useful health data → connectivity critical. Else include health_issues with severity critical; also include nvme/disk/mdisk/drive issues whose message/status indicates offline/degraded even if severity was warn (normalize to critical in the candidate).

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_alert_state.py tests/test_health_alert_state.py
git commit -m "Add shared health alert acknowledge, pause, and mute state."
```

---

### Task 3: Health Server alert APIs

**Files:**
- Modify: `launchpad/health_server.py`
- Create: `tests/test_health_alert_api.py`

**Interfaces:**
- Consumes: Task 2 module; settings getter/setter; `list_cards`; monitor states
- Produces:
  - `GET /api/health-alerts` → `{ "alerts": [...], "cards": { "<id>": {"alarm_muted": bool, "paused_until": float|null } } }`
  - `POST /api/health-alerts/acknowledge` body `{ "fingerprint": "..." }` or `{ "fingerprints": [...] }`
  - `POST /api/health-alerts/pause` body `{ "card_id": N, "minutes": 5|10|15|20 }`
  - `POST /api/health-alerts/alarm` body `{ "card_id": N, "muted": true|false }`

- [ ] **Step 1: Write API tests** using existing HealthServer test helpers (mirror `test_health_server_*` patterns: set_settings_backend, register_card, inject health_issues/error).

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Wire routes** in GET/POST handlers; persist via `_get_setting`/`_set_setting` key `health_alert_state`. On GET, prune acks against current fingerprints then return `list_popup_alerts`.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_health_alert_api.py
git commit -m "Expose health alert popup APIs on Health Server."
```

---

### Task 4: Browser Health Dashboard popup

**Files:**
- Modify: `launchpad/health_server.py` (Health HTML/JS embedded page)
- Modify or create: `tests/test_health_dashboard_alert_popup.py` (string/contract tests for modal markup and poll URL)

**Interfaces:**
- Consumes: `/api/health-alerts*` from Task 3
- Produces: modal with card name, issue list, Acknowledge, Pause 5/10/15/20, Alarm off, Close; poll ~30s

- [ ] **Step 1: Failing contract tests** asserting HTML contains `health-alert-modal`, `Acknowledge`, `Alarm off`, pause labels, and JS fetches `/api/health-alerts`.

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement modal + poll + action POSTs.** Show one card’s alerts at a time (queue). Close hides modal without POST acknowledge. After refresh success, trigger an immediate alert poll.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_health_dashboard_alert_popup.py
git commit -m "Add Health Dashboard critical alert popup with pause and mute."
```

---

### Task 5: Desktop Connection Dashboard popup

**Files:**
- Modify: `launchpad/ui/dashboard_view.py`
- Optionally small helper `launchpad/ui/health_alert_dialog.py` if it keeps `dashboard_view` cleaner
- Test: `tests/test_dashboard_health_alerts.py` (import/wiring / method presence / poll constant) following existing dashboard test style

**Interfaces:**
- Consumes: `get_health_server()` list + alert APIs (HTTP to local server **or** direct Python calls on the server object — prefer **direct method calls** on HealthServer if HTTP from same process is awkward; if so, add `HealthServer.get_health_alerts()` / `acknowledge_health_alert()` etc. used by both HTTP and desktop)
- Produces: CTkToplevel or message dialog with same actions; optional `winsound.MessageBeep` / `Beep` on new fingerprint; poll every 30s alongside capacity alerts

- [ ] **Step 1: If HTTP handlers are the only entry, extract server methods in this task (or Task 3 follow-up) so desktop can call without HTTP. Prefer adding methods in Task 3; this task only UI.**

- [ ] **Step 2: Failing test** that `dashboard_view.py` references health-alerts poll / dialog strings.

- [ ] **Step 3: Implement poll + dialog + beep (muted when card alarm off or paused).**

- [ ] **Step 4: PASS + commit**

```powershell
git add launchpad/ui/dashboard_view.py launchpad/ui/health_alert_dialog.py tests/test_dashboard_health_alerts.py
git commit -m "Add Connection Dashboard critical health alert popups."
```

---

### Task 6: Bump APP_VERSION to 1.6.155

**Files:**
- `launchpad/config.py`
- `tests/test_system_connectivity_version.py`
- `tests/test_hadoop_sudo_wire.py` (rename `test_version_154` → `test_version_155`)
- `tests/test_capacity_unit_js.py`

- [ ] **Step 1:** Update pins to `1.6.155` (tests fail).
- [ ] **Step 2:** Set `APP_VERSION = "1.6.155"`.
- [ ] **Step 3:** Run version + alert-focused suites — PASS.
- [ ] **Step 4: Commit**

```powershell
git add launchpad/config.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py tests/test_capacity_unit_js.py
git commit -m "Bump version to 1.6.155 for critical health alert popups."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Alert message fallbacks | Task 1 |
| lsdrive + canister command | Task 1 |
| Drive offline/degraded critical | Task 1 + 2 |
| Fingerprint / ack / pause / mute | Task 2 |
| Shared APIs | Task 3 |
| Browser popup | Task 4 |
| Desktop popup + beep | Task 5 |
| Version 1.6.155 | Task 6 |
| Critical-only / both surfaces | Tasks 2–5 |
