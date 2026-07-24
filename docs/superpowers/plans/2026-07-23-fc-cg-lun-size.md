# FlashCopy CG Member Map LUN Size Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show source LUN size on FlashCopy CG Member maps / stand-alone maps, plus a CG total in the Member maps hint, by enriching inventory with `lsvdisk` capacities.

**Architecture:** Pure helpers enrich maps from an `lsvdisk` capacity index and sum CG totals. `collect_fc_consistgrp_inventory` also runs `lsvdisk` (best-effort). `fc_consistgrp.py` UI adds Size columns and total hint text. Version **1.6.60**.

**Tech Stack:** Existing FC consistgrp ops, `parse_lsvdisk_volumes`, `_parse_size_bytes` / `_format_bytes`, pytest.

**Spec:** `docs/superpowers/specs/2026-07-23-fc-consistgrp-lun-size-design.md`

## Global Constraints

- **Worktree:** `.worktrees/fc-cg-lun-size` on `feature/fc-cg-lun-size` from `feature/contingency-groups` tip (`APP_VERSION=1.6.59`, includes LUN-size design commit)
- Size = **source** volume capacity only
- Member maps: Size column + CG total in hint; stand-alone: Size column
- `lsvdisk` failure must not fail whole inventory
- Bump `APP_VERSION` to **1.6.60**
- Commit at each task’s commit step
- Run from: `cd C:\Users\BrianColley\LaunchPad\.worktrees\fc-cg-lun-size`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/fc_consistgrp_ops.py` | Capacity index, enrich maps, CG total helpers; inventory runs `lsvdisk` |
| `launchpad/fc_consistgrp.py` | Size column UI + Member maps total hint |
| `launchpad/config.py` | `1.6.60` |
| `tests/test_fc_consistgrp_ops.py` | Enrichment / total / inventory tests |
| `tests/test_fc_consistgrp_page.py` | Page contract tests (create if missing) |

---

### Task 0: Confirm baseline

**Files:** none

- [ ] **Step 1: Create worktree**

```powershell
cd C:\Users\BrianColley\LaunchPad
git fetch origin
git worktree add .worktrees/fc-cg-lun-size -b feature/fc-cg-lun-size feature/contingency-groups
cd .worktrees/fc-cg-lun-size
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-23-fc-consistgrp-lun-size-design.md
Test-Path docs\superpowers\plans\2026-07-23-fc-cg-lun-size.md
```

Expected: `1.6.59` (or tip with design+plan), paths `True`.

- [ ] **Step 2: No feature commit**

---

### Task 1: Enrichment + CG total helpers

**Files:**
- Modify: `launchpad/fc_consistgrp_ops.py`
- Modify: `tests/test_fc_consistgrp_ops.py`

**Interfaces:**
- Produces:
  - `volume_capacity_index(lsvdisk_output: str) -> dict[str, dict]`  
    Keys: volume name. Values: `{ "capacity": str, "bytes": int | None }` using `parse_lsvdisk_volumes` + `_parse_size_bytes` (cast float→int when not None).
  - `enrich_maps_with_source_size(maps: list[dict], index: dict[str, dict]) -> list[dict]`  
    Copies each map; sets `source_size` (display string) and `source_size_bytes` (int or omit/`None`) from index lookup on `source`.
  - `sum_source_size_bytes(maps: list[dict]) -> int` — sum known bytes only.
  - `format_cg_total_size(maps: list[dict]) -> str` — `_format_bytes(sum)` if sum > 0 else `""` (UI treats empty as no total / `—`).

- [ ] **Step 1: Failing tests**

```python
from launchpad.fc_consistgrp_ops import (
    enrich_maps_with_source_size,
    format_cg_total_size,
    sum_source_size_bytes,
    volume_capacity_index,
)

LSVDISK_SAMPLE = """id:name:capacity:mdisk_grp_name
0:AWD1_AS400_1:100.00GB:Pool0
1:AWD1_AS400_2:200.00GB:Pool0
2:VOL_A:50.00GB:Pool0
"""


def test_volume_capacity_index():
    idx = volume_capacity_index(LSVDISK_SAMPLE)
    assert idx["AWD1_AS400_1"]["capacity"] == "100.00GB"
    assert idx["AWD1_AS400_1"]["bytes"] == int(100 * (1024**3))


def test_enrich_maps_with_source_size():
    maps = parse_lsfcmap_rows(MAP_SAMPLE)
    idx = volume_capacity_index(LSVDISK_SAMPLE)
    enriched = enrich_maps_with_source_size(maps, idx)
    by_name = {m["name"]: m for m in enriched}
    assert by_name["fcmap0"]["source_size"] == "100.00GB"
    assert by_name["standalone1"]["source_size"] == "50.00GB"
    assert by_name["fcmap0"]["source_size_bytes"] == int(100 * (1024**3))


def test_enrich_unknown_source_leaves_empty():
    maps = [{"name": "x", "source": "missing_vol", "consistgrp": "g"}]
    enriched = enrich_maps_with_source_size(maps, {})
    assert enriched[0].get("source_size") in ("", None)
    assert not enriched[0].get("source_size_bytes")


def test_sum_and_format_cg_total():
    maps = [
        {"source_size_bytes": int(100 * (1024**3))},
        {"source_size_bytes": int(200 * (1024**3))},
        {"source_size": "?", "source_size_bytes": None},
    ]
    assert sum_source_size_bytes(maps) == int(300 * (1024**3))
    total = format_cg_total_size(maps)
    assert total  # non-empty formatted string from _format_bytes
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
cd C:\Users\BrianColley\LaunchPad\.worktrees\fc-cg-lun-size
python -m pytest tests/test_fc_consistgrp_ops.py -k "capacity_index or enrich_maps_with_source or sum_and_format" -v
```

- [ ] **Step 3: Implement helpers** in `fc_consistgrp_ops.py`

Import `parse_lsvdisk_volumes` from `flashsystem_fc` and `_parse_size_bytes`, `_format_bytes` from `flashsystem_parse`.

- [ ] **Step 4: PASS + commit**

```powershell
git add launchpad/fc_consistgrp_ops.py tests/test_fc_consistgrp_ops.py
git commit -m "Add FC map source-size enrichment and CG total helpers."
```

---

### Task 2: Inventory collects `lsvdisk` and enriches maps

**Files:**
- Modify: `launchpad/fc_consistgrp_ops.py` (`collect_fc_consistgrp_inventory`)
- Modify: `tests/test_fc_consistgrp_ops.py`

**Interfaces:**
- Produces: `collect_fc_consistgrp_inventory` also runs `svcinfo lsvdisk -delim :`; on success enriches maps; on exception/empty continues with unenriched maps.

- [ ] **Step 1: Update inventory tests**

Extend `test_collect_fc_consistgrp_inventory_parses_delimited_tables` (and fallback test) so `run_cmd` returns `lsvdisk` output for commands containing `lsvdisk`. Assert enriched `source_size` on a known map.

Add:

```python
def test_collect_inventory_lsvdisk_failure_still_returns_maps():
    def run_cmd(cmd: str) -> str:
        if "lsfcconsistgrp" in cmd:
            return CG_SAMPLE
        if "lsfcmap" in cmd:
            return MAP_SAMPLE
        if "lsvdisk" in cmd:
            raise RuntimeError("ssh failed")
        return ""

    groups, maps = collect_fc_consistgrp_inventory(run_cmd)
    assert groups and maps
    assert not maps[0].get("source_size")
```

Wrap `lsvdisk` call in try/except inside collect.

- [ ] **Step 2: FAIL → implement**

```python
# after parsing maps:
index: dict = {}
try:
    vols_output = run_cmd("svcinfo lsvdisk -delim :")
    if not str(vols_output or "").strip():
        vols_output = run_cmd("svcinfo lsvdisk")
    index = volume_capacity_index(vols_output)
except Exception:
    index = {}
maps = enrich_maps_with_source_size(maps, index)
```

- [ ] **Step 3: PASS + commit**

```powershell
git add launchpad/fc_consistgrp_ops.py tests/test_fc_consistgrp_ops.py
git commit -m "Enrich FlashCopy CG inventory maps with lsvdisk source sizes."
```

---

### Task 3: Page UI Size column + CG total hint

**Files:**
- Modify: `launchpad/fc_consistgrp.py`
- Create: `tests/test_fc_consistgrp_page.py` (if no page contract file exists)

**Interfaces:**
- Produces: Member maps `<th>Size</th>` after Target; stand-alone same; `renderMemberMaps` / `renderStandAlone` show `source_size` or `—`; hint includes `Total size …` when total non-empty.

- [ ] **Step 1: Contract tests**

```python
from launchpad.fc_consistgrp import FC_CONSISTGRP_HTML


def test_fc_consistgrp_size_column_and_total_hint():
    html = FC_CONSISTGRP_HTML
    assert ">Size</th>" in html or ">Size<" in html
    assert "source_size" in html
    assert "Total size" in html
```

- [ ] **Step 2: Implement UI**

- Member maps header: `… Target | Size | Status | Progress` — colspan empty rows → 7
- Stand-alone: add Size; colspan → 6
- In `renderMemberMaps`, after Target cell add Size; compute total via JS sum of `source_size_bytes` or display preformatted — simplest: sum bytes in JS when present, else show raw `source_size` strings only and for total use a small JS helper that sums `Number(mapping.source_size_bytes||0)` and formats roughly, **OR** pass total from server only for selected group in hint by computing in JS:

```javascript
function formatBytes(n) {
  // match _format_bytes style roughly, or show GB with 2 decimals
}
function memberMapsTotalLabel(maps) {
  let sum = 0;
  let any = false;
  for (const m of maps) {
    const b = Number(m.source_size_bytes);
    if (Number.isFinite(b) && b > 0) { sum += b; any = true; }
  }
  return any ? (" · Total size " + formatBytes(sum)) : "";
}
```

Prefer importing format consistency: optional tiny pure `format_cg_total_size` already returns server string — for client-selected group, JS sum is fine if it matches `_format_bytes` closely. Simpler approach: expose `format_cg_total_size` logic duplicated lightly in JS using GB/TB thresholds like `_format_bytes` — check `_format_bytes` implementation and mirror.

- [ ] **Step 3: PASS + commit**

```powershell
python -m pytest tests/test_fc_consistgrp_page.py tests/test_fc_consistgrp_ops.py -q
git add launchpad/fc_consistgrp.py tests/test_fc_consistgrp_page.py
git commit -m "Show source Size and CG total on FlashCopy Consistgrp page."
```

---

### Task 4: Version bump 1.6.60

**Files:**
- Modify: `launchpad/config.py`

- [ ] **Step 1:** `APP_VERSION = "1.6.60"`

- [ ] **Step 2: Smoke**

```powershell
python -c "from launchpad.config import APP_VERSION; from launchpad.fc_consistgrp import FC_CONSISTGRP_HTML; assert APP_VERSION=='1.6.60'; assert 'Size' in FC_CONSISTGRP_HTML; print('ok')"
python -m pytest tests/test_fc_consistgrp_ops.py tests/test_fc_consistgrp_page.py -q
```

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version to 1.6.60 for FlashCopy CG LUN size."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Enrichment helpers + CG total | 1 |
| Inventory `lsvdisk` best-effort | 2 |
| UI Size + total hint + stand-alone | 3 |
| Version 1.6.60 | 4 |

## Self-review notes

- Do not fail inventory when `lsvdisk` errors.
- Source only — never use target for Size.
- Preserve existing CG action flows untouched.
