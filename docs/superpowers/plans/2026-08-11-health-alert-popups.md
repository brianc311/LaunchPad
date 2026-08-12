# Critical Health Alert Popups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Popup critical health alerts (with card name) on desktop and Health Dashboard, with Acknowledge / Pause / per-card Alarm off, plus drive detection and readable Active Issues alert text (v**1.6.155**).

**Architecture:** Pure `health_alert_state.py` owns fingerprints, ack-until-clear, per-card mute, and pause timers. Health Server exposes GET/POST APIs over a JSON settings key. Browser and desktop both poll and act on that API. Detection improvements (`_analyze_alerts` fallbacks, `lsdrive`, canister command) feed `health_issues` before popup eligibility.

**Tech Stack:** Python, HealthServer HTTP, CustomTkinter dashboard, embedded Health Dashboard JS, pytest.

**Spec:** `docs/superpowers/specs/2026-08-11-health-alert-popups-design.md`

## Global Constraints

- APP_VERSION is currently `1.6.154`; bump to `1.6.155` only in the final version task. Do not bump earlier.
- Popups are **critical only**. Warn stays in Active Issues, never in popup list.
- Acknowledge = suppress fingerprint until the issue clears; re-alert if it returns.
- Alarm off = mute popups/sound for **one card** until Alarm on; Active Issues still show.
- Pause options exactly: **5, 10, 15, 20** minutes (per card; new pause replaces prior expiry).
- Surfaces: Connection Dashboard **and** Health Dashboard; shared server state.
- Setting key: `health_alert_state` (JSON via existing settings getter/setter).
- Close dismisses UI only (does not acknowledge).
- No email/SMS/Windows Action Center; no FC-port popups; no collapsible Active Issues; no Excel export work in this plan.
- Windows PowerShell commits (`git commit -m "..."`); commit at each task’s commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch or install zips.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/flashsystem_health.py` | Alert message fallbacks; drive analysis; promote offline/degraded drives |
| `launchpad/storage_presets.py` | `Health - Drives` (`lsdrive`); Controllers → `lsnodecanister` |
| `tests/test_health_alert_messages.py` | Alert text + drive critical tests |
| `launchpad/health_alert_state.py` | Fingerprints, mute, pause, ack, open-popup computation |
| `tests/test_health_alert_state.py` | State machine tests |
| `launchpad/health_server.py` | Persist state; `/api/health-alerts*` routes; browser modal/poll JS |
| `tests/test_health_alerts_api.py` | API integration tests |
| `tests/test_health_alert_page.py` | HTML/JS contracts for modal + poll |
| `launchpad/ui/dashboard_view.py` | Desktop poll + dialog + beep |
| `launchpad/config.py` | `APP_VERSION` → `1.6.155` |
| Version pin tests | `1.6.155` |

---

### Task 1: Alert message fallbacks + drive/canister detection

**Files:**
- Modify: `launchpad/flashsystem_health.py`
- Modify: `launchpad/storage_presets.py`
- Create: `tests/test_health_alert_messages.py`

**Interfaces:**
- Consumes: existing `_analyze_alerts`, `_analyze_status_table`, `_status_issue`, `analyze_health`
- Produces: non-empty alert messages; `category=drive` critical issues from `lsdrive`; Controllers command uses `lsnodecanister`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_health_alert_messages.py`:

```python
from launchpad.flashsystem_health import analyze_health
from launchpad.storage_presets import SVC_COMMANDS


def test_analyze_alerts_uses_description_when_message_blank():
    output = (
        "id:message:description:object_name\n"
        "1::Canister battery fault:node1\n"
    )
    analysis = analyze_health(
        "Valparaiso, IN",
        [{"label": "Health - Alerts", "command": "lseventlog", "output": output, "error": None}],
        None,
    )
    alerts = [i for i in analysis["health_issues"] if i.get("category") == "alert"]
    assert alerts
    assert "Canister battery fault" in alerts[0]["message"]
    assert alerts[0]["message"].strip()


def test_lsdrive_offline_is_critical_drive_issue():
    output = (
        "id:status:capacity:use\n"
        "0:offline:1.8TB:member\n"
    )
    analysis = analyze_health(
        "Valparaiso, IN",
        [{"label": "Health - Drives", "command": "svcinfo lsdrive -delim :", "output": output, "error": None}],
        None,
    )
    drives = [i for i in analysis["health_issues"] if i.get("category") == "drive"]
    assert drives
    assert drives[0]["severity"] == "critical"
    assert "offline" in drives[0]["message"].lower()


def test_svc_commands_include_lsdrive_and_lsnodecanister():
    labels = {label: cmd for label, cmd in SVC_COMMANDS}
    assert "lsdrive" in labels["Health - Drives"]
    assert "lsnodecanister" in labels["Health - Controllers"]
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
cd C:\Users\BrianColley\LaunchPad
python -m pytest tests/test_health_alert_messages.py -v
```

Expected: FAIL (missing message text / no drive issues / preset strings absent).

- [ ] **Step 3: Implement**

In `storage_presets.py` `SVC_COMMANDS`:

- Change Controllers line to `("Health - Controllers", "svcinfo lsnodecanister -delim :")`.
- Add `("Health - Drives", "svcinfo lsdrive -delim :")` after Controllers (before Alerts is fine).

In `flashsystem_health.py` `_analyze_alerts`, replace message extraction with:

```python
def _first_nonempty(*values: str) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""

message = _first_nonempty(
    record.get("message"),
    record.get("description"),
    " ".join(
        part
        for part in (
            str(record.get("event_id") or "").strip(),
            str(record.get("object_name") or "").strip(),
        )
        if part
    ),
    record.get("object_name"),
) or "Alert"
```

Add `_analyze_drives` (mirror `_analyze_nvme` / `_status_issue` with `category="drive"`, `item_label="Drive"`). Force severity critical when status lowercased contains `offline` or `degraded`:

```python
issue = _status_issue("drive", name, "Drive", status, server=server)
if issue and any(token in (status or "").lower() for token in ("offline", "degraded")):
    issue["severity"] = "critical"
```

Call it from `analyze_health` with `_find_result(..., "lsdrive", "health - drives")`. Ensure Controllers find still matches `lsnodecanister` (already in `_find_result` needles for controllers).

Also promote existing `nvme`/`disk`/`mdisk` issues containing offline/degraded to critical in a small helper used when building issues OR inside those analyzers — preferred: after collecting issues in `analyze_health`, run:

```python
for issue in issues:
    cat = str(issue.get("category") or "").lower()
    msg = str(issue.get("message") or "").lower()
    if cat in {"nvme", "disk", "mdisk", "drive"} and any(
        t in msg for t in ("offline", "degraded", "failed")
    ):
        issue["severity"] = "critical"
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/test_health_alert_messages.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/flashsystem_health.py launchpad/storage_presets.py tests/test_health_alert_messages.py
git commit -m "Fix alert text and detect offline FlashSystem drives."
```

---

### Task 2: `health_alert_state` module

**Files:**
- Create: `launchpad/health_alert_state.py`
- Create: `tests/test_health_alert_state.py`

**Interfaces:**
- Consumes: card dicts with `id`, `name`, `error`, `health_issues`, `updated_at`; monitor_on map
- Produces:
  - `HEALTH_ALERT_SETTING = "health_alert_state"`
  - `issue_fingerprint(card_id, category, message) -> str`
  - `normalize_state(raw) -> dict`
  - `collect_critical_candidates(cards, monitor_states) -> list[dict]`  # each has card_id, card_name, category, message, severity, fingerprint
  - `open_popup_alerts(candidates, state, *, now: float) -> list[dict]`
  - `acknowledge(state, fingerprints: list[str], present: set[str]) -> dict`
  - `prune_acknowledgements(state, present: set[str]) -> dict`
  - `set_pause(state, card_id, minutes, *, now) -> dict`
  - `set_alarm_muted(state, card_id, muted: bool) -> dict`
  - `PAUSE_MINUTES = (5, 10, 15, 20)`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_health_alert_state.py` covering:

```python
import time
from launchpad.health_alert_state import (
    PAUSE_MINUTES,
    acknowledge,
    collect_critical_candidates,
    issue_fingerprint,
    open_popup_alerts,
    prune_acknowledgements,
    set_alarm_muted,
    set_pause,
)


def test_warn_not_candidate():
    cards = [{
        "id": 1,
        "name": "Site A",
        "error": None,
        "updated_at": "t",
        "health_issues": [{"severity": "warn", "category": "capacity", "message": "80%"}],
    }]
    assert collect_critical_candidates(cards, {1: True}) == []


def test_unreachable_is_connectivity_critical():
    cards = [{
        "id": 2,
        "name": "Valparaiso, IN",
        "error": "SSH timeout",
        "updated_at": "t",
        "health_issues": [],
        "metrics": None,
        "command_results": None,
    }]
    items = collect_critical_candidates(cards, {2: True})
    assert len(items) == 1
    assert items[0]["category"] == "connectivity"
    assert items[0]["card_name"] == "Valparaiso, IN"
    assert "SSH timeout" in items[0]["message"]


def test_acknowledge_until_clear_then_return():
    fp = issue_fingerprint(1, "drive", "Drive 0 is offline")
    state = {"acknowledged": [], "muted": {}, "paused_until": {}}
    state = acknowledge(state, [fp], {fp})
    cand = [{"fingerprint": fp, "card_id": 1, "card_name": "A", "category": "drive", "message": "Drive 0 is offline", "severity": "critical"}]
    assert open_popup_alerts(cand, state, now=time.time()) == []
    state = prune_acknowledgements(state, set())  # cleared
    assert open_popup_alerts(cand, state, now=time.time())  # returns again


def test_pause_and_alarm_mute():
    assert PAUSE_MINUTES == (5, 10, 15, 20)
    now = 1_000_000.0
    fp = issue_fingerprint(3, "node", "Node n1 is offline")
    cand = [{"fingerprint": fp, "card_id": 3, "card_name": "B", "category": "node", "message": "Node n1 is offline", "severity": "critical"}]
    state = set_pause({"acknowledged": [], "muted": {}, "paused_until": {}}, 3, 10, now=now)
    assert open_popup_alerts(cand, state, now=now + 60) == []
    assert open_popup_alerts(cand, state, now=now + 601)
    state = set_alarm_muted({"acknowledged": [], "muted": {}, "paused_until": {}}, 3, True)
    assert open_popup_alerts(cand, state, now=now) == []
```

Unreachable detection: treat as unreachable when monitor on and `error` is non-empty and there is no successful health payload (`not command_results` and not metrics) — match Health Dashboard `fail` styling intent.

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/test_health_alert_state.py -v
```

Expected: FAIL import / missing module.

- [ ] **Step 3: Implement `launchpad/health_alert_state.py`**

Implement the interfaces above. State shape:

```python
{
  "acknowledged": ["1|drive|drive 0 is offline", ...],
  "muted": {"3": true},
  "paused_until": {"3": 1710000000.0},  # unix time
}
```

`issue_fingerprint`: `f"{card_id}|{category}|{message.strip().lower()}"`.

`open_popup_alerts`: drop if fingerprint in acknowledged; drop if card muted; drop if `now < paused_until[card_id]`; else include.

`acknowledge`: add fingerprints; `prune_acknowledgements`: keep only those still in `present`.

Reject pause minutes not in `PAUSE_MINUTES` with `ValueError`.

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/test_health_alert_state.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_alert_state.py tests/test_health_alert_state.py
git commit -m "Add shared health alert acknowledge, pause, and mute state."
```

---

### Task 3: Health Server `/api/health-alerts` API

**Files:**
- Modify: `launchpad/health_server.py`
- Create: `tests/test_health_alerts_api.py`

**Interfaces:**
- Consumes: Task 2 helpers; settings getter/setter; `list_cards` / monitor map
- Produces:
  - `GET /api/health-alerts` → `{ "alerts": [...], "cards": { "<id>": {"muted": bool, "paused_until": float|null } } }`
  - `POST /api/health-alerts/acknowledge` body `{ "fingerprints": ["..."] }`
  - `POST /api/health-alerts/pause` body `{ "card_id": 1, "minutes": 10 }`
  - `POST /api/health-alerts/alarm` body `{ "card_id": 1, "muted": true }`
  - On GET: prune acks against current present fingerprints; persist updated state

- [ ] **Step 1: Write the failing API tests**

Use the existing HealthServer + settings backend pattern from `tests/test_health_server_lun_builder.py` / capacity tests:

```python
def test_health_alerts_get_and_acknowledge(monkeypatch):
    # register monitor-on card with critical drive issue via fake command_results
    # GET returns alert with card name
    # POST acknowledge
    # GET returns empty alerts for that fingerprint
    ...


def test_health_alerts_pause_and_alarm(monkeypatch):
    # pause 5 → empty; alarm mute → empty for that card only
    ...
```

Keep tests focused: monkeypatch `list_cards` / card objects or inject `command_results` + monitor state the same way other health API tests do. If monitor map is only in the desktop app, Health Server must expose monitor state via existing `/api/monitor` — use that when collecting candidates.

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/test_health_alerts_api.py -v
```

Expected: FAIL (404 / missing handlers).

- [ ] **Step 3: Wire HealthServer methods + routes**

Add helpers on `HealthServer`:

- `_load_health_alert_state` / `_save_health_alert_state`
- `get_health_alerts()` — list monitor-on cards as API dicts, `collect_critical_candidates`, prune acks, `open_popup_alerts`, return payload
- `acknowledge_health_alerts(fingerprints)`
- `pause_health_alerts(card_id, minutes)`
- `set_health_alert_alarm(card_id, muted)`

In the HTTP handler GET/POST branches (alongside other `/api/` routes), dispatch the four paths. Require unlock/settings backend when persisting (same pattern as other mutating APIs).

When building candidates from `to_api()` cards, connectivity: if monitor on and `error` and not `cardHasData`-equivalent (no metrics and no command_results), inject connectivity critical in `collect_critical_candidates` (already Task 2).

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/test_health_alerts_api.py tests/test_health_alert_state.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_health_alerts_api.py
git commit -m "Expose health alert popup API with acknowledge, pause, and mute."
```

---

### Task 4: Health Dashboard browser popup

**Files:**
- Modify: `launchpad/health_server.py` (HEALTH HTML/JS)
- Create: `tests/test_health_alert_page.py`

**Interfaces:**
- Consumes: `/api/health-alerts*` from Task 3
- Produces: modal with card name, issue list, Acknowledge, Pause 5/10/15/20, Alarm off, Close; poll ~30s

- [ ] **Step 1: Write failing page-contract tests**

```python
from launchpad.health_server import HEALTH_DASHBOARD_HTML  # use the actual HTML constant name in health_server


def test_health_dashboard_has_alert_modal_and_poll():
    html = HEALTH_DASHBOARD_HTML  # or extract via HealthServer page helper used by other tests
    assert "health-alert-modal" in html
    assert "/api/health-alerts" in html
    assert "Acknowledge" in html
    assert "Alarm off" in html
    assert "Pause" in html
```

Inspect how other tests load Health HTML (`test_capacity_unit_js.py` / active-issues tests) and match that pattern.

- [ ] **Step 2: Run test to verify it fails**

```powershell
python -m pytest tests/test_health_alert_page.py -v
```

Expected: FAIL missing strings.

- [ ] **Step 3: Add modal + JS**

In Health Dashboard HTML:

- Modal backdrop `#health-alert-modal` with title `#health-alert-card-name`, body `#health-alert-body`, buttons Acknowledge / Pause select (5/10/15/20) / Alarm off / Close.
- JS `pollHealthAlerts()` every 30s and after card refresh success: `GET /api/health-alerts`; if `alerts.length` and modal not user-closed-for-fingerprint set, show first card’s alerts (group by `card_id`).
- Acknowledge posts fingerprints of listed items; Pause posts `card_id` + minutes; Alarm off posts `muted: true`.
- Track `dismissedFingerprints` only for Close (session); still re-show on next poll if still open (per spec Close does not acknowledge) — so Close only hides until next poll cycle **or** hide until fingerprints change. Spec: “may reappear on next poll”. Implement: Close sets `suppressUntilNextChange` for current fingerprint set; if GET returns the same set, stay hidden; if set changes, show again.

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/test_health_alert_page.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_health_alert_page.py
git commit -m "Add Health Dashboard critical alert popup with pause and mute."
```

---

### Task 5: Desktop Connection Dashboard popup

**Files:**
- Modify: `launchpad/ui/dashboard_view.py`
- Create: `tests/test_dashboard_health_alerts.py` (pure helpers if extracted; otherwise light smoke importing poll method with mocks)

**Interfaces:**
- Consumes: `get_health_server().get_health_alerts()` (prefer in-process calls like capacity alerts, not raw HTTP)
- Produces: modal dialog (CTkToplevel or messagebox-style custom frame) with same actions; poll ~30s; beep on new fingerprint when not muted

- [ ] **Step 1: Write failing test for poll eligibility helper**

Prefer extracting a tiny pure function in `health_alert_state.py` or `dashboard_health_alerts.py`:

```python
# launchpad/dashboard_health_alerts.py
HEALTH_ALERT_POLL_MS = 30_000

def new_fingerprints(previous: set[str], current: list[dict]) -> set[str]:
    now = {str(item.get("fingerprint") or "") for item in current}
    return now - previous
```

Test `new_fingerprints`.

- [ ] **Step 2: Run test to verify it fails**

```powershell
python -m pytest tests/test_dashboard_health_alerts.py -v
```

- [ ] **Step 3: Implement desktop UI**

In `dashboard_view.py` (mirror `_schedule_capacity_alert_poll`):

- Schedule `_schedule_health_alert_poll` at 30s.
- `_refresh_health_alerts`: call `server.get_health_alerts()`; if alerts and not showing, open dialog listing card name + messages; buttons call server acknowledge/pause/alarm methods then refresh.
- Beep: `self.bell()` when `new_fingerprints` non-empty and card not muted.
- Do not block capacity strip; both can coexist.

- [ ] **Step 4: Run tests**

```powershell
python -m pytest tests/test_dashboard_health_alerts.py tests/test_health_alert_state.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/ui/dashboard_view.py launchpad/dashboard_health_alerts.py tests/test_dashboard_health_alerts.py
git commit -m "Add desktop critical health alert popup with acknowledge and pause."
```

---

### Task 6: Bump APP_VERSION to 1.6.155

**Files:**
- Modify: `launchpad/config.py`
- Modify: `tests/test_system_connectivity_version.py`
- Modify: `tests/test_capacity_unit_js.py`
- Modify: `tests/test_hadoop_sudo_wire.py` (`test_version_154` → `test_version_155`)

**Interfaces:**
- Produces: `APP_VERSION = "1.6.155"`

- [ ] **Step 1: Update version pins to `1.6.155`** (and rename hadoop test to `test_version_155`)

- [ ] **Step 2: Run version tests — expect FAIL vs 1.6.154**

```powershell
python -m pytest tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py::test_version_155 tests/test_capacity_unit_js.py -v
```

- [ ] **Step 3: Set `APP_VERSION = "1.6.155"` in `launchpad/config.py`**

- [ ] **Step 4: Regression**

```powershell
python -m pytest tests/test_health_alert_messages.py tests/test_health_alert_state.py tests/test_health_alerts_api.py tests/test_health_alert_page.py tests/test_dashboard_health_alerts.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py::test_version_155 tests/test_capacity_unit_js.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/config.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py tests/test_capacity_unit_js.py
git commit -m "Bump version to 1.6.155 for critical health alert popups."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Alert message fallbacks (no blank `alert ·`) | Task 1 |
| `lsdrive` + drive critical / offline-degraded promotion | Task 1 |
| Canister command `lsnodecanister` | Task 1 |
| Fingerprint + ack until clear | Task 2 |
| Pause 5/10/15/20 | Task 2–5 |
| Per-card alarm mute | Task 2–5 |
| Critical-only popups | Task 2 |
| Unreachable connectivity | Task 2–3 |
| Shared API | Task 3 |
| Browser popup | Task 4 |
| Desktop popup + beep | Task 5 |
| APP_VERSION 1.6.155 | Task 6 |
| No FC/email/collapsible/Excel | — (not planned) |
