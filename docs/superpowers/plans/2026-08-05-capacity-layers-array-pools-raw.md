# Capacity Layers (Array, Pools/CPGs, Raw) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep normal array capacity as the always-on site metric; add Include CPG/pools and Show raw capacity toggles on Capacity Report that control UI, live capacity-focus commands, and Excel.

**Architecture:** Parse system capacity into separate `capacity_summary` (allocated/usable) and `raw_capacity_summary` (physical/raw). Extend `filter_capacity_focus_commands` with `include_pools`. Capacity Report gains two `localStorage` toggles and passes `include_pools` / `show_raw` on refresh and export. Excel omits pool or raw sections per flags.

**Tech Stack:** Python 3, HealthServer HTML/JS, openpyxl capacity export, pytest.

**Spec:** `docs/superpowers/specs/2026-08-05-capacity-layers-array-pools-raw-design.md`

## Global Constraints

- **Branch:** `feature/hpe-capacity-parse`
- **Normal array capacity always** collected (do not skip `showsys` / `lssystem`).
- **Include CPG / pools** default **on**; when off: hide UI + skip `showcpg` / `lsmdiskgrp` on capacity focus.
- **Show raw capacity** default **off**; raw from same system output; no raw alerts in v1.
- IBM pools labeled **Pools** (not FlashCopy CG).
- HPE site % = allocated from `showsys -d`, not All-CPGs rollup when system summary exists.
- Query/export flags: `include_pools=0|1`, `show_raw=0|1`.
- Bump `APP_VERSION` to **1.6.114** in the final task.
- Commit per task; run from `C:\Users\BrianColley\LaunchPad`
- Imports at module top (no new inline imports).

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/flashsystem_parse.py` | `parse_raw_capacity_summary`; keep normal `parse_capacity_summary` on allocated/usable |
| `launchpad/flashsystem_health.py` | Prefer system over pool rollup; attach `raw_capacity_summary`; HTML raw section |
| `launchpad/command_format.py` | `filter_capacity_focus_commands(..., include_pools: bool = True)` |
| `launchpad/health_server.py` | Refresh query `include_pools`; card API includes `raw_capacity_summary` |
| `launchpad/capacity_report.py` | Two toggles, CSS, pass flags on refresh/export |
| `launchpad/capacity_export.py` | Honor `include_pools` / `show_raw` |
| `tests/test_*.py` | Parse, filter, analyze, page markers, export |
| `launchpad/config.py` | `1.6.114` |

---

### Task 1: Raw capacity parse + normal vs physical split

**Files:**
- Modify: `launchpad/flashsystem_parse.py`
- Modify: `tests/test_hpe_capacity_parse.py` (or create `tests/test_capacity_layers_parse.py`)

**Interfaces:**

```python
def parse_raw_capacity_summary(output: str) -> dict[str, Any] | None:
    """From showsys -d / lssystem text: physical/raw total/free/used + used_pct.
    Return None if physical/raw fields absent.
    Keys mirror capacity_summary: name, used_bytes, total_bytes, free_bytes, used_pct, raw.
    """

def parse_capacity_summary(output: str) -> dict[str, Any] | None:
    """Normal/usable summary. Prefer allocated + total_capacity (HPE) or usable
    mdisk capacity (IBM). Do NOT use physical_capacity as total when allocated
    + total_capacity are present (physical belongs in parse_raw_capacity_summary).
    """
```

- [ ] **Step 1: Failing tests**

```python
HPE_SHOWSYS = """
Total Capacity (MB) : 1000000
Allocated Capacity (MB) : 270000
Free Capacity (MB) : 730000
...
"""  # use a realistic fixture; if raw lines exist in real samples, include them

def test_parse_capacity_summary_prefers_allocated_not_physical():
    # when both allocated/total and physical exist, used_pct ≈ allocated/total

def test_parse_raw_capacity_summary_from_physical_fields():
    # returns summary from physical_* / raw fields; None if absent
```

- [ ] **Step 2:** Run — expect FAIL  
`python -m pytest tests/test_hpe_capacity_parse.py tests/test_capacity_layers_parse.py -q -k "raw or allocated or physical" `

- [ ] **Step 3: Implement** parse helpers (adjust `pick_size` order in `parse_capacity_summary` so `physical_capacity` is not preferred over `total_capacity` + allocated).

- [ ] **Step 4:** PASS focused tests

- [ ] **Step 5: Commit**  
`git commit -m "Parse raw capacity separately from allocated array capacity."`

---

### Task 2: analyze_health prefers system; expose raw; HTML section

**Files:**
- Modify: `launchpad/flashsystem_health.py`
- Modify: `tests/` (health capacity / analyze tests)

**Interfaces:**

```python
# analyze_health return dict gains:
#   "raw_capacity_summary": dict | None

def format_capacity_report_html(
    capacity: dict | None,
    pools_output: str,
    *,
    raw_capacity: dict | None = None,
) -> str:
    """Include a Raw / physical block when raw_capacity present (CSS class capacity-raw-wrap)."""
```

Rules:
- If system `capacity` exists, do **not** overwrite with `capacity_summary_from_pools`.
- Call `parse_raw_capacity_summary(system_output)` when system output exists.
- Pool issues unchanged when pools present.

- [ ] **Step 1: Failing tests** — system ~27% + CPG ~97% → `capacity_summary.used_pct` ~27%; `raw_capacity_summary` set when physical present; HTML contains `capacity-raw-wrap` when raw passed.

- [ ] **Step 2–4:** Implement + pass

- [ ] **Step 5: Commit**  
`git commit -m "Expose raw capacity summary and prefer system over CPG rollup."`

---

### Task 3: Capacity focus `include_pools` filter

**Files:**
- Modify: `launchpad/command_format.py`
- Modify: `launchpad/health_server.py` (`refresh_card` / `/api/refresh/` query)
- Test: `tests/test_command_format.py` or new

**Interfaces:**

```python
def filter_capacity_focus_commands(
    commands: list[tuple[str, str]],
    *,
    include_pools: bool = True,
) -> list[tuple[str, str]]:
    """When include_pools is False, drop showcpg / lsmdiskgrp / 'capacity - cpg'
    / 'capacity - pools' (and similar pool labels). Keep showsys / lssystem."""
```

Wire refresh:

```python
# /api/refresh/?focus=capacity&include_pools=0|1
include_pools = (query.get("include_pools") or ["1"])[0] not in {"0", "false", "no"}
# refresh_card(..., focus=focus, include_pools=include_pools)
# inside refresh_card when focus==capacity:
commands = filter_capacity_focus_commands(commands, include_pools=include_pools)
```

Also pass `include_pools` into `export_capacity_excel_bytes` / Dell refresh paths later (Task 4 can wire export; Task 3 at least refresh API + `refresh_card` signature).

HealthCard / `to_api` should include `raw_capacity_summary` from analysis.

- [ ] **Step 1: Failing tests** — filter drops showcpg/lsmdiskgrp when False; keeps showsys; refresh_card spy receives include_pools.

- [ ] **Step 2–4:** Implement + pass

- [ ] **Step 5: Commit**  
`git commit -m "Skip pool/CPG commands when include_pools is off."`

---

### Task 4: Capacity Report toggles + Excel flags

**Files:**
- Modify: `launchpad/capacity_report.py`
- Modify: `launchpad/capacity_export.py`
- Modify: `launchpad/health_server.py` (`/api/capacity-export`, optionally Dell)
- Tests: page markers + export unit tests

**UI:**

```html
<label><input type="checkbox" id="show-pools-toggle" checked> Include CPG / pools</label>
<label><input type="checkbox" id="show-raw-toggle"> Show raw capacity</label>
```

- Keys: keep/migrate `launchpad.capacityReport.showPools`; add `launchpad.capacityReport.showRaw` (default `"0"`).
- CSS: existing `hide-pool-storage`; add `hide-raw-capacity` for `.capacity-raw-wrap`.
- `refreshCard`: append `&include_pools=${showPoolsToggle.checked ? 1 : 0}`.
- `downloadExcel` / Dell if using capacity refresh: `&include_pools=` and `&show_raw=`.

**Excel:**

```python
def export_storage_capacity_excel_from_sites(
    ...,
    include_pools: bool = True,
    show_raw: bool = False,
):
    # include_pools False → omit pool sheet rows / pool stats
    # show_raw True → raw columns or section when site has raw_capacity_summary
```

Export path builds sites after `refresh_card(..., focus="capacity", include_pools=...)`.

- [ ] **Step 1: Marker tests** for toggle ids, localStorage keys, query param names; export omits pools when flag off.

- [ ] **Step 2–4:** Implement + pass

- [ ] **Step 5: Commit**  
`git commit -m "Add Capacity Report pool and raw toggles with Excel flags."`

---

### Task 5: Version bump + verification

**Files:**
- `launchpad/config.py` → `APP_VERSION = "1.6.114"`
- `tests/test_system_connectivity_version.py`

- [ ] **Step 1: Bump + pin**

- [ ] **Step 2: Focused pytest**

```bash
python -m pytest tests/test_hpe_capacity_parse.py tests/test_capacity_layers_parse.py tests/test_command_format.py tests/test_health_server_capacity_export.py tests/test_capacity_report_dell_button.py tests/test_system_connectivity_version.py -q
```

(Adjust to actual test module names created.)

- [ ] **Step 3: Manual smoke (operator)**  
1. Capacity Report: site % matches array, not All CPGs.  
2. Include CPG/pools off → pools hidden; refresh faster; no new CPG rows.  
3. Show raw on → raw block when physical fields exist.  
4. Excel respects both flags.

- [ ] **Step 4: Commit**  
`git commit -m "Bump app version to 1.6.114 for capacity layers."`

---

## Done when

- [ ] Site primary capacity is array/normal, not pool rollup when system data exists.
- [ ] Include CPG/pools toggle controls UI + live collect + Excel.
- [ ] Show raw capacity toggle controls UI + Excel; raw parsed separately.
- [ ] No raw alerts; pool/array alerts unchanged.
- [ ] `APP_VERSION` is **1.6.114**.

## Spec coverage

| Spec item | Task |
|-----------|------|
| Prefer system over CPG/pool rollup | 1–2 |
| `raw_capacity_summary` | 1–2 |
| Skip pool cmds when off | 3 |
| Two toggles + localStorage | 4 |
| Excel flags | 4 |
| Version 1.6.114 | 5 |
| No raw alerts | 2 (do not emit) |
