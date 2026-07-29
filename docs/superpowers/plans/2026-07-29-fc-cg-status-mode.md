# FlashCopy CGs Status Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Manage | Status dual mode on `/fc-consistgrp`: multi-site live CG status tabs (All / Idle or Copied / Stopped / Copying) and Excel export of the active tab’s rows (v**1.6.80**).

**Architecture:** Keep existing Manage single-array inventory/mutations. Status mode scans monitor-on FlashSystem/SVC cards (site filter or all), caches rows, filters by status bucket in the UI, and exports filtered rows via a new xlsx helper. Copy System Connectivity / Host Volume Health live+cache+export patterns.

**Tech Stack:** Python, HealthServer SSH (`_snap_run_command`), openpyxl, pytest.

**Spec:** `docs/superpowers/specs/2026-07-29-fc-cg-status-mode-design.md`

## Global Constraints

- **Worktree:** `.worktrees/fc-cg-status-mode` on `feature/fc-cg-status-mode` from `feature/contingency-groups` tip (include design `04a3285` / merge tip with `1.6.79`+)
- Dual mode on `/fc-consistgrp`: **Manage** (unchanged behavior) | **Status** (new)
- Status eligibility: `monitor_on` + SSH + `is_svc_fc_profile(profile)` only (no HPE/DS8884)
- Tabs: All / Idle or Copied / Stopped / Copying; Export Excel = **active tab rows only**
- One row per CG per card; stand-alone maps out of scope
- No Status-mode mutations (start/stop/delete)
- Bump `APP_VERSION` to **1.6.80**
- Commit at each task’s commit step
- Run from: `cd C:\Users\BrianColley\LaunchPad\.worktrees\fc-cg-status-mode`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/fc_consistgrp_ops.py` | `normalize_fc_cg_status_bucket`, optional flash_time field, eligibility helper |
| `launchpad/fc_consistgrp_status_export.py` | Build xlsx bytes for status rows |
| `launchpad/fc_consistgrp.py` | Mode toggle, Status UI (site/refresh/tabs/table/export), JS |
| `launchpad/health_server.py` | `scan_fc_consistgrp_status_live`, cache, export route, GET APIs |
| `launchpad/config.py` | `1.6.80` |
| Tests | Bucket unit, page markers, API live/export, version |

---

### Task 0: Confirm baseline

**Files:** none

- [ ] **Step 1: Create worktree**

```powershell
cd C:\Users\BrianColley\LaunchPad
git worktree add .worktrees/fc-cg-status-mode -b feature/fc-cg-status-mode feature/contingency-groups
cd .worktrees\fc-cg-status-mode
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-29-fc-cg-status-mode-design.md
```

Expected: tip ≥ `1.6.79`, spec `True`.

- [ ] **Step 2: No feature commit**

---

### Task 1: Status bucketing + eligibility (TDD)

**Files:**
- Modify: `launchpad/fc_consistgrp_ops.py`
- Create/Modify: `tests/test_fc_consistgrp_ops.py` (extend)

**Interfaces:**
- Produces:
  - `normalize_fc_cg_status_bucket(status: str) -> str` — returns one of `"idle_or_copied"`, `"stopped"`, `"copying"`, or `""` (unknown → empty; only appears under All)
  - `is_fc_consistgrp_status_eligible(card: dict | object) -> bool` — monitor_on + ssh + `is_svc_fc_profile`
  - Optionally extend `parse_lsfcconsistgrp` to include `flash_time` when CLI field present (blank otherwise)

- [ ] **Step 1: Failing tests**

```python
from launchpad.fc_consistgrp_ops import normalize_fc_cg_status_bucket


def test_normalize_idle_or_copied_variants():
    assert normalize_fc_cg_status_bucket("idle_or_copied") == "idle_or_copied"
    assert normalize_fc_cg_status_bucket("Idle or Copied") == "idle_or_copied"


def test_normalize_stopped_and_copying():
    assert normalize_fc_cg_status_bucket("stopped") == "stopped"
    assert normalize_fc_cg_status_bucket("Copying") == "copying"


def test_normalize_unknown_empty():
    assert normalize_fc_cg_status_bucket("weird_state") == ""
    assert normalize_fc_cg_status_bucket("") == ""
```

Add eligibility tests with simple fake card dicts (`monitor_on`, `card_type`, `device_profile`).

- [ ] **Step 2: Run — FAIL** then implement — PASS

```powershell
python -m pytest tests/test_fc_consistgrp_ops.py -q --tb=short
```

- [ ] **Step 3: Commit**

```powershell
git add launchpad/fc_consistgrp_ops.py tests/test_fc_consistgrp_ops.py
git commit -m "Add FlashCopy CG status bucket normalizer and Status eligibility."
```

---

### Task 2: Status export helper (TDD)

**Files:**
- Create: `launchpad/fc_consistgrp_status_export.py`
- Create: `tests/test_fc_consistgrp_status_export.py`

**Interfaces:**
- Produces:
  - `STATUS_HEADERS` / field keys matching: Site, Card, Host, CG name, Status, Maps, Flash time, Error
  - `filter_status_rows(rows, *, bucket: str) -> list` — `bucket` in `("", "all", "idle_or_copied", "stopped", "copying")`; empty/`all` returns all
  - `export_fc_consistgrp_status_xlsx(rows: list[dict]) -> bytes` — sheet name `FC CG Status`

- [ ] **Step 1: Failing tests** for filter + xlsx sheet/headers/row values

- [ ] **Step 2: Implement → PASS → Commit**

```powershell
git add launchpad/fc_consistgrp_status_export.py tests/test_fc_consistgrp_status_export.py
git commit -m "Add FlashCopy CG Status Excel export helper."
```

---

### Task 3: HealthServer live scan + cache + API routes (TDD)

**Files:**
- Modify: `launchpad/health_server.py`
- Create/Modify: `tests/test_health_server_fc_consistgrp.py` or `tests/test_fc_consistgrp_status_api.py`

**Interfaces:**
- Produces:
  - `scan_fc_consistgrp_status_live(self, *, card_id: int | None = None) -> dict` with `rows: list[dict]`, `errors: list`
  - Each row: `site`, `card_name`, `host`, `name` (CG), `status`, `map_count`, `flash_time`, `error`, `card_id`, `bucket` (normalized)
  - Cache get/set; `export_fc_consistgrp_status_bytes(self, *, format, card_id=None, bucket="all")`
  - GET `/api/fc-consistgrp/status/live` (403 if locked; optional `?card_id=`)
  - GET `/api/fc-consistgrp/status/export?format=xlsx&bucket=...&card_id=...&open=1`

Scan loop:
1. `sync_from_app()`; select monitor-on eligible cards (filter by `card_id` if set — treat as site/card filter like SC: when UI passes card_id for a site’s first card OR pass site name — prefer matching SC: site filter is client-side by filtering cards list, live endpoint uses optional `card_id` for single card OR no param for all eligible).
2. For each eligible card: `collect_fc_consistgrp_inventory` via `_snap_run_command` (groups only needed; maps optional — prefer groups-only path if easy, else reuse full collect and ignore maps).
3. On failure: append error string; optionally add a placeholder row with Error set; continue.

- [ ] **Step 1: API tests** unlock required; happy path with mocked `_snap_run_command` returning `idle_or_copied` / `stopped` fixtures; export requires prior scan

- [ ] **Step 2: Implement → PASS → Commit**

```powershell
git add launchpad/health_server.py tests/test_fc_consistgrp_status_api.py
git commit -m "Add FlashCopy CG Status live scan and export APIs."
```

---

### Task 4: Page UI — Manage | Status mode (TDD)

**Files:**
- Modify: `launchpad/fc_consistgrp.py`
- Modify: `tests/test_fc_consistgrp_page.py`

**Interfaces:**
- Produces HTML/JS:
  - Mode toggle buttons `Manage` / `Status` (`data-mode` or similar)
  - Status panel (hidden in Manage): site select, Refresh live, Export Excel, tabs All / Idle or Copied / Stopped / Copying, table body
  - Manage sections hidden when Status active
  - JS: load sites from `/api/fc-consistgrp/cards` or `/api/cards` (prefer cards API; if cards lack site, extend `fc_consistgrp_cards()` to include `site`, `monitor_on`, `device_profile` for client filtering — **do this in Task 3/4 as needed**)
  - `refreshStatusLive()` → `/api/fc-consistgrp/status/live`
  - Tab click filters client-side by `bucket`
  - Export → `/api/fc-consistgrp/status/export?format=xlsx&bucket=<active>&open=1`

- [ ] **Step 1: Page tests** assert mode labels, tab labels, export control, API path strings in HTML

- [ ] **Step 2: Implement UI → PASS → Commit**

```powershell
git add launchpad/fc_consistgrp.py tests/test_fc_consistgrp_page.py launchpad/health_server.py
git commit -m "Add Manage/Status dual mode UI to FlashCopy CGs page."
```

---

### Task 5: Version bump to 1.6.80

**Files:**
- Modify: `launchpad/config.py`
- Modify: `tests/test_system_connectivity_version.py` (or dedicated version assert used by project)

- [ ] **Step 1:** Assert `1.6.80` (RED) → set `APP_VERSION = "1.6.80"` (GREEN)

- [ ] **Step 2: Commit**

```powershell
git add launchpad/config.py tests/test_system_connectivity_version.py
git commit -m "Bump LaunchPad to 1.6.80 for FlashCopy CGs Status mode."
```

---

### Task 6: Final verification

```powershell
python -m pytest tests/test_fc_consistgrp_ops.py tests/test_fc_consistgrp_status_export.py tests/test_fc_consistgrp_status_api.py tests/test_fc_consistgrp_page.py tests/test_health_server_fc_consistgrp.py tests/test_system_connectivity_version.py -q --tb=short
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
```

Expected: PASS, `1.6.80`. No commit unless fixes.

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Manage \| Status dual mode | 4 |
| Site / All + Refresh live | 3–4 |
| Status tabs + bucketing | 1, 4 |
| Export current tab only | 2–4 |
| SVC/FlashSystem only | 1, 3 |
| Per-card error continue | 3 |
| Version 1.6.80 | 5 |
| No Status mutations / no stand-alone maps | Global |
