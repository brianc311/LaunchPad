# Snapcopy Summary Page + Data Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move multi-site Array FlashCopy CG summary to a dedicated Snapcopy Summary page, fix Site/Host/Policy/Flash-time display, and keep checked-row multi-sheet Excel export working (v**1.6.86**).

**Architecture:** New HealthServer page module (Hosts & Volumes pattern). Reuse `scan_fc_cg_summary_live` + `export-selected`. Fix live-scan **site = card.name**; compose **Policy** from Snapshot Schedule label + array fields in `build_cg_summaries`; add **Host** column (`https://{host}` in UI). Remove embedded summary from Consistency Groups; add Snapcopy Summary nav button.

**Tech Stack:** Python, HealthServer, openpyxl, pytest.

**Spec:** `docs/superpowers/specs/2026-07-30-snapcopy-summary-page-design.md`

## Global Constraints

- **Worktree:** `.worktrees/snapcopy-summary` on `feature/snapcopy-summary` from `feature/contingency-groups` tip (≥ `1.6.85` + this spec)
- Site column = **card name** (never category like `General`)
- Host link = `https://{host}` new tab (GUI only; no SSH Connect)
- Policy = schedule **label** primary, then array policy fields with ` · `
- Export = checked rows only; one sheet per site; Refresh fills cache first
- Entry = Consistency Groups button only (no dashboard button)
- Bump `APP_VERSION` to **1.6.86**
- Commit per task; run from worktree
- Operator install folder note: `C:\Users\BrianColley\LaunchPad\LaunchPad-install`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/fc_cg_summary.py` | `compose_cg_policy_display`; Policy in `build_cg_summaries` |
| `launchpad/fc_cg_summary_export.py` | Add Host column after Site |
| `launchpad/health_server.py` | `site = card.name` in live scan; serve `/snapcopy-summary`; `open_snapcopy_summary()` |
| `launchpad/snapcopy_summary_page.py` | New page HTML/JS (moved UI) |
| `launchpad/contingency_groups.py` | Remove summary section; add Snapcopy Summary button |
| `launchpad/config.py` | `1.6.86` |
| Tests | Policy compose, live site/policy, export Host, page markers, contingency cleanup, version |

---

### Task 0: Confirm baseline

```powershell
cd C:\Users\BrianColley\LaunchPad
git worktree add .worktrees/snapcopy-summary -b feature/snapcopy-summary feature/contingency-groups
cd .worktrees\snapcopy-summary
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-30-snapcopy-summary-page-design.md
```

Expected: `1.6.85` (or higher), spec `True`. No feature commit.

---

### Task 1: Policy compose + Site = card name + Host in Excel (TDD)

**Files:**
- Modify: `launchpad/fc_cg_summary.py`
- Modify: `launchpad/fc_cg_summary_export.py`
- Modify: `launchpad/health_server.py` (`scan_fc_cg_summary_live` site line)
- Modify: `tests/test_fc_cg_summary.py`
- Modify: `tests/test_fc_cg_summary_export.py`
- Modify: `tests/test_fc_cg_summary_multisite_api.py`

**Interfaces:**
- Add `compose_cg_policy_display(*, array_policy: str = "", schedule: dict | None = None) -> str`
  - Schedule label from `schedule.get("label")` if dict
  - Non-empty label, then non-empty array_policy, joined with ` · `
- `build_cg_summaries`: set `"policy"` via `compose_cg_policy_display(array_policy=group.get("policy") or "", schedule=schedule)`
- `scan_fc_cg_summary_live`: `site = str(card.name or "").strip() or "Unknown"` (do **not** use `card.category`)
- Export: insert `"Host"` / `"host"` immediately after Site in `SUMMARY_HEADERS` / `SUMMARY_FIELDS`

- [ ] **Step 1: Failing tests**

```python
# tests/test_fc_cg_summary.py
def test_compose_cg_policy_schedule_then_array():
    assert compose_cg_policy_display(
        array_policy="50 · enabled",
        schedule={"label": "WEEKLY"},
    ) == "WEEKLY · 50 · enabled"
    assert compose_cg_policy_display(array_policy="", schedule={"label": "WEEKLY"}) == "WEEKLY"
    assert compose_cg_policy_display(array_policy="50", schedule=None) == "50"
    assert compose_cg_policy_display() == ""

def test_build_cg_summaries_policy_includes_schedule_label():
    groups = [{"name": "CG1", "status": "idle_or_copied", "policy": "50"}]
    rows = build_cg_summaries(
        groups=groups, maps=[], host_maps=[],
        schedule={"days": 7, "held": False, "label": "WEEKLY"},
    )
    assert rows[0]["policy"] == "WEEKLY · 50"
```

```python
# tests/test_fc_cg_summary_multisite_api.py — in mocked live scan happy path:
# card.name="Anderson", category="General"
assert by_key["…"]["site"] == "Anderson"
assert by_key["…"]["site"] != "General"
```

```python
# tests/test_fc_cg_summary_export.py
assert SUMMARY_HEADERS[0] == "Site"
assert SUMMARY_HEADERS[1] == "Host"
# multisite row with host appears in column B
```

- [ ] **Step 2: Implement → PASS → Commit**

```powershell
python -m pytest tests/test_fc_cg_summary.py tests/test_fc_cg_summary_export.py tests/test_fc_cg_summary_multisite_api.py -q --tb=short
git add launchpad/fc_cg_summary.py launchpad/fc_cg_summary_export.py launchpad/health_server.py tests/test_fc_cg_summary.py tests/test_fc_cg_summary_export.py tests/test_fc_cg_summary_multisite_api.py
git commit -m "fix(fc-cg-summary): card-name site, schedule policy, Host Excel column."
```

Flash time: confirm `collect_fc_consistgrp_inventory` still calls `enrich_groups_flash_time`. If a unit gap exists for blank concise → filled detail, add a focused test in `tests/test_fc_consistgrp_ops.py` (or existing enrich tests) in this task — do not invent a second enrichment path.

---

### Task 2: Snapcopy Summary page module + HealthServer route (TDD)

**Files:**
- Create: `launchpad/snapcopy_summary_page.py`
- Modify: `launchpad/health_server.py` (import, `do_GET` serve HTML, `open_snapcopy_summary`)
- Create: `tests/test_snapcopy_summary_page.py`

**Interfaces:**
- `SNAPCOPY_SUMMARY_PATH = "/snapcopy-summary"`
- `SNAPCOPY_SUMMARY_HTML` — dark theme matching Hosts & Volumes / Contingency
- Page controls (ids):
  - `snapcopy-site` (select; All sites)
  - `snapcopy-refresh`, `snapcopy-export`
  - `snapcopy-select-all`, row `.snapcopy-row-cb` with `data-row-key`
  - table columns: checkbox, Site, Host (`<a href="https://…">`), Name, Status, Flash time, Progress, Maps, Host maps, Size, Policy, Snaps/week
  - status: `snapcopy-status`
  - nav: link to `/contingency-groups` labeled Consistency Groups
- JS: load sites from `/api/fc-consistgrp/cards` (or `/api/cards` if that is what Contingency used); Refresh → `GET /api/contingency-groups/fc-cg-summary/live`; Export → `POST …/export-selected` with `{selected, open:true}` + blob download (copy working pattern from current Contingency JS)
- `HealthServer.open_snapcopy_summary() -> str` like `open_host_volume_health`

- [ ] **Step 1: Page tests**

```python
def test_snapcopy_summary_markers():
    assert SNAPCOPY_SUMMARY_PATH == "/snapcopy-summary"
    assert 'id="snapcopy-refresh"' in SNAPCOPY_SUMMARY_HTML
    assert 'id="snapcopy-export"' in SNAPCOPY_SUMMARY_HTML
    assert "/api/contingency-groups/fc-cg-summary/live" in SNAPCOPY_SUMMARY_HTML
    assert "/api/contingency-groups/fc-cg-summary/export-selected" in SNAPCOPY_SUMMARY_HTML
    assert "https://" in SNAPCOPY_SUMMARY_HTML
    assert 'href="/contingency-groups"' in SNAPCOPY_SUMMARY_HTML

def test_health_server_serves_snapcopy_summary():
    # assert path constant used in do_GET source or open_ helper
    assert hasattr(HealthServer, "open_snapcopy_summary")
```

- [ ] **Step 2: Implement page + wire server → PASS → Commit**

```powershell
python -m pytest tests/test_snapcopy_summary_page.py -q --tb=short
git add launchpad/snapcopy_summary_page.py launchpad/health_server.py tests/test_snapcopy_summary_page.py
git commit -m "feat(snapcopy-summary): add dedicated Snapcopy Summary HealthServer page."
```

Copy UI/JS from `launchpad/contingency_groups.py` summary section (rename ids). Prefer extracting cleanly rather than leaving dead Contingency JS (removal is Task 3).

---

### Task 3: Consistency Groups — button in, panel out (TDD)

**Files:**
- Modify: `launchpad/contingency_groups.py`
- Modify: `tests/test_contingency_groups_page.py`

**Interfaces:**
- Add `<a class="btn secondary" href="/snapcopy-summary">Snapcopy Summary</a>` near FlashCopy CGs / Health Dashboard links
- Remove `#fc-cg-summary-section` and all `fc-cg-summary-*` / `exportFcCgSummary` / `refreshFcCgSummary` JS
- Contingency planning Export Excel / Export All Excel unchanged

- [ ] **Step 1: Update page tests**

```python
def test_contingency_has_snapcopy_summary_link():
    assert 'href="/snapcopy-summary"' in CONTINGENCY_GROUPS_HTML
    assert "Snapcopy Summary" in CONTINGENCY_GROUPS_HTML

def test_contingency_no_embedded_fc_cg_summary():
    assert 'id="fc-cg-summary-section"' not in CONTINGENCY_GROUPS_HTML
    assert 'id="fc-cg-summary-refresh"' not in CONTINGENCY_GROUPS_HTML
```

Remove obsolete Contingency tests that asserted summary markers.

- [ ] **Step 2: Implement → PASS → Commit**

```powershell
python -m pytest tests/test_contingency_groups_page.py tests/test_snapcopy_summary_page.py -q --tb=short
git add launchpad/contingency_groups.py tests/test_contingency_groups_page.py
git commit -m "refactor(contingency): move CG summary to Snapcopy Summary page."
```

---

### Task 4: Version 1.6.86

**Files:**
- Modify: `launchpad/config.py`
- Modify: `tests/test_system_connectivity_version.py`

- [ ] Set `APP_VERSION = "1.6.86"` and assert in version test (rename test to `test_app_version_1686` if present).

```powershell
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
python -m pytest tests/test_system_connectivity_version.py -q --tb=short
git add launchpad/config.py tests/test_system_connectivity_version.py
git commit -m "Bump LaunchPad to 1.6.86 for Snapcopy Summary page."
```

---

### Task 5: Final verification

```powershell
python -m pytest tests/test_fc_cg_summary.py tests/test_fc_cg_summary_export.py tests/test_fc_cg_summary_multisite_api.py tests/test_snapcopy_summary_page.py tests/test_contingency_groups_page.py tests/test_system_connectivity_version.py -q --tb=short
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
```

Expected: PASS, `1.6.86`.

Manual smoke (operator): Consistency Groups → Snapcopy Summary → Refresh → check rows → Export Excel; Site shows card names; Host opens `https://IP`; Policy shows schedule when configured.

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Dedicated `/snapcopy-summary` page | 2 |
| Remove panel from Consistency Groups | 3 |
| Snapcopy Summary button on Contingency | 3 |
| Site = card name | 1 |
| Host `https://` link + Excel Host | 1–2 |
| Policy schedule + array | 1 |
| Flash time enrichment retained | 1 |
| Export checked / multi-sheet | 2 (reuse APIs) |
| Version 1.6.86 | 4 |
| No dashboard button | Global / 3 |
