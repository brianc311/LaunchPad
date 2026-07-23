# FC WWPN Search + WAG Include Bar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add FC WWPN search (WWPN / remote / host / volume) that sets the Site picker, with client-then-server find, plus a WAG1/WAG2/Other include bar for list and Excel.

**Architecture:** Pure matcher in `fc_wwpn_search.py` (port/adapt from PR #16 `fc_wwpn_filter.py`). Page runs client match → set Site; on miss calls `GET /api/fc-wwpn-find`. WAG checkboxes filter via `site_group` / `filter_cards_by_groups`; Excel passes `groups=`.

**Tech Stack:** Embedded HTML/JS, HealthServer, existing snapshot schedule group helpers, pytest.

**Spec:** `docs/superpowers/specs/2026-07-23-fc-wwpn-search-wag-design.md`

## Global Constraints

- **Worktree:** `.worktrees/fc-wwpn-search` on `feature/fc-wwpn-search-site` (from contingency-groups @ 1.6.52)
- Search drives **Site picker** (not Contingency-group filter)
- Match: normalized WWPN substring + host/volume text
- Find: **client first**, then **`/api/fc-wwpn-find`**
- WAG1 / WAG2 / Other default all on; filter list + Excel
- Do not remove Site picker or modal mappings export
- Bump `APP_VERSION` to **1.6.53**
- Prefer porting PR #16 matcher/tests (`fc_wwpn_filter` → `fc_wwpn_search` rename per spec) rather than inventing a second matcher
- Commit at each task’s commit step
- Run from: `cd C:\Users\BrianColley\LaunchPad\.worktrees\fc-wwpn-search`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/fc_wwpn_search.py` | `normalize_wwpn`, `card_matches_fc_query`, `find_cards_matching_fc_query` |
| `launchpad/fc_wwpn_export.py` | `parse_fc_export_groups`, `cards_for_fc_export` (from PR #16) |
| `launchpad/health_server.py` | `GET /api/fc-wwpn-find`; wire `groups=` on `/api/fc-wwpn-export` |
| `launchpad/fc_wwpn_report.py` | Search UI; client→server find; set Site; WAG bar; export `groups=` |
| `launchpad/config.py` | `1.6.53` |
| `tests/test_fc_wwpn_search.py` | Matcher + find helpers |
| `tests/test_fc_wwpn_find_api.py` or extend search tests | API contract / handler source |
| `tests/test_contingency_groups_page.py` or page tests in search file | HTML wiring |

---

### Task 0: Confirm baseline

**Files:** none

- [ ] **Step 1: Confirm worktree**

```powershell
cd C:\Users\BrianColley\LaunchPad\.worktrees\fc-wwpn-search
git status -sb
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-23-fc-wwpn-search-wag-design.md
```

Expected: `feature/fc-wwpn-search-site`, `1.6.52`, design `True`.

- [ ] **Step 2: No feature commit**

---

### Task 1: Pure search matcher

**Files:**
- Create: `launchpad/fc_wwpn_search.py`
- Create: `tests/test_fc_wwpn_search.py`

**Interfaces:**
- Produces:
  - `normalize_wwpn(value: str) -> str`
  - `card_matches_fc_query(card: dict, query: str) -> bool`  # empty query → True (no filter)
  - `find_cards_matching_fc_query(cards: list[dict], query: str) -> list[dict]`  # empty query → []; non-empty → matching cards sorted by name

- [ ] **Step 1: Write failing tests**

Port/adapt from PR #16 `tests/test_fc_wwpn_filter.py` into `tests/test_fc_wwpn_search.py`, renaming to `card_matches_fc_query` / `normalize_wwpn`. Include:

```python
from launchpad.fc_wwpn_search import (
    card_matches_fc_query,
    find_cards_matching_fc_query,
    normalize_wwpn,
)


def test_normalize_wwpn_strips_colons_and_spaces():
    assert normalize_wwpn("10:00:00:00:c9:a1:b2:c3") == "10000000C9A1B2C3"


def test_empty_query_matches_all_for_filter_semantics():
    card = {"name": "Site", "fc_ports": [], "fc_hosts": [], "fc_mappings": [], "fc_fabric": []}
    assert card_matches_fc_query(card, "") is True


def test_find_empty_query_returns_no_matches():
    cards = [{"id": 1, "name": "A", "fc_ports": [{"wwpn": "AA"}]}]
    assert find_cards_matching_fc_query(cards, "") == []
    assert find_cards_matching_fc_query(cards, "   ") == []


def test_matches_local_and_remote_wwpn():
    card = {
        "name": "Carolina, PR",
        "fc_ports": [{"wwpn": "10:00:00:00:c9:a1:b2:c3", "remote_wwpns": "20:00:00:00:11:22:33:44"}],
        "fc_hosts": [],
        "fc_mappings": [],
        "fc_fabric": [{"local_wwpn": "AA", "remote_wwpn": "BB:CC", "host_name": ""}],
    }
    assert card_matches_fc_query(card, "c9a1b2c3") is True
    assert card_matches_fc_query(card, "2000000011223344") is True
    assert card_matches_fc_query(card, "deadbeef") is False


def test_matches_host_and_volume_names():
    card = {
        "name": "Hartford, CT",
        "fc_ports": [],
        "fc_hosts": [{"host_name": "pconsps3", "wwpns": "AA:BB"}],
        "fc_mappings": [{"vdisk_name": "pconsps_archvg_1", "host_name": "pconsps3"}],
        "fc_fabric": [],
    }
    assert card_matches_fc_query(card, "pconsps3") is True
    assert card_matches_fc_query(card, "archvg") is True


def test_find_sorts_by_name_and_returns_hits_only():
    cards = [
        {"id": 2, "name": "Zed", "fc_ports": [{"wwpn": "AA"}], "fc_hosts": [], "fc_mappings": [], "fc_fabric": []},
        {"id": 1, "name": "Alpha", "fc_ports": [{"wwpn": "AA"}], "fc_hosts": [], "fc_mappings": [], "fc_fabric": []},
        {"id": 3, "name": "Other", "fc_ports": [{"wwpn": "BB"}], "fc_hosts": [], "fc_mappings": [], "fc_fabric": []},
    ]
    found = find_cards_matching_fc_query(cards, "AA")
    assert [c["name"] for c in found] == ["Alpha", "Zed"]
```

Also port `test_matches_fc_ports_by_node_only`, `test_concatenated_wwpn_fields_do_not_false_positive` from PR #16.

- [ ] **Step 2: Run tests — expect FAIL**

```powershell
python -m pytest tests/test_fc_wwpn_search.py -v
```

- [ ] **Step 3: Implement `fc_wwpn_search.py`**

Cherry-pick logic from `origin/feature/fc-wwpn-search-filter:launchpad/fc_wwpn_filter.py` (or copy file and rename functions). Ensure:

- WWPN fields checked individually (no false positive from concatenating adjacent WWPNs)
- Include `fc_ports`, `fc_ports_by_node[].ports`, `fc_fabric` local/remote, host names, mapping host/vdisk names
- `find_cards_matching_fc_query`: if `not str(query).strip()` return `[]`; else filter with `card_matches_fc_query` and sort by `name` case-insensitive

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```powershell
git add launchpad/fc_wwpn_search.py tests/test_fc_wwpn_search.py
git commit -m "Add FC WWPN search matcher for WWPN, host, and volume queries."
```

---

### Task 2: Find API + Excel groups= wiring

**Files:**
- Modify: `launchpad/fc_wwpn_export.py` (add `parse_fc_export_groups`, `cards_for_fc_export` from PR #16)
- Modify: `launchpad/health_server.py`
- Modify: `tests/test_fc_wwpn_search.py` (API source contract) and/or `tests/test_fc_wwpn_export_filter.py`

**Interfaces:**
- `GET /api/fc-wwpn-find?q=` → `{query, matches:[{id,name},...]}`; empty q → 400 `q required`
- `/api/fc-wwpn-export` applies `parse_fc_export_groups` + `cards_for_fc_export` before existing `filter_cards_for_fc_export` / workbook build

- [ ] **Step 1: Failing tests**

```python
from pathlib import Path
from launchpad import health_server as health_server_mod
from launchpad.fc_wwpn_export import parse_fc_export_groups, DEFAULT_FC_EXPORT_GROUPS


def test_parse_fc_export_groups_defaults_and_empty():
    assert parse_fc_export_groups({}) == set(DEFAULT_FC_EXPORT_GROUPS)
    assert parse_fc_export_groups({"groups": [""]}) == set()
    assert parse_fc_export_groups({"groups": ["wag1,other"]}) == {"wag1", "other"}


def test_health_server_exposes_fc_wwpn_find_route():
    source = Path(health_server_mod.__file__).read_text(encoding="utf-8")
    assert 'path == "/api/fc-wwpn-find"' in source
    assert "find_cards_matching_fc_query" in source
    assert '"q required"' in source
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement export group helpers + API**

Add to `fc_wwpn_export.py` (from PR #16):

```python
from launchpad.snapshot_schedule_export import filter_cards_by_groups

DEFAULT_FC_EXPORT_GROUPS = frozenset({"wag1", "wag2", "other"})


def parse_fc_export_groups(query: dict[str, list[str]]) -> set[str]:
    if "groups" not in query:
        return set(DEFAULT_FC_EXPORT_GROUPS)
    return {
        part.strip().lower()
        for raw in query.get("groups") or [""]
        for part in str(raw).split(",")
        if part.strip()
    }


def cards_for_fc_export(cards, groups):
    return filter_cards_by_groups(list(cards), groups)
```

In `health_server.py` GET handler (near other fc-wwpn routes):

```python
if path == "/api/fc-wwpn-find":
    from launchpad.fc_wwpn_search import find_cards_matching_fc_query
    from launchpad.storage_presets import is_svc_fc_profile
    query = parse_qs(parsed.query)
    q = (query.get("q") or [""])[0]
    if not str(q).strip():
        self._send_json({"error": "q required"}, status=400)
        return
    server.sync_from_app()
    cards = [
        card for card in server.list_cards(allow_sync=False)
        if is_svc_fc_profile(str(card.get("device_profile") or ""))
        or bool(card.get("fc_available"))
    ]
    # list_cards returns API dicts via to_api — ensure matcher sees fc_* fields
    matches = find_cards_matching_fc_query(cards, q)
    self._send_json({
        "query": q,
        "matches": [{"id": c.get("id"), "name": c.get("name")} for c in matches],
    })
    return
```

Update `/api/fc-wwpn-export` to parse groups and filter with `cards_for_fc_export` before card_id filter (order: FC-eligible → groups → card_id).

- [ ] **Step 4: Run tests — PASS**

- [ ] **Step 5: Commit**

```powershell
git commit -m "Add FC WWPN find API and WAG groups filter for Excel export."
```

---

### Task 3: Page UI — search + WAG + Site

**Files:**
- Modify: `launchpad/fc_wwpn_report.py`
- Tests: page contract assertions

**Interfaces:**
- Search input + Find; client `find` using same field rules (duplicate minimal JS matcher OR fetch find API always after local scan of `cardsCache`)
- On hits: set `activeSiteId`, update Site select, `render()`, status message
- On miss: `fetch('/api/fc-wwpn-find?q=')`; if matches, set Site; else not-found status
- WAG checkboxes; `includedGroups()`; filter before Site filter in `render()`; Excel adds `groups=`

Recommended client approach (keep DRY with server):

1. Local scan of `cardsCache` with JS port of matcher (or call find API only — simpler but always hits server). **Spec wants client first:** implement a small JS `cardMatchesQuery(card, q)` mirroring Python fields, then server fallback.

- [ ] **Step 1: Failing page tests**

```python
from launchpad.fc_wwpn_report import FC_WWPN_REPORT_HTML

def test_fc_wwpn_exposes_search_and_wag_controls():
    for text in (
        'id="fc-search"',
        "Search WWPN, remote WWPN, host, or volume",
        'id="fc-search-btn"',
        "function runFcSearch(",
        "/api/fc-wwpn-find",
        "can't locate site",
        'id="filter-wag1"',
        'id="filter-wag2"',
        'id="filter-other"',
        "groups=",
    ):
        assert text in FC_WWPN_REPORT_HTML
```

- [ ] **Step 2: FAIL then implement UI**

Hero additions:

```html
<input type="search" id="fc-search" placeholder="Search WWPN, remote WWPN, host, or volume…" aria-label="Search FC inventory">
<button type="button" id="fc-search-btn" class="btn secondary">Find</button>
```

WAG bar (from PR #16 styling), default checked.

JS outline:

```javascript
function runFcSearch() {
  const q = (searchInput.value || "").trim();
  if (!q) { statusEl.textContent = "Enter a WWPN, host, or volume to find."; return; }
  let matches = cardsCache.filter(isSvcLike).filter((c) => cardMatchesQuery(c, q));
  const finish = (list) => {
    if (!list.length) {
      activeSiteId = "";
      updateSiteOptions();
      render();
      statusEl.textContent = `WWPN not found — can't locate site`;
      return;
    }
    list = list.slice().sort((a,b) => String(a.name||"").localeCompare(String(b.name||""), undefined, {sensitivity:"base"}));
    activeSiteId = String(list[0].id);
    updateSiteOptions();
    render();
    const extra = list.length - 1;
    statusEl.textContent = extra
      ? `Found on ${list[0].name} (also on ${extra} other site(s))`
      : `Found on ${list[0].name}`;
  };
  if (matches.length) { finish(matches); return; }
  fetch(`/api/fc-wwpn-find?q=${encodeURIComponent(q)}`)
    .then((r) => r.json())
    .then((payload) => {
      const ids = new Set((payload.matches || []).map((m) => String(m.id)));
      finish(cardsCache.filter((c) => ids.has(String(c.id))));
      // If server found ids not in cache, still set activeSiteId from payload.matches[0]
    })
    .catch((err) => { statusEl.textContent = `Search failed: ${err.message || err}`; });
}
```

Handle server-only hit when card not in cache: set `activeSiteId` from `payload.matches[0].id`, status Found on name, `render()` may show “Selected site not found” until refresh — acceptable; or trigger loadCards first.

WAG: filter `isSvcLike` cards with `siteGroup(card)` in checked set before Site filter (port `site_group` logic from snapshot schedule JS or inline category/name heuristics matching Python).

Excel `downloadExcel`: append `groups=` from checked boxes.

- [ ] **Step 3: PASS + commit**

```powershell
git commit -m "Add FC WWPN Find search and WAG include bar on the report page."
```

---

### Task 4: Version bump

- [ ] Set `APP_VERSION = "1.6.53"`
- [ ] Run: `pytest tests/test_fc_wwpn_search.py tests/test_fc_wwpn_export_filter.py tests/test_contingency_groups_page.py -q`
- [ ] Commit: `Bump version to 1.6.53 for FC WWPN search and WAG filters.`

---

## Spec coverage

| Requirement | Task |
|-------------|------|
| Matcher WWPN/host/volume | Task 1 |
| Find API | Task 2 |
| Client then server → Site | Task 3 |
| WAG bar + Excel groups | Tasks 2–3 |
| Version | Task 4 |
