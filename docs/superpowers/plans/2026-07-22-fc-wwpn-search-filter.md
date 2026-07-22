# FC WWPN Search + WAG Include Filters — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add FC WWPN Report search (WWPN / remote WWPN / host / volume) and Snapshot-Schedule-style WAG1/WAG2/Other include filters that also gate Excel export.

**Architecture:** Client-side include + search filters in `fc_wwpn_report.py` combine with the existing Contingency-group filter before render. Excel export passes `groups=` to `/api/fc-wwpn-export`, which reuses `filter_cards_by_groups` from `snapshot_schedule_export`. A small pure Python matcher (`fc_wwpn_filter.py`) defines search rules for unit tests; the page JS mirrors that algorithm.

**Tech Stack:** Existing HealthServer, FC WWPN report HTML/JS, openpyxl export, pytest.

**Spec:** `docs/superpowers/specs/2026-07-22-fc-wwpn-search-filter-design.md`

## Global Constraints

- Work in `C:\Users\BrianColley\LaunchPad\.worktrees\fc-wwpn-search-filter` on branch `feature/fc-wwpn-search-filter` (from `feature/contingency-groups`).
- FC WWPN Report only — do not change Capacity Report or Snapshot Schedule UI.
- One search box; hide non-matches; highlight first match; search is **screen-only** (does not filter Excel).
- Include bar filters **screen and Excel**; reuse `site_group` / `filter_cards_by_groups` (do not duplicate grouping rules).
- Hint text on this page: `Uncheck a group to hide it from the report and export.`
- Search placeholder: `Search WWPN, remote WWPN, host, or volume…`
- Bump `APP_VERSION` from tip `1.6.41` to `1.6.49` (1.6.42–1.6.48 claimed by parallel branches).
- Commit at each task’s commit step (PowerShell: `git commit -m "message"` — no bash heredoc).

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/fc_wwpn_filter.py` (new) | `normalize_wwpn`, `card_matches_search` |
| `launchpad/fc_wwpn_report.py` | Include bar + search UI; combined filter in `render()`; Excel `groups=` URL |
| `launchpad/health_server.py` | `/api/fc-wwpn-export` parse `groups` and filter cards |
| `launchpad/config.py` | Version `1.6.49` |
| `tests/test_fc_wwpn_filter.py` (new) | Search matcher unit tests |
| `tests/test_fc_wwpn_export_groups.py` (new) | Export group filtering |
| `tests/test_fc_wwpn_page.py` (new) | Page wiring strings |

---

### Task 0: Confirm worktree baseline

**Files:** none (git only)

**Interfaces:**
- Consumes: existing branch with approved design doc
- Produces: confirmed cwd + `APP_VERSION`

- [ ] **Step 1: Confirm location and version**

```powershell
cd C:\Users\BrianColley\LaunchPad\.worktrees\fc-wwpn-search-filter
git branch --show-current
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
```

Expected: `feature/fc-wwpn-search-filter` and `1.6.41`.

- [ ] **Step 2: No commit**

---

### Task 1: Search matcher helper

**Files:**
- Create: `launchpad/fc_wwpn_filter.py`
- Create: `tests/test_fc_wwpn_filter.py`

**Interfaces:**
- Consumes: card dict shape used by FC WWPN UI (`fc_ports`, `fc_hosts`, `fc_mappings`, `fc_fabric` with fields as in `fc_wwpn_report.py` / `rows_from_card_api`)
- Produces:
  - `normalize_wwpn(value: str) -> str` — strip spaces/colons, uppercase
  - `card_matches_search(card: dict, query: str) -> bool` — empty/whitespace query → `True`; else match if any local port WWPN, remote WWPN (ports/`fc_fabric`), host name, host WWPN, or mapped `vdisk_name` contains the query (WWPN fields compared after normalize; names case-insensitive substring)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_fc_wwpn_filter.py`:

```python
from launchpad.fc_wwpn_filter import card_matches_search, normalize_wwpn


def test_normalize_wwpn_strips_colons_and_spaces():
    assert normalize_wwpn("10:00:00:00:c9:a1:b2:c3") == "10000000C9A1B2C3"
    assert normalize_wwpn("  aa bb  ") == "AABB"


def test_empty_query_matches_all():
    card = {"name": "Site", "fc_ports": [], "fc_hosts": [], "fc_mappings": [], "fc_fabric": []}
    assert card_matches_search(card, "") is True
    assert card_matches_search(card, "   ") is True


def test_matches_local_and_remote_wwpn():
    card = {
        "fc_ports": [{"wwpn": "10:00:00:00:c9:a1:b2:c3", "remote_wwpns": "20:00:00:00:11:22:33:44"}],
        "fc_hosts": [],
        "fc_mappings": [],
        "fc_fabric": [{"local_wwpn": "AA", "remote_wwpn": "BB:CC", "host_name": ""}],
    }
    assert card_matches_search(card, "c9a1b2c3") is True
    assert card_matches_search(card, "2000000011223344") is True
    assert card_matches_search(card, "bbcc") is True
    assert card_matches_search(card, "deadbeef") is False


def test_matches_host_and_volume_names():
    card = {
        "fc_ports": [],
        "fc_hosts": [{"host_name": "esx-wag1-01", "wwpns": "AA:BB"}],
        "fc_mappings": [{"vdisk_name": "ADC-Data01", "host_name": "esx-wag1-01"}],
        "fc_fabric": [],
    }
    assert card_matches_search(card, "esx-wag1") is True
    assert card_matches_search(card, "adc-data") is True
    assert card_matches_search(card, "missing") is False
```

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_fc_wwpn_filter.py -v
```

Expected: FAIL (module not found).

- [ ] **Step 3: Implement `launchpad/fc_wwpn_filter.py`**

```python
"""Pure helpers for FC WWPN report search matching."""

from __future__ import annotations

import re
from typing import Any


def normalize_wwpn(value: str) -> str:
    return re.sub(r"[\s:]", "", str(value or "")).upper()


def _text_haystack(parts: list[Any]) -> str:
    return " ".join(str(p or "") for p in parts).lower()


def _wwpn_haystack(parts: list[Any]) -> str:
    return "".join(normalize_wwpn(str(p or "")) for p in parts)


def card_matches_search(card: dict[str, Any], query: str) -> bool:
    raw = str(query or "").strip()
    if not raw:
        return True
    q_text = raw.lower()
    q_wwpn = normalize_wwpn(raw)

    text_parts: list[Any] = []
    wwpn_parts: list[Any] = []

    for port in card.get("fc_ports") or []:
        if not isinstance(port, dict):
            continue
        wwpn_parts.append(port.get("wwpn"))
        wwpn_parts.append(port.get("remote_wwpns"))
    for host in card.get("fc_hosts") or []:
        if not isinstance(host, dict):
            continue
        text_parts.append(host.get("host_name") or host.get("name"))
        wwpn_parts.append(host.get("wwpns"))
        wwpn_parts.append(host.get("wwpn"))
        wwpn_parts.append(host.get("host_wwpns"))
    for mapping in card.get("fc_mappings") or []:
        if not isinstance(mapping, dict):
            continue
        text_parts.append(mapping.get("vdisk_name") or mapping.get("volume"))
        text_parts.append(mapping.get("host_name") or mapping.get("host"))
        wwpn_parts.append(mapping.get("host_wwpns"))
    for login in card.get("fc_fabric") or []:
        if not isinstance(login, dict):
            continue
        text_parts.append(login.get("host_name"))
        wwpn_parts.append(login.get("local_wwpn"))
        wwpn_parts.append(login.get("remote_wwpn"))

    if q_text and q_text in _text_haystack(text_parts):
        return True
    if q_wwpn and q_wwpn in _wwpn_haystack(wwpn_parts):
        return True
    return False
```

Also walk `fc_ports_by_node[].ports` the same way as top-level `fc_ports` (some cards only populate by-node). Append that loop in the implementation.

- [ ] **Step 4: Run GREEN**

```powershell
python -m pytest tests/test_fc_wwpn_filter.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/fc_wwpn_filter.py tests/test_fc_wwpn_filter.py
git commit -m "Add FC WWPN search matcher helper."
```

---

### Task 2: Excel export respects `groups=`

**Files:**
- Modify: `launchpad/health_server.py` (`/api/fc-wwpn-export` handler ~1908+)
- Create: `tests/test_fc_wwpn_export_groups.py`

**Interfaces:**
- Consumes: `filter_cards_by_groups` / `site_group` from `launchpad.snapshot_schedule_export`
- Produces: export filters cards before `build_fc_wwpn_workbook`; default when `groups` omitted = all three (`wag1,wag2,other`) so existing callers keep full export

Mirror Snapshot Schedule parsing (~1871–1900 in `health_server.py`):

```python
groups_raw = (query.get("groups") or ["wag1,wag2,other"])[0]
groups = {
    part.strip().lower()
    for part in str(groups_raw).split(",")
    if part.strip()
}
# after building `cards` list for FC profiles:
from launchpad.snapshot_schedule_export import filter_cards_by_groups
cards = filter_cards_by_groups(cards, groups)
```

If `groups` is empty set after parse, `filter_cards_by_groups` returns `[]` — keep that.

- [ ] **Step 1: Write failing tests**

Create `tests/test_fc_wwpn_export_groups.py`:

```python
from launchpad.snapshot_schedule_export import filter_cards_by_groups, site_group


def test_site_group_classifies_wag_names():
    assert site_group({"name": "WAG1-Anderson", "category": "", "host": "", "model": "", "device_profile": ""}) == "wag1"
    assert site_group({"name": "Lab", "category": "WAG2", "host": "", "model": "", "device_profile": ""}) == "wag2"
    assert site_group({"name": "Moreno", "category": "CA", "host": "", "model": "", "device_profile": ""}) == "other"


def test_filter_cards_by_groups_wag1_only():
    cards = [
        {"name": "WAG1-A", "category": "", "host": "", "model": "", "device_profile": ""},
        {"name": "WAG2-B", "category": "", "host": "", "model": "", "device_profile": ""},
        {"name": "Other-C", "category": "Lab", "host": "", "model": "", "device_profile": ""},
    ]
    kept = filter_cards_by_groups(cards, {"wag1"})
    assert [c["name"] for c in kept] == ["WAG1-A"]


def test_filter_cards_empty_groups_yields_empty():
    cards = [{"name": "WAG1-A", "category": "", "host": "", "model": "", "device_profile": ""}]
    assert filter_cards_by_groups(cards, set()) == []
```

Add an API-level test if easy with existing HealthServer test helpers — otherwise add a focused unit that documents the handler must call `filter_cards_by_groups` by importing and asserting the helper behavior above, plus a smoke that reads `health_server.py` source contains `filter_cards_by_groups` near `fc-wwpn-export` **or** better: monkeypatch `build_fc_wwpn_workbook` in a HealthServer GET test.

Prefer a HealthServer test pattern from `tests/test_health_server_lun_builder.py` if present; if not, after implementing the handler change, add:

```python
def test_fc_wwpn_export_handler_filters_by_groups(tmp_path, monkeypatch):
    # Construct minimal HealthServer + handler call OR
    # assert filter integration via a thin wrapper function extracted in health_server
    ...
```

Simplest reliable approach for this codebase: extract a tiny function in `fc_wwpn_export.py`:

```python
def cards_for_fc_export(cards: list[dict], groups: set[str] | None) -> list[dict]:
    from launchpad.snapshot_schedule_export import filter_cards_by_groups
    return filter_cards_by_groups(list(cards), groups)
```

Call it from the handler. Test `cards_for_fc_export` in `tests/test_fc_wwpn_export_groups.py`.

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_fc_wwpn_export_groups.py -v
```

Expected: FAIL until `cards_for_fc_export` exists (site_group tests may already PASS).

- [ ] **Step 3: Implement export filtering**

1. Add `cards_for_fc_export` to `launchpad/fc_wwpn_export.py` as above.
2. In `health_server.py` `/api/fc-wwpn-export`: parse `groups` like snapshot export; `cards = cards_for_fc_export(cards, groups)` before `build_fc_wwpn_workbook(cards)`.
3. Default omitted `groups` query → `{"wag1","wag2","other"}`.

- [ ] **Step 4: Run GREEN**

```powershell
python -m pytest tests/test_fc_wwpn_export_groups.py tests/test_fc_wwpn_filter.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/fc_wwpn_export.py launchpad/health_server.py tests/test_fc_wwpn_export_groups.py
git commit -m "Filter FC WWPN Excel export by WAG include groups."
```

---

### Task 3: Include bar + search UI in FC WWPN report

**Files:**
- Modify: `launchpad/fc_wwpn_report.py`
- Create: `tests/test_fc_wwpn_page.py`

**Interfaces:**
- Consumes: Task 1 matcher rules (mirror in JS); Task 2 `groups=` export query
- Produces: page with include bar + search; `render()` applies include ∩ search ∩ contingency group; Excel URL includes `groups`

**UI (place below hero-actions, similar to Snapshot Schedule `.site-filters`):**

```html
<div class="site-filters no-print" id="site-filters">
  <span class="filter-label">Include in list / Excel</span>
  <label class="filter-check" for="filter-wag1">
    <input type="checkbox" id="filter-wag1" checked>
    WAG1
  </label>
  <label class="filter-check" for="filter-wag2">
    <input type="checkbox" id="filter-wag2" checked>
    WAG2
  </label>
  <label class="filter-check" for="filter-other">
    <input type="checkbox" id="filter-other" checked>
    Other sites
  </label>
  <span class="filter-hint">Uncheck a group to hide it from the report and export.</span>
</div>
<div class="search-row no-print">
  <input type="search" id="fc-search" placeholder="Search WWPN, remote WWPN, host, or volume…" aria-label="Search FC inventory">
</div>
```

Copy relevant CSS from Snapshot Schedule for `.site-filters` / `.filter-check` / `.filter-label` / `.filter-hint` (adapt colors to FC WWPN variables). Add `.site.highlight` outline for first search match.

**JS requirements:**

1. `siteGroup(card)` — same rules as Python `site_group` (haystack of name/category/host/model/device_profile; wag1/wag2/other).
2. `selectedSiteGroups()` → `["wag1","wag2","other"]` from checked boxes.
3. `cardMatchesSearch(card, query)` — mirror `fc_wwpn_filter.card_matches_search` (including `fc_ports_by_node`).
4. Update `render()`:
   - Start from `cardsCache.filter(isSvcLike)`.
   - Filter by `selectedSiteGroups()` via `siteGroup`.
   - Apply `filterCardByGroup(card, activeGroup())` as today (keep cards that still have useful FC rows **or** keep current behavior of mapping filtered card — if filtered card has zero hosts/maps/ports after group filter, still show only when contingency group is unset; preserve existing semantics).
   - Filter by `cardMatchesSearch`.
   - Update status: `Showing N of T site(s)` where T is SVC-like count before include/search (or before all filters — use: T = svc-like in cache; N = rendered count). When search non-empty, append ` · search matched`.
   - After render, if search non-empty and first `.site` exists: `scrollIntoView` + add `highlight` class briefly.
5. `downloadExcel()`:
   - If `selectedSiteGroups()` empty → status `Select at least one group (WAG1, WAG2, or Other) before exporting.` and return.
   - `fetch(`/api/fc-wwpn-export?open=1&groups=${groups.join(",")}`)`.
6. Wire `input`/`change` on search + checkboxes to `render()`.

Comment in JS: `// Keep cardMatchesSearch in sync with launchpad.fc_wwpn_filter.card_matches_search`

- [ ] **Step 1: Write failing page tests**

Create `tests/test_fc_wwpn_page.py`:

```python
from launchpad.fc_wwpn_report import FC_WWPN_REPORT_HTML


def test_fc_wwpn_page_has_include_bar_and_search():
    html = FC_WWPN_REPORT_HTML
    assert "Include in list / Excel" in html
    assert 'id="filter-wag1"' in html
    assert 'id="filter-wag2"' in html
    assert 'id="filter-other"' in html
    assert "Uncheck a group to hide it from the report and export." in html
    assert 'id="fc-search"' in html
    assert "Search WWPN, remote WWPN, host, or volume" in html


def test_fc_wwpn_excel_passes_groups_query():
    html = FC_WWPN_REPORT_HTML
    assert "groups=" in html or "groups:${" in html or 'groups=${' in html
    assert "selectedSiteGroups" in html
    assert "cardMatchesSearch" in html
    assert "siteGroup" in html
```

Confirm export symbol name: the HTML constant may be `FC_WWPN_REPORT_HTML` — check `fc_wwpn_report.py` top-level name and import that.

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_fc_wwpn_page.py -v
```

Expected: FAIL (missing strings).

- [ ] **Step 3: Implement UI + JS filters**

Edit `launchpad/fc_wwpn_report.py` per requirements above.

- [ ] **Step 4: Run GREEN**

```powershell
python -m pytest tests/test_fc_wwpn_page.py tests/test_fc_wwpn_filter.py tests/test_fc_wwpn_export_groups.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/fc_wwpn_report.py tests/test_fc_wwpn_page.py
git commit -m "Add FC WWPN search and WAG include filters to the report UI."
```

---

### Task 4: Version bump + verification

**Files:**
- Modify: `launchpad/config.py`

**Interfaces:**
- Produces: `APP_VERSION == "1.6.49"`

- [ ] **Step 1: Bump version**

```python
APP_VERSION = "1.6.49"
```

- [ ] **Step 2: Run targeted suite**

```powershell
python -m pytest tests/test_fc_wwpn_filter.py tests/test_fc_wwpn_export_groups.py tests/test_fc_wwpn_page.py tests/test_snapshot_schedule_export.py -v
python -c "from launchpad.config import APP_VERSION; assert APP_VERSION == '1.6.49'"
```

Expected: PASS.

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version to 1.6.49 for FC WWPN search and include filters."
```

---

## Spec coverage checklist (self-review)

| Spec requirement | Task |
|------------------|------|
| One search box; hide non-matches; highlight first | Task 3 |
| Match WWPN / remote WWPN / host / volume | Tasks 1, 3 |
| Include WAG1/WAG2/Other; report hint wording | Task 3 |
| Excel respects include groups | Tasks 2, 3 |
| Search does not filter Excel | Tasks 2–3 (URL has groups only) |
| Reuse `site_group` / `filter_cards_by_groups` | Task 2 |
| Contingency-group filter still applied | Task 3 (`filterCardByGroup`) |
| Version bump | Task 4 |
| No Capacity/Snapshot Schedule UI changes | (non-goal) |
