# Dashboard Capacity Alerts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show capacity warn/critical alerts on the main Connection Dashboard via a clickable top strip and per-SSH-card CRIT/WARN badges, using the last Health Server snapshot (no extra SSH).

**Architecture:** Pure helpers in a small module derive capacity issues, per-card severity, and fleet counts from Health Server `list_cards()` payloads plus monitor state. `GlowCard` renders a capacity badge; `DashboardView` shows a compact alert strip under the tool buttons, polls Health Server in-process on a timer, and opens Capacity Report on strip click.

**Tech Stack:** Python 3, CustomTkinter, in-process `get_health_server().list_cards(allow_sync=False)`, pytest.

**Spec:** `docs/superpowers/specs/2026-08-03-dashboard-capacity-alerts-design.md`

## Global Constraints

- **Branch:** continue on `feature/hpe-capacity-parse` (capacity issue detection + Capacity Report banners already in progress). Do **not** create a separate worktree unless the branch tip is unavailable.
- **Data source only:** last Health Server snapshot `health_issues` — no new background `showcpg`/SSH from the desktop UI.
- **Thresholds:** ≥80% warn, ≥90% critical (unchanged; 82% stays warn).
- **Monitor-on only:** ignore Monitor-off cards for strip counts and badges.
- **Never refreshed:** if `updated_at` is missing/empty, no badge and no strip contribution for that card.
- **Strip click:** opens Capacity Report (same path as existing Capacity Report tool button).
- **Badge scope v1:** capacity issues only (not node/CPU/alert categories).
- Bump `APP_VERSION` to **1.6.101** in the final task (after confirming 1.6.100 capacity-banner work is already on the branch or included).
- Commit at each task’s commit step.
- Run from: `cd C:\Users\BrianColley\LaunchPad` (or the active `feature/hpe-capacity-parse` checkout).

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/dashboard_capacity_alerts.py` | Pure helpers: filter capacity issues, card severity, fleet summary text/counts |
| `tests/test_dashboard_capacity_alerts.py` | Unit tests for helpers |
| `launchpad/ui/card_widget.py` | CRIT/WARN capacity badge on SSH GlowCards |
| `launchpad/ui/dashboard_view.py` | Alert strip UI, poll timer, apply badges, strip → Capacity Report |
| `launchpad/config.py` | `APP_VERSION = "1.6.101"` |
| `tests/test_dashboard_capacity_alerts_ui.py` | String/contract checks that strip wiring and badge API exist |

---

### Task 1: Pure capacity-alert helpers

**Files:**
- Create: `launchpad/dashboard_capacity_alerts.py`
- Create: `tests/test_dashboard_capacity_alerts.py`

**Interfaces:**
- Produces:
  - `is_capacity_issue(issue: dict) -> bool`
  - `filter_capacity_issues(issues: list[dict] | None) -> list[dict]`
  - `card_capacity_severity(issues: list[dict] | None, *, monitor_on: bool, updated_at: str | None) -> str | None`
    - returns `"critical"`, `"warn"`, or `None`
  - `fleet_capacity_alert_summary(cards: list[dict], monitor_states: dict[int, bool]) -> dict`
    - returns `{"critical_sites": int, "warn_sites": int, "label": str, "has_alert": bool}`
    - a site counts as critical if any capacity issue is critical; else warn if any capacity warn; monitor-off / no `updated_at` skipped
  - `CAPACITY_ALERT_POLL_MS = 30_000`

- [ ] **Step 1: Write the failing tests**

```python
from launchpad.dashboard_capacity_alerts import (
    card_capacity_severity,
    filter_capacity_issues,
    fleet_capacity_alert_summary,
    is_capacity_issue,
)


def test_is_capacity_issue_by_category_and_message():
    assert is_capacity_issue({"category": "capacity", "message": "x", "severity": "warn"})
    assert is_capacity_issue(
        {"category": "other", "message": "Pool CPG_OS01 is 82.3% full", "severity": "warn"}
    )
    assert is_capacity_issue(
        {"category": "other", "message": "Running at 91.0% capacity", "severity": "critical"}
    )
    assert not is_capacity_issue(
        {"category": "node", "message": "Node 1 offline", "severity": "critical"}
    )


def test_card_severity_critical_wins_and_gates():
    issues = [
        {"category": "capacity", "severity": "warn", "message": "Pool A is 82.0% full"},
        {"category": "capacity", "severity": "critical", "message": "Pool B is 98.0% full"},
    ]
    assert card_capacity_severity(issues, monitor_on=True, updated_at="2026-08-03") == "critical"
    assert card_capacity_severity(issues, monitor_on=False, updated_at="2026-08-03") is None
    assert card_capacity_severity(issues, monitor_on=True, updated_at=None) is None
    assert (
        card_capacity_severity(
            [{"category": "capacity", "severity": "warn", "message": "Pool A is 82.0% full"}],
            monitor_on=True,
            updated_at="2026-08-03",
        )
        == "warn"
    )


def test_fleet_summary_counts_sites_not_issues():
    cards = [
        {
            "id": 1,
            "name": "A",
            "updated_at": "t",
            "health_issues": [
                {"category": "capacity", "severity": "critical", "message": "Pool X is 99% full"},
                {"category": "capacity", "severity": "warn", "message": "Pool Y is 81% full"},
            ],
        },
        {
            "id": 2,
            "name": "B",
            "updated_at": "t",
            "health_issues": [
                {"category": "capacity", "severity": "warn", "message": "Pool Z is 82% full"},
            ],
        },
        {
            "id": 3,
            "name": "C",
            "updated_at": "t",
            "health_issues": [
                {"category": "capacity", "severity": "warn", "message": "Pool W is 85% full"},
            ],
        },
    ]
    summary = fleet_capacity_alert_summary(cards, {1: True, 2: True, 3: False})
    assert summary["critical_sites"] == 1
    assert summary["warn_sites"] == 1  # id 2 only; id 3 monitor off
    assert summary["has_alert"] is True
    assert "CRITICAL" in summary["label"]
    assert "WARNING" in summary["label"]


def test_fleet_summary_hidden_when_empty():
    summary = fleet_capacity_alert_summary(
        [{"id": 1, "updated_at": "t", "health_issues": []}],
        {1: True},
    )
    assert summary["has_alert"] is False
    assert summary["label"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dashboard_capacity_alerts.py -v`

Expected: FAIL with `ModuleNotFoundError` or import error for `launchpad.dashboard_capacity_alerts`.

- [ ] **Step 3: Minimal implementation**

Create `launchpad/dashboard_capacity_alerts.py`:

```python
"""Derive Connection Dashboard capacity alert badges/strip from Health Server cards."""

from __future__ import annotations

import re
from typing import Any

CAPACITY_ALERT_POLL_MS = 30_000

_CAPACITY_MSG_RE = re.compile(
    r"%\s*(full|capacity)|running at\s+\d",
    re.IGNORECASE,
)


def is_capacity_issue(issue: dict[str, Any] | None) -> bool:
    if not issue:
        return False
    if str(issue.get("category") or "").lower() == "capacity":
        return True
    return bool(_CAPACITY_MSG_RE.search(str(issue.get("message") or "")))


def filter_capacity_issues(issues: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [issue for issue in (issues or []) if is_capacity_issue(issue)]


def card_capacity_severity(
    issues: list[dict[str, Any]] | None,
    *,
    monitor_on: bool,
    updated_at: str | None,
) -> str | None:
    if not monitor_on or not (updated_at or "").strip():
        return None
    capacity = filter_capacity_issues(issues)
    if not capacity:
        return None
    if any(str(issue.get("severity") or "").lower() == "critical" for issue in capacity):
        return "critical"
    return "warn"


def fleet_capacity_alert_summary(
    cards: list[dict[str, Any]],
    monitor_states: dict[int, bool],
) -> dict[str, Any]:
    critical_sites = 0
    warn_sites = 0
    for card in cards:
        card_id = int(card.get("id") or card.get("card_id") or 0)
        severity = card_capacity_severity(
            card.get("health_issues"),
            monitor_on=bool(monitor_states.get(card_id, False)),
            updated_at=card.get("updated_at"),
        )
        if severity == "critical":
            critical_sites += 1
        elif severity == "warn":
            warn_sites += 1
    has_alert = critical_sites > 0 or warn_sites > 0
    if not has_alert:
        label = ""
    else:
        parts: list[str] = []
        if critical_sites:
            parts.append(f"CRITICAL capacity: {critical_sites} site(s)")
        if warn_sites:
            parts.append(f"WARNING: {warn_sites} site(s)")
        label = " · ".join(parts)
    return {
        "critical_sites": critical_sites,
        "warn_sites": warn_sites,
        "label": label,
        "has_alert": has_alert,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dashboard_capacity_alerts.py -v`

Expected: all PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/dashboard_capacity_alerts.py tests/test_dashboard_capacity_alerts.py
git commit -m "Add helpers for Connection Dashboard capacity alert strip and badges."
```

---

### Task 2: GlowCard capacity badge

**Files:**
- Modify: `launchpad/ui/card_widget.py`
- Modify: `tests/test_dashboard_capacity_alerts_ui.py` (create)

**Interfaces:**
- Consumes: severity `"critical"` | `"warn"` | `None`; optional tooltip messages
- Produces: `GlowCard.set_capacity_alert(severity: str | None, messages: list[str] | None = None) -> None`
  - Shows a small label badge `CRIT` (red `#ef4444`) or `WARN` (amber `#f59e0b`) near the type badge
  - Hides badge when `severity` is `None`
  - Tooltip / status tip lists joined messages when present
  - Does **not** change SSH status LED behavior

- [ ] **Step 1: Write failing UI contract test**

```python
from pathlib import Path

CARD = Path("launchpad/ui/card_widget.py").read_text(encoding="utf-8")


def test_glowcard_has_set_capacity_alert():
    assert "def set_capacity_alert(" in CARD
    assert "CRIT" in CARD
    assert "WARN" in CARD
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_dashboard_capacity_alerts_ui.py::test_glowcard_has_set_capacity_alert -v`

Expected: FAIL (file missing or assertion fails).

- [ ] **Step 3: Implement badge on GlowCard**

In `launchpad/ui/card_widget.py`:

1. After `self.type_badge` is created, add:

```python
self.capacity_alert_badge = ctk.CTkLabel(
    top_row,
    text="",
    font=ctk.CTkFont(size=10, weight="bold"),
    text_color="#111111",
    fg_color=theme["surface"],
    corner_radius=8,
    width=44,
    height=20,
)
# Place to the left of type_badge (shift type_badge column if needed), initially grid_remove()
self.capacity_alert_badge.grid(row=0, column=4, sticky="e", padx=(4, 4))
self.capacity_alert_badge.grid_remove()
self.type_badge.grid(row=0, column=5, sticky="e")
# If drag_handle exists, keep it at column 6
```

Adjust column indexes carefully so select / icon / name / expand / capacity badge / type badge / drag handle still fit. Prefer inserting capacity badge immediately before `type_badge`.

2. Add method:

```python
def set_capacity_alert(
    self,
    severity: str | None,
    messages: list[str] | None = None,
) -> None:
    if not hasattr(self, "capacity_alert_badge") or self.capacity_alert_badge is None:
        return
    if severity not in {"critical", "warn"}:
        self.capacity_alert_badge.grid_remove()
        self.capacity_alert_badge.configure(text="")
        return
    is_critical = severity == "critical"
    self.capacity_alert_badge.configure(
        text="CRIT" if is_critical else "WARN",
        fg_color="#ef4444" if is_critical else "#f59e0b",
        text_color="#ffffff" if is_critical else "#111111",
    )
    self.capacity_alert_badge.grid()
    tip = "\n".join(m for m in (messages or []) if m).strip()
    if tip:
        self._capacity_alert_tip = tip
    else:
        self._capacity_alert_tip = (
            "Critical capacity on this site" if is_critical else "Capacity warning on this site"
        )
```

3. Bind Enter/Leave on the badge to show `_capacity_alert_tip` using the same tip helper as the SSH status LED if one exists (`_show_status_tip` / `_hide_status_tip`). If those helpers require `status_led`, add a small dedicated tip for the badge mirroring that pattern.

4. In `apply_theme`, re-apply current capacity badge colors if a severity is stored on `self._capacity_alert_severity`.

- [ ] **Step 4: Run contract test**

Run: `python -m pytest tests/test_dashboard_capacity_alerts_ui.py::test_glowcard_has_set_capacity_alert -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/ui/card_widget.py tests/test_dashboard_capacity_alerts_ui.py
git commit -m "Add CRIT/WARN capacity badge to SSH connection cards."
```

---

### Task 3: Dashboard strip + poll + badge wiring

**Files:**
- Modify: `launchpad/ui/dashboard_view.py`
- Modify: `tests/test_dashboard_capacity_alerts_ui.py`

**Interfaces:**
- Consumes:
  - `get_health_server().list_cards(allow_sync=False)`
  - `get_monitor_states()` / `self._monitor_states`
  - `fleet_capacity_alert_summary`, `card_capacity_severity`, `filter_capacity_issues`, `CAPACITY_ALERT_POLL_MS`
  - `GlowCard.set_capacity_alert`
  - existing `_open_capacity_report_all`
- Produces:
  - Compact alert strip widget under header tools (or above filters), hidden when no alerts
  - Click / button on strip calls `_open_capacity_report_all`
  - `_refresh_capacity_alerts()` applies strip + per-card badges
  - Timer every `CAPACITY_ALERT_POLL_MS` while dashboard is alive; cancel on `refresh_cards` teardown like other timers
  - Also call `_refresh_capacity_alerts()` after monitor toggles and after Capacity/Health open workers finish (best-effort `after(0, ...)`)

- [ ] **Step 1: Extend failing UI contract tests**

Append to `tests/test_dashboard_capacity_alerts_ui.py`:

```python
from pathlib import Path

DASH = Path("launchpad/ui/dashboard_view.py").read_text(encoding="utf-8")


def test_dashboard_wires_capacity_alert_strip():
    assert "_refresh_capacity_alerts" in DASH
    assert "fleet_capacity_alert_summary" in DASH
    assert "CAPACITY_ALERT_POLL_MS" in DASH
    assert "set_capacity_alert" in DASH
```

- [ ] **Step 2: Run tests to verify new assertions fail**

Run: `python -m pytest tests/test_dashboard_capacity_alerts_ui.py -v`

Expected: FAIL on missing `_refresh_capacity_alerts` until implemented.

- [ ] **Step 3: Build strip UI in `_build_header` (or immediately after tools)**

After the tools frame in `_build_header`, add a full-width strip:

```python
self.capacity_alert_strip = ctk.CTkFrame(
    header,
    fg_color="#7f1d1d",
    corner_radius=10,
    border_width=1,
    border_color="#ef4444",
)
self.capacity_alert_strip.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))
self.capacity_alert_strip.grid_columnconfigure(0, weight=1)
self.capacity_alert_label = ctk.CTkLabel(
    self.capacity_alert_strip,
    text="",
    text_color="#fecaca",
    font=ctk.CTkFont(size=13, weight="bold"),
    anchor="w",
)
self.capacity_alert_label.grid(row=0, column=0, padx=12, pady=8, sticky="ew")
self.capacity_alert_btn = ctk.CTkButton(
    self.capacity_alert_strip,
    text="Open Capacity Report",
    width=170,
    fg_color="#ef4444",
    hover_color="#dc2626",
    command=self._open_capacity_report_all,
)
self.capacity_alert_btn.grid(row=0, column=1, padx=12, pady=8)
self.capacity_alert_strip.grid_remove()
```

When only warnings (no criticals), restyle strip to amber (`#78350f` / `#f59e0b` / `#fde68a`) inside `_refresh_capacity_alerts`.

- [ ] **Step 4: Implement refresh + timer**

In `DashboardView.__init__` (near other timers):

```python
self._capacity_alert_timer: str | None = None
```

Add methods:

```python
def _schedule_capacity_alert_poll(self) -> None:
    if self._capacity_alert_timer:
        self.after_cancel(self._capacity_alert_timer)
    from launchpad.dashboard_capacity_alerts import CAPACITY_ALERT_POLL_MS
    self._capacity_alert_timer = self.after(
        CAPACITY_ALERT_POLL_MS, self._on_capacity_alert_timer
    )

def _on_capacity_alert_timer(self) -> None:
    self._capacity_alert_timer = None
    self._refresh_capacity_alerts()
    self._schedule_capacity_alert_poll()

def _refresh_capacity_alerts(self) -> None:
    from launchpad.dashboard_capacity_alerts import (
        card_capacity_severity,
        filter_capacity_issues,
        fleet_capacity_alert_summary,
    )
    from launchpad.health_server import get_health_server

    try:
        server = get_health_server()
        cards = server.list_cards(allow_sync=False)
    except Exception:
        cards = []
    monitor_states = dict(self._monitor_states)
    summary = fleet_capacity_alert_summary(cards, monitor_states)
    by_id = {int(c.get("id")): c for c in cards if c.get("id") is not None}

    if summary["has_alert"]:
        critical = summary["critical_sites"] > 0
        self.capacity_alert_strip.configure(
            fg_color="#7f1d1d" if critical else "#78350f",
            border_color="#ef4444" if critical else "#f59e0b",
        )
        self.capacity_alert_label.configure(
            text=summary["label"],
            text_color="#fecaca" if critical else "#fde68a",
        )
        self.capacity_alert_btn.configure(
            fg_color="#ef4444" if critical else "#f59e0b",
            hover_color="#dc2626" if critical else "#d97706",
            text_color="#ffffff" if critical else "#111111",
        )
        self.capacity_alert_strip.grid()
    else:
        self.capacity_alert_strip.grid_remove()

    for widget in self.card_widgets:
        payload = by_id.get(widget.card_id)
        if not payload:
            widget.set_capacity_alert(None)
            continue
        severity = card_capacity_severity(
            payload.get("health_issues"),
            monitor_on=self._is_monitor_on(widget.card_id),
            updated_at=payload.get("updated_at"),
        )
        messages = [
            str(i.get("message") or "")
            for i in filter_capacity_issues(payload.get("health_issues"))
        ]
        widget.set_capacity_alert(severity, messages)
```

Wire:

1. End of `refresh_cards` (after widgets built): `self._refresh_capacity_alerts(); self._schedule_capacity_alert_poll()`
2. Cancel `_capacity_alert_timer` in the same place `_stats_timer` / `_ssh_status_timer` are cancelled at the start of `refresh_cards`
3. After successful monitor toggle handlers: `self._refresh_capacity_alerts()`
4. After Capacity Report / Health Dashboard worker success callbacks: `self.after(0, self._refresh_capacity_alerts)`

Do not start SSH refresh from this poll.

- [ ] **Step 5: Run UI + helper tests**

Run:

```powershell
python -m pytest tests/test_dashboard_capacity_alerts.py tests/test_dashboard_capacity_alerts_ui.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```powershell
git add launchpad/ui/dashboard_view.py tests/test_dashboard_capacity_alerts_ui.py
git commit -m "Show capacity alert strip and card badges on Connection Dashboard."
```

---

### Task 4: Version bump + verification

**Files:**
- Modify: `launchpad/config.py` (`APP_VERSION = "1.6.101"`)

**Interfaces:**
- Consumes: Tasks 1–3 complete; capacity issue detection from analyze_health available on branch
- Produces: shipped version string 1.6.101

- [ ] **Step 1: Confirm prerequisite capacity issues exist**

Run:

```powershell
python -c "from launchpad.flashsystem_health import analyze_health; o='Id,Name,Warn%,VVs,TPVVs,TDVVs,Usr,Snp,Base,Free,Total\n3,CPG_DATA01,-,7,7,0,7,7,13680640,162000,13842640\n'; a=analyze_health('t',[{'label':'Capacity - CPG %','command':'showcpg','output':o,'error':None}],None); print([(i['severity'], i['message']) for i in a['health_issues'] if i['category']=='capacity'])"
```

Expected: at least one `critical` capacity issue for ~98.8% pool.

- [ ] **Step 2: Bump version**

Set `APP_VERSION = "1.6.101"` in `launchpad/config.py`.

- [ ] **Step 3: Run focused regression suite**

```powershell
python -m pytest tests/test_dashboard_capacity_alerts.py tests/test_dashboard_capacity_alerts_ui.py tests/test_hpe_capacity_parse.py tests/test_capacity_report_site.py -q
```

Expected: all PASS.

- [ ] **Step 4: Manual check list (operator)**

1. Unlock LaunchPad; turn Monitor on for an HPE site that is ≥80%.
2. Open Capacity Report and Refresh so Health Server gets `updated_at` + issues.
3. Return to Connection Dashboard without closing LaunchPad.
4. Confirm top strip shows WARNING and/or CRITICAL counts.
5. Confirm that site’s card shows `WARN` or `CRIT`.
6. Click **Open Capacity Report** on the strip — Capacity Report opens.
7. Turn Monitor off for that card — badge clears; strip recounts.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version to 1.6.101 for Connection Dashboard capacity alerts."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Top alert strip with critical/warn site counts | Task 3 |
| Strip click opens Capacity Report | Task 3 |
| Per SSH card CRIT/WARN badge + tooltip messages | Task 2–3 |
| Monitor-on + refreshed-only gating | Task 1 helpers |
| Reuse Health Server snapshot / no extra SSH | Tasks 1, 3 |
| ≥80 warn / ≥90 critical unchanged | Task 1 (severity from existing issues) |
| Poll while Health Server reachable | Task 3 timer |
| Unit tests for counts/severity | Task 1 |
| UI contract / wiring tests | Tasks 2–3 |
| Version 1.6.101+ | Task 4 |

## Placeholder / consistency self-review

- No TBD/TODO placeholders.
- Helper names (`card_capacity_severity`, `fleet_capacity_alert_summary`, `set_capacity_alert`, `_refresh_capacity_alerts`) are consistent across tasks.
- Poll constant `CAPACITY_ALERT_POLL_MS` defined once in the helper module and imported by the dashboard.
