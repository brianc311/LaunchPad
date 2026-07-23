# LUN Builder + Consistency Groups Find / Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add client-only Find search on LUN Builder (volume/purpose/host) and Consistency Groups (group/host/volume), with cross-item switch + row filter; rename operator-visible Contingency Groups → Consistency Groups while keeping `/contingency-groups` URLs.

**Architecture:** Pure Python match/filter helpers (mirroring FC WWPN search style). Pages load full catalogs already; Find runs in browser JS using the same rules (duplicated lightly in page scripts, covered by Python unit tests for the canonical rules). UI string rename only; no new APIs.

**Tech Stack:** Embedded HTML/JS pages, `expand_lun_batch` from `lun_builder_data`, pytest, Health Dashboard Tk button label.

**Spec:** `docs/superpowers/specs/2026-07-23-lun-cg-search-rename-design.md`

## Global Constraints

- **Worktree:** create `.worktrees/lun-cg-search` on `feature/lun-cg-search-rename` from `feature/contingency-groups` tip (includes design commit; `APP_VERSION=1.6.53`)
- Client-only Find — **no** new find HTTP routes
- URLs/APIs/modules stay `contingency-groups` / `contingency_*`
- Operator-visible label **Consistency Groups**
- LUN Builder: filter Hosts/LUNs; miss → switch build A–Z + filter
- Consistency Groups: group name/location first; else content match → switch + filter Hosts/Volumes/Maps
- Wizard snap panels out of scope for v1 filtering
- Bump `APP_VERSION` to **1.6.54**
- Commit at each task’s commit step
- Run from: `cd C:\Users\BrianColley\LaunchPad\.worktrees\lun-cg-search`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/lun_builder_search.py` | Match/filter helpers for LUN builds (uses `expand_lun_batch`) |
| `launchpad/contingency_groups_search.py` | Match/filter helpers for contingency groups |
| `launchpad/lun_builder.py` | Find UI + JS filter/switch wiring |
| `launchpad/contingency_groups.py` | Rename visible strings + Find UI + JS wiring |
| `launchpad/fc_wwpn_report.py` | Nav link label → Consistency Groups |
| `launchpad/ui/dashboard_view.py` | Button + status text → Consistency Groups |
| `launchpad/config.py` | `1.6.54` |
| `tests/test_lun_builder_search.py` | LUN matcher tests |
| `tests/test_contingency_groups_search.py` | CG matcher tests |
| `tests/test_lun_builder_page.py` | Find wiring contract |
| `tests/test_contingency_groups_page.py` | Rename + Find wiring; path unchanged |

---

### Task 0: Confirm baseline

**Files:** none (worktree setup only)

- [ ] **Step 1: Create worktree + branch**

```powershell
cd C:\Users\BrianColley\LaunchPad
git fetch origin
git worktree add .worktrees/lun-cg-search -b feature/lun-cg-search-rename feature/contingency-groups
cd .worktrees/lun-cg-search
git status -sb
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-23-lun-cg-search-rename-design.md
Test-Path docs\superpowers\plans\2026-07-23-lun-cg-search-rename.md
```

Expected: `feature/lun-cg-search-rename`, `1.6.53`, both paths `True`.

If the plan file is only on the parent tip and not yet in the worktree, copy or ensure the plan commit is on the branch before Task 1.

- [ ] **Step 2: No feature commit**

---

### Task 1: LUN Builder search helpers

**Files:**
- Create: `launchpad/lun_builder_search.py`
- Create: `tests/test_lun_builder_search.py`

**Interfaces:**
- Produces:
  - `normalize_query(value: str) -> str`  # strip; lower for text match
  - `host_row_matches(host: dict, query: str) -> bool`  # empty query → True
  - `lun_row_matches(lun: dict, query: str) -> bool`  # purpose, host_names, expand_lun_batch names; empty → True
  - `build_matches_query(build: dict, query: str) -> bool`  # empty → True
  - `find_builds_matching_query(builds: list[dict], query: str) -> list[dict]`  # empty → []; else matching builds sorted by name A–Z

- [ ] **Step 1: Write failing tests**

```python
from launchpad.lun_builder_search import (
    build_matches_query,
    find_builds_matching_query,
    host_row_matches,
    lun_row_matches,
    normalize_query,
)


def test_normalize_query_strips_and_lowers():
    assert normalize_query("  ArchVG  ") == "archvg"


def test_empty_query_matches_all_rows():
    assert host_row_matches({"lpar_name": "pconsps3"}, "") is True
    assert lun_row_matches({"purpose": "archvg", "count": 1, "host_names": ["pconsps3"]}, "") is True
    assert build_matches_query({"name": "X", "hosts": [], "luns": []}, "") is True


def test_find_empty_query_returns_no_builds():
    builds = [{"id": "a", "name": "Hartford", "hosts": [{"lpar_name": "pconsps3"}], "luns": []}]
    assert find_builds_matching_query(builds, "") == []
    assert find_builds_matching_query(builds, "   ") == []


def test_host_row_matches_lpar_name():
    host = {"lpar_name": "pconsps3"}
    assert host_row_matches(host, "sps3") is True
    assert host_row_matches(host, "nope") is False


def test_lun_row_matches_purpose_hosts_and_expanded_volume():
    lun = {
        "purpose": "archvg",
        "count": 2,
        "shared": True,
        "name_prefix": "pcon",
        "cluster": "sps",
        "host_names": ["pconsps3", "pconsps4"],
    }
    assert lun_row_matches(lun, "archvg") is True
    assert lun_row_matches(lun, "pconsps4") is True
    assert lun_row_matches(lun, "pconsps_archvg_1") is True
    assert lun_row_matches(lun, "missing") is False


def test_find_builds_sorted_by_name():
    builds = [
        {
            "id": "b",
            "name": "Zebra",
            "hosts": [{"lpar_name": "hostz"}],
            "luns": [],
        },
        {
            "id": "a",
            "name": "Alpha",
            "hosts": [],
            "luns": [{"purpose": "root", "count": 1, "host_names": ["hostz"], "exact_name": True}],
        },
    ]
    found = find_builds_matching_query(builds, "hostz")
    assert [b["name"] for b in found] == ["Alpha", "Zebra"]
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
cd C:\Users\BrianColley\LaunchPad\.worktrees\lun-cg-search
python -m pytest tests/test_lun_builder_search.py -v
```

Expected: FAIL (module not found).

- [ ] **Step 3: Implement helpers**

Create `launchpad/lun_builder_search.py`:

```python
"""Pure helpers for LUN Builder Find matching."""

from __future__ import annotations

from typing import Any

from launchpad.lun_builder_data import expand_lun_batch


def normalize_query(value: str) -> str:
    return str(value or "").strip().lower()


def _text_matches(field: Any, q: str) -> bool:
    if not q:
        return False
    text = str(field or "").strip().lower()
    return bool(text) and q in text


def host_row_matches(host: dict[str, Any], query: str) -> bool:
    q = normalize_query(query)
    if not q:
        return True
    return _text_matches(host.get("lpar_name"), q)


def lun_row_matches(lun: dict[str, Any], query: str) -> bool:
    q = normalize_query(query)
    if not q:
        return True
    if _text_matches(lun.get("purpose"), q):
        return True
    for name in lun.get("host_names") or []:
        if _text_matches(name, q):
            return True
    for row in expand_lun_batch(lun):
        if _text_matches(row.get("name"), q):
            return True
    return False


def build_matches_query(build: dict[str, Any], query: str) -> bool:
    q = normalize_query(query)
    if not q:
        return True
    if any(host_row_matches(host, query) for host in (build.get("hosts") or []) if isinstance(host, dict)):
        return True
    if any(lun_row_matches(lun, query) for lun in (build.get("luns") or []) if isinstance(lun, dict)):
        return True
    return False


def find_builds_matching_query(builds: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    if not str(query or "").strip():
        return []
    return sorted(
        [b for b in builds if isinstance(b, dict) and build_matches_query(b, query)],
        key=lambda b: str(b.get("name") or "").lower(),
    )
```

Adjust `test_lun_row_matches_purpose_hosts_and_expanded_volume` if the exact expanded name from `expand_lun_batch` differs (inspect with a one-liner and align the assertion to the real name, e.g. `pconsps_archvg_1`).

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/test_lun_builder_search.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/lun_builder_search.py tests/test_lun_builder_search.py
git commit -m "Add LUN Builder Find match helpers for hosts, purposes, and volumes."
```

---

### Task 2: Consistency Groups search helpers

**Files:**
- Create: `launchpad/contingency_groups_search.py`
- Create: `tests/test_contingency_groups_search.py`

**Interfaces:**
- Produces:
  - `normalize_query(value: str) -> str`
  - `group_identity_matches(group: dict, query: str) -> bool`  # name or location; empty → True
  - `host_row_matches(host: dict, query: str) -> bool`  # name + wwpns; empty → True
  - `volume_row_matches(volume: dict, query: str) -> bool`  # name; empty → True
  - `map_row_matches(mapping: dict, query: str) -> bool`  # volume + host; empty → True
  - `group_content_matches(group: dict, query: str) -> bool`  # hosts/volumes/maps only
  - `find_groups_matching_identity(groups: list[dict], query: str) -> list[dict]`  # empty → []; sorted by name
  - `find_groups_matching_content(groups: list[dict], query: str) -> list[dict]`  # empty → []; sorted by name

- [ ] **Step 1: Write failing tests**

```python
from launchpad.contingency_groups_search import (
    find_groups_matching_content,
    find_groups_matching_identity,
    group_content_matches,
    group_identity_matches,
    host_row_matches,
    map_row_matches,
    volume_row_matches,
)


def test_identity_matches_name_and_location():
    group = {"name": "Hartford, CT", "location": "Hartford, CT", "hosts": [], "volumes": [], "maps": []}
    assert group_identity_matches(group, "hartford") is True
    assert group_identity_matches(group, "xyz") is False


def test_find_identity_empty_returns_none():
    groups = [{"name": "Hartford, CT", "location": "", "hosts": [], "volumes": [], "maps": []}]
    assert find_groups_matching_identity(groups, "") == []


def test_content_matches_host_volume_map():
    group = {
        "name": "Site",
        "location": "",
        "hosts": [{"name": "pconsps3", "wwpns": ["AA:BB"]}],
        "volumes": [{"name": "pconsps_archvg_1"}],
        "maps": [{"volume": "pconsps_archvg_1", "host": "pconsps3"}],
    }
    assert group_content_matches(group, "pconsps3") is True
    assert group_content_matches(group, "archvg") is True
    assert host_row_matches(group["hosts"][0], "aabb") is True
    assert volume_row_matches(group["volumes"][0], "archvg") is True
    assert map_row_matches(group["maps"][0], "pconsps3") is True
    assert group_content_matches(group, "nope") is False


def test_find_content_sorted_and_skips_identity_only():
    groups = [
        {"name": "Zebra", "location": "", "hosts": [{"name": "hostz", "wwpns": []}], "volumes": [], "maps": []},
        {"name": "Alpha", "location": "Alpha Loc", "hosts": [], "volumes": [], "maps": []},
    ]
    assert [g["name"] for g in find_groups_matching_content(groups, "hostz")] == ["Zebra"]
    assert [g["name"] for g in find_groups_matching_identity(groups, "alpha")] == ["Alpha"]
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/test_contingency_groups_search.py -v
```

Expected: FAIL (module not found).

- [ ] **Step 3: Implement helpers**

Create `launchpad/contingency_groups_search.py`:

```python
"""Pure helpers for Consistency Groups (contingency) Find matching."""

from __future__ import annotations

import re
from typing import Any


def normalize_query(value: str) -> str:
    return str(value or "").strip().lower()


def _text_matches(field: Any, q: str) -> bool:
    if not q:
        return False
    text = str(field or "").strip().lower()
    return bool(text) and q in text


def _wwpn_matches(field: Any, q: str) -> bool:
    if not q:
        return False
    q_norm = re.sub(r"[\s:]", "", q).upper()
    if isinstance(field, list):
        parts = field
    else:
        parts = re.split(r"[;,\s]+", str(field or ""))
    for part in parts:
        token = re.sub(r"[\s:]", "", str(part or "")).upper()
        if token and q_norm in token:
            return True
    return False


def group_identity_matches(group: dict[str, Any], query: str) -> bool:
    q = normalize_query(query)
    if not q:
        return True
    return _text_matches(group.get("name"), q) or _text_matches(group.get("location"), q)


def host_row_matches(host: dict[str, Any], query: str) -> bool:
    q = normalize_query(query)
    if not q:
        return True
    return _text_matches(host.get("name"), q) or _wwpn_matches(host.get("wwpns"), q)


def volume_row_matches(volume: dict[str, Any], query: str) -> bool:
    q = normalize_query(query)
    if not q:
        return True
    return _text_matches(volume.get("name"), q)


def map_row_matches(mapping: dict[str, Any], query: str) -> bool:
    q = normalize_query(query)
    if not q:
        return True
    return _text_matches(mapping.get("volume"), q) or _text_matches(mapping.get("host"), q)


def group_content_matches(group: dict[str, Any], query: str) -> bool:
    q = normalize_query(query)
    if not q:
        return True
    if any(host_row_matches(h, query) for h in (group.get("hosts") or []) if isinstance(h, dict)):
        return True
    if any(volume_row_matches(v, query) for v in (group.get("volumes") or []) if isinstance(v, dict)):
        return True
    if any(map_row_matches(m, query) for m in (group.get("maps") or []) if isinstance(m, dict)):
        return True
    return False


def find_groups_matching_identity(groups: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    if not str(query or "").strip():
        return []
    return sorted(
        [g for g in groups if isinstance(g, dict) and group_identity_matches(g, query)],
        key=lambda g: str(g.get("name") or "").lower(),
    )


def find_groups_matching_content(groups: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    if not str(query or "").strip():
        return []
    return sorted(
        [g for g in groups if isinstance(g, dict) and group_content_matches(g, query)],
        key=lambda g: str(g.get("name") or "").lower(),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/test_contingency_groups_search.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/contingency_groups_search.py tests/test_contingency_groups_search.py
git commit -m "Add Consistency Groups Find match helpers for identity and content."
```

---

### Task 3: UI rename Contingency Groups → Consistency Groups

**Files:**
- Modify: `launchpad/contingency_groups.py` (title, h1, aria-label, footer; optionally soften lede “contingency hosts” → “site hosts” / keep planning meaning)
- Modify: `launchpad/fc_wwpn_report.py` (nav link text only; href unchanged)
- Modify: `launchpad/ui/dashboard_view.py` (button `text=` and open status summary string)
- Modify: `tests/test_contingency_groups_page.py` (assert new label; path still `/contingency-groups`)

**Interfaces:**
- Consumes: none from Tasks 1–2
- Produces: operator-visible **Consistency Groups** strings; path still `/contingency-groups`

- [ ] **Step 1: Update failing/updated page tests first**

In `tests/test_contingency_groups_page.py`, change:

```python
def test_fc_wwpn_report_links_to_contingency_groups():
    assert 'href="/contingency-groups">Consistency Groups</a>' in FC_WWPN_REPORT_HTML
```

Add:

```python
def test_consistency_groups_ui_label_keeps_contingency_path():
    assert CONTINGENCY_GROUPS_PATH == "/contingency-groups"
    assert "<h1>Consistency Groups</h1>" in CONTINGENCY_GROUPS_HTML
    assert "LaunchPad Consistency Groups" in CONTINGENCY_GROUPS_HTML
    assert 'aria-label="Consistency group"' in CONTINGENCY_GROUPS_HTML
    assert "/api/contingency-groups" in CONTINGENCY_GROUPS_HTML
```

- [ ] **Step 2: Run to verify rename assertions fail**

```powershell
python -m pytest tests/test_contingency_groups_page.py::test_fc_wwpn_report_links_to_contingency_groups tests/test_contingency_groups_page.py::test_consistency_groups_ui_label_keeps_contingency_path -v
```

Expected: FAIL on old strings.

- [ ] **Step 3: Apply renames**

In `contingency_groups.py`:
- `<title>LaunchPad Consistency Groups</title>`
- `<h1>Consistency Groups</h1>`
- `aria-label="Consistency group"`
- Footer: `LaunchPad Consistency Groups v{{APP_VERSION}}`
- Lede: keep planning/create meaning; e.g. `Maintain a planning reference for site hosts, volumes, and mappings. By default these entries are planning-only; Run Create (after Preview) can create _snap volumes and start FlashCopy on the linked array.`

In `fc_wwpn_report.py`:
- `href="/contingency-groups">Consistency Groups</a>`

In `dashboard_view.py`:
- `text="Consistency Groups"`
- Status summary: `Consistency Groups opened — reference library only; it does not modify arrays.`

- [ ] **Step 4: Run page tests**

```powershell
python -m pytest tests/test_contingency_groups_page.py -q
```

Expected: PASS (update any remaining assertions that still require the old visible label).

- [ ] **Step 5: Commit**

```powershell
git add launchpad/contingency_groups.py launchpad/fc_wwpn_report.py launchpad/ui/dashboard_view.py tests/test_contingency_groups_page.py
git commit -m "Rename Contingency Groups UI label to Consistency Groups."
```

---

### Task 4: Wire LUN Builder Find UI

**Files:**
- Modify: `launchpad/lun_builder.py` (search input + Find; filter/switch JS)
- Modify: `tests/test_lun_builder_page.py` (contract strings)

**Interfaces:**
- Consumes: Task 1 semantics (mirror in JS using existing `expandLunBatch`)
- Produces: `#lun-search`, `#lun-search-btn`, `runLunSearch(` in page HTML

- [ ] **Step 1: Write failing page contract tests**

Add to `tests/test_lun_builder_page.py`:

```python
def test_lun_builder_exposes_find_search():
    for text in (
        'id="lun-search"',
        'id="lun-search-btn"',
        "function runLunSearch(",
        "Search volume, purpose, or host",
        "No matching hosts, volumes, or purposes",
    ):
        assert text in LUN_BUILDER_HTML
```

- [ ] **Step 2: Run to verify fail**

```powershell
python -m pytest tests/test_lun_builder_page.py::test_lun_builder_exposes_find_search -v
```

Expected: FAIL.

- [ ] **Step 3: Implement UI + JS**

In the picker row of `lun_builder.py` (after New button, before status), add:

```html
<input type="search" id="lun-search" placeholder="Search volume, purpose, or host…" aria-label="Search LUN build">
<button type="button" class="secondary" id="lun-search-btn">Find</button>
```

Add minimal CSS matching FC WWPN search input width if needed.

In the script section, add state `let lunSearchQuery = "";` and helpers mirroring Task 1:

- `hostRowMatches(host, q)`, `lunRowMatches(lun, q)` using `expandLunBatch`
- `buildMatches(build, q)`
- In `render()`, after building host/lun rows, if `lunSearchQuery` is non-empty, set `tr.style.display` / skip non-matching rows (or add `hidden` class). Prefer rendering all rows then hiding non-matches so indices/`data-index` stay stable.
- `function runLunSearch()`:
  1. Read input → `lunSearchQuery`
  2. If empty: clear filter, `render()`, status ok / cleared
  3. If `buildMatches(activeBuild(), q)`: `render()`, status `Showing matching rows`
  4. Else search `[...templates, ...builds]` (or whatever arrays the page uses for picker items — include both template and saved lists the picker exposes), pick first by name A–Z, set `currentId` / picker, `render()`, status with extras count
  5. Else status `No matching hosts, volumes, or purposes`

Wire click + Enter on the search input.

Keep data-index stable when filtering (hide rows; do not renumber).

- [ ] **Step 4: Run page + search unit tests**

```powershell
python -m pytest tests/test_lun_builder_page.py tests/test_lun_builder_search.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/lun_builder.py tests/test_lun_builder_page.py
git commit -m "Add LUN Builder Find search with row filter and cross-build switch."
```

---

### Task 5: Wire Consistency Groups Find UI

**Files:**
- Modify: `launchpad/contingency_groups.py` (search input + Find; filter/switch JS)
- Modify: `tests/test_contingency_groups_page.py` (Find contract)

**Interfaces:**
- Consumes: Task 2 semantics (mirror in JS)
- Produces: `#cg-search`, `#cg-search-btn`, `runCgSearch(`

- [ ] **Step 1: Write failing page contract tests**

```python
def test_consistency_groups_exposes_find_search():
    for text in (
        'id="cg-search"',
        'id="cg-search-btn"',
        "function runCgSearch(",
        "Search group, host, or volume",
        "No matching groups, hosts, or volumes",
    ):
        assert text in CONTINGENCY_GROUPS_HTML
```

- [ ] **Step 2: Run to verify fail**

```powershell
python -m pytest tests/test_contingency_groups_page.py::test_consistency_groups_exposes_find_search -v
```

Expected: FAIL.

- [ ] **Step 3: Implement UI + JS**

Near Group picker, add:

```html
<input type="search" id="cg-search" placeholder="Search group, host, or volume…" aria-label="Search consistency groups">
<button type="button" class="secondary" id="cg-search-btn">Find</button>
```

State: `let cgSearchQuery = "";` and optional mode `let cgFilterContent = false;` (when identity match, show full group; when content match, filter tables).

`runCgSearch()`:
1. Empty → clear filter flags, render, return
2. Identity matches across `groups` → select first A–Z, clear content filter, note extras, render
3. Else content matches → select first A–Z, set content filter on, hide non-matching host/volume/map rows (main tables only; wizard out of scope), note extras
4. Else `No matching groups, hosts, or volumes`

Apply hide logic in existing `render()` / row render paths for `#hosts-body`, `#volumes-body`, `#maps-body` only.

- [ ] **Step 4: Run CG page + search tests**

```powershell
python -m pytest tests/test_contingency_groups_page.py tests/test_contingency_groups_search.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/contingency_groups.py tests/test_contingency_groups_page.py
git commit -m "Add Consistency Groups Find search with group switch and row filter."
```

---

### Task 6: Version bump 1.6.54

**Files:**
- Modify: `launchpad/config.py`

**Interfaces:**
- Produces: `APP_VERSION == "1.6.54"`

- [ ] **Step 1: Bump version**

Set `APP_VERSION = "1.6.54"` in `launchpad/config.py`.

- [ ] **Step 2: Smoke**

```powershell
python -c "from launchpad.config import APP_VERSION; from launchpad.lun_builder import LUN_BUILDER_HTML; from launchpad.contingency_groups import CONTINGENCY_GROUPS_HTML; assert APP_VERSION=='1.6.54'; assert 'lun-search' in LUN_BUILDER_HTML; assert 'cg-search' in CONTINGENCY_GROUPS_HTML; assert 'Consistency Groups' in CONTINGENCY_GROUPS_HTML; assert CONTINGENCY_GROUPS_HTML.count('/contingency-groups')>=1; print('ok')"
python -m pytest tests/test_lun_builder_search.py tests/test_contingency_groups_search.py tests/test_lun_builder_page.py tests/test_contingency_groups_page.py -q
```

Expected: `ok` and all PASS.

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version to 1.6.54 for LUN/CG Find and Consistency Groups rename."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| LUN Find volume/purpose/host + filter | 1, 4 |
| LUN cross-build switch A–Z | 1, 4 |
| CG Find group then content + filter | 2, 5 |
| UI rename Consistency Groups; paths unchanged | 3 |
| Dashboard + FC WWPN nav labels | 3 |
| No new find API | (global) |
| Wizard filter out of scope | 5 |
| Version 1.6.54 | 6 |

## Self-review notes

- Expanded volume assertion in Task 1 must match `expand_lun_batch` output for the sample lun (adjust test if prefix/cluster stem differs).
- LUN Builder picker includes templates + saved builds — Find must scan both lists the UI can select.
- Do not change `CONTINGENCY_GROUPS_PATH` or API strings.
