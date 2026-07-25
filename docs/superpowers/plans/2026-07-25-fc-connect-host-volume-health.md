# FC Connect + Hosts & Volumes Health Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Connect + Open GUI on FlashCopy CGs for the selected array, and a dedicated Hosts & Volumes Health browser report that live-scans monitor-on IBM/HPE for offline/degraded hosts and volumes with Excel/CSV export.

**Architecture:** Browser POSTs to HealthServer; desktop callbacks open SSH via existing `launch_card` and GUI via `webbrowser` + card `url`. New helpers filter host/volume status; live scan reuses Volume Find eligibility and SSH runners; page at `/host-volume-health` with Site dropdown and exports.

**Tech Stack:** HealthServer HTML/JS, `launch_card` / SSH interactive, openpyxl + zipfile CSV, pytest.

**Spec:** `docs/superpowers/specs/2026-07-25-fc-connect-host-volume-health-design.md`

## Global Constraints

- **Worktree:** `.worktrees/fc-connect-host-volume-health` on `feature/fc-connect-host-volume-health` from `feature/contingency-groups` tip (merge design docs if needed)
- FC: **Connect** = dashboard SSH connect for selected `card_id`; **Open GUI** = open `card.url` (prepend `https://` if no scheme); disable/hide GUI when url empty
- Connect/Open GUI require unlock (credentials); clear 403 when locked
- Report path: **`/host-volume-health`**; title **Hosts & Volumes Health**
- Eligibility: same as Volume Find (`is_volume_find_eligible`)
- Offline/degraded: case-insensitive status contains `offline` or `degraded`
- Live refresh unlock required; Excel sheets Hosts + Volumes; CSV ZIP with hosts.csv + volumes.csv
- Nav: Connection Dashboard button **Hosts & Volumes**; Health hero link; peer links as needed
- Site dropdown: None = all
- Bump `APP_VERSION` to **1.6.66**
- Commit at each task’s commit step
- Run from: `cd C:\Users\BrianColley\LaunchPad\.worktrees\fc-connect-host-volume-health`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/host_volume_health.py` | Status filter, row builders, live-scan orchestration helpers |
| `launchpad/host_volume_health_page.py` | `HOST_VOLUME_HEALTH_PATH`, HTML/JS |
| `launchpad/host_volume_health_export.py` | Excel + CSV ZIP builders |
| `launchpad/fc_consistgrp.py` | Connect + Open GUI buttons/JS |
| `launchpad/health_server.py` | Routes, connect/gui providers, serve page, live scan, export |
| `launchpad/app.py` / `dashboard_view.py` | Wire connect provider; dashboard opener button |
| `launchpad/config.py` | `1.6.66` |
| Tests | Filter, export, API, page, FC chrome |

---

### Task 0: Confirm baseline

**Files:** none

- [ ] **Step 1: Create worktree**

```powershell
cd C:\Users\BrianColley\LaunchPad
git fetch origin
git worktree add .worktrees/fc-connect-host-volume-health -b feature/fc-connect-host-volume-health feature/contingency-groups
cd .worktrees/fc-connect-host-volume-health
# merge docs/fc-connect-host-volume-health-design if needed
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-25-fc-connect-host-volume-health-design.md
Test-Path docs\superpowers\plans\2026-07-25-fc-connect-host-volume-health.md
```

Expected: `1.6.65` (or tip), both paths `True`.

- [ ] **Step 2: No feature commit**

---

### Task 1: Offline/degraded filter helpers (TDD)

**Files:**
- Create: `launchpad/host_volume_health.py`
- Create: `tests/test_host_volume_health.py`

**Interfaces:**
- Produces:
  - `status_is_offline_or_degraded(status: str) -> bool` — True iff casefold status contains `offline` or `degraded`
  - `normalize_gui_url(url: str) -> str` — strip; if nonempty and no `://`, prepend `https://`
  - Reuse `parse_fc_hosts`, `parse_lsvdisk_volumes`, `parse_showhost_hosts`, `parse_showvv_volumes`, `is_volume_find_eligible`, `vendor_for_profile`

- [ ] **Step 1: Failing tests**

```python
from launchpad.host_volume_health import (
    normalize_gui_url,
    status_is_offline_or_degraded,
)


def test_status_offline_degraded():
    assert status_is_offline_or_degraded("offline") is True
    assert status_is_offline_or_degraded("degraded") is True
    assert status_is_offline_or_degraded("offline_unconfigured") is True
    assert status_is_offline_or_degraded("online") is False
    assert status_is_offline_or_degraded("active") is False
    assert status_is_offline_or_degraded("") is False


def test_normalize_gui_url():
    assert normalize_gui_url("10.1.2.3") == "https://10.1.2.3"
    assert normalize_gui_url("https://x") == "https://x"
    assert normalize_gui_url("  ") == ""
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement helpers**

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```powershell
git add launchpad/host_volume_health.py tests/test_host_volume_health.py
git commit -m "Add offline/degraded status helpers for host-volume health."
```

---

### Task 2: Desktop connect/GUI provider + FC page buttons

**Files:**
- Modify: `launchpad/fc_consistgrp.py`
- Modify: `launchpad/health_server.py`
- Modify: `launchpad/app.py` and/or `launchpad/ui/dashboard_view.py` (wire provider that decrypts + `launch_card` / opens URL)
- Create: `tests/test_fc_consistgrp_connect.py` (HTML contracts + API unit with mocks)

**Interfaces:**
- `HealthServer.set_card_launch_backend(connect_fn, open_gui_fn)` or single `launch_card_by_id(card_id) -> str` and `open_card_gui(card_id) -> str`
- `POST /api/fc-consistgrp/connect` body `{ "card_id": N }` → connect SSH
- `POST /api/fc-consistgrp/open-gui` body `{ "card_id": N }` → open URL; 400 if no url
- Both require `is_unlocked()` else 403
- FC HTML: buttons `#connect-btn`, `#open-gui-btn` next to Refresh; enable GUI only when selected card has url (cards payload must include `url`)

- [ ] **Step 1: Contract tests** for button ids and API unlock behavior (mock server)

- [ ] **Step 2: Implement backend + UI**

Ensure `/api/fc-consistgrp/cards` (or existing cards list used by page) includes `url` field.

- [ ] **Step 3: Commit**

```powershell
git commit -m "Add Connect and Open GUI on FlashCopy CGs page."
```

---

### Task 3: Live scan + report page (core)

**Files:**
- Create: `launchpad/host_volume_health_page.py`
- Extend: `launchpad/host_volume_health.py` with `filter_problem_hosts` / `filter_problem_volumes` from parsed rows
- Modify: `launchpad/health_server.py` — serve HTML; `POST /api/host-volume-health/live` (or GET) returning `{ hosts, volumes, errors }`

**Interfaces:**
- Path constant `HOST_VOLUME_HEALTH_PATH = "/host-volume-health"`
- Live: for each eligible card (optional `card_id` query for Site): SSH IBM lshost+lsvdisk or HPE showhost+showvv; filter by `status_is_offline_or_degraded`; include card_name, host, vendor, names, status, pool_or_cpg for volumes
- Page: Site None, Refresh live, two tables, status/errors

- [ ] **Step 1: Unit tests** for filtering parsed rows into problem lists

- [ ] **Step 2: Page HTML contract tests** (title, path, Site, Export placeholders, Refresh)

- [ ] **Step 3: Implement live scan method on HealthServer** (mirror volume-find live unlock/SSH patterns)

- [ ] **Step 4: Commit**

```powershell
git commit -m "Add Hosts & Volumes Health live scan page."
```

---

### Task 4: Excel + CSV export

**Files:**
- Create: `launchpad/host_volume_health_export.py`
- Modify: `health_server.py` — `GET /api/host-volume-health/export?format=xlsx|csv&card_id=&open=1`
- Modify: page JS Export buttons
- Create: `tests/test_host_volume_health_export.py`

**Interfaces:**
- Excel: sheets `Hosts`, `Volumes`
- CSV: ZIP with `hosts.csv`, `volumes.csv`
- Export uses last scan cache on server **or** accepts posted rows; prefer server keeps last live result in memory for export scope (document in report). Simpler: export re-runs filter on cached last payload stored on HealthServer after live scan.

- [ ] **Step 1: Export unit tests**

- [ ] **Step 2: Implement + wire buttons**

- [ ] **Step 3: Commit**

```powershell
git commit -m "Add Excel and CSV export for Hosts & Volumes Health."
```

---

### Task 5: Nav wiring

**Files:**
- Modify: `launchpad/ui/dashboard_view.py` — button **Hosts & Volumes**
- Modify: Health HTML in `health_server.py` — link
- Modify: peer pages (capacity, fc_wwpn, volume_find, fc_consistgrp) — secondary link best-effort
- Modify: `HealthServer.open_host_volume_health()` + dashboard opener

- [ ] **Step 1: Contract tests** for dashboard method / HTML href `/host-volume-health`

- [ ] **Step 2: Implement**

- [ ] **Step 3: Commit**

```powershell
git commit -m "Add Hosts & Volumes nav from dashboard and Health."
```

---

### Task 6: Version 1.6.66

**Files:**
- Modify: `launchpad/config.py`

- [ ] **Step 1:** `APP_VERSION = "1.6.66"`

- [ ] **Step 2:** Run related pytest suites

- [ ] **Step 3: Commit**

```powershell
git commit -m "Bump version to 1.6.66 for FC Connect and host-volume health."
```

---

### Task 7: Final review + PR

- [ ] Full related suite green
- [ ] Spec checklist
- [ ] PR into `feature/contingency-groups`

```powershell
git push -u origin HEAD
gh pr create --base feature/contingency-groups --title "FC Connect + Hosts & Volumes Health (v1.6.66)" --body "## Summary
- FlashCopy CGs: Connect (SSH) + Open GUI for selected array
- New /host-volume-health live offline/degraded hosts & volumes (IBM+HPE)
- Excel + CSV ZIP export; dashboard + Health nav
- Version 1.6.66

## Test plan
- [ ] pytest related suites
- [ ] FC page: Connect SSH; Open GUI when URL set
- [ ] Report Refresh live; Site filter; Excel/CSV
"
```

---

## Spec coverage (self-review)

| Spec item | Task |
|-----------|------|
| FC Connect SSH | 2 |
| FC Open GUI | 2 |
| Status filter offline/degraded | 1 |
| Live scan IBM+HPE | 3 |
| Page + Site dropdown | 3 |
| Excel/CSV | 4 |
| Dashboard + Health nav | 5 |
| Version 1.6.66 | 6 |

**Placeholder scan:** none intentional.  
**Locked path:** `/host-volume-health`. **Button label:** Hosts & Volumes.
