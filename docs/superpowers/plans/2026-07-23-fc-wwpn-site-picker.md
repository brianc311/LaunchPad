# FC WWPN Site Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the FC WWPN Contingency-group filter with a Site picker so None shows all site cards, a selected site shows only that card, and Excel export follows the same selection.

**Architecture:** Client-side filter in `fc_wwpn_report.py` (`render()` keeps SVC-like cards matching `activeSiteId`, or all when empty). Remove Contingency-group filter helpers and `/api/contingency-groups` load used only for that dropdown. `/api/fc-wwpn-export` accepts optional `card_id` / `card_name` and filters the card list before `build_fc_wwpn_workbook`. Pure helper `filter_cards_for_fc_export` lives in `fc_wwpn_export.py` for unit tests.

**Tech Stack:** Embedded HTML/JS page, HealthServer GET export, openpyxl workbook builder, pytest string/API tests.

**Spec:** `docs/superpowers/specs/2026-07-23-fc-wwpn-site-picker-design.md`

## Global Constraints

- **Base / worktree:** `feature/fc-wwpn-site-picker` at `.worktrees/fc-wwpn-site-picker` (from `feature/contingency-groups` @ `a83b683`, tip version `1.6.47`)
- Replace Contingency-group dropdown with **Site** picker (do **not** keep both)
- **None** = all SVC/FlashSystem-like cards; pick site = that card only
- Label: **Site**; first option **None** (empty value); options = card names sorted A–Z; value = card id
- Optional URL sync: `?site=<card_id>` (replace former `?group=`)
- Keep **Contingency Groups** nav link → `/contingency-groups`
- Excel: selected site → pass `card_id`; None → omit (all cards)
- Do **not** invent WAG/`groups=` filters on this tip (they are not present on `1.6.47`)
- Do **not** change Refresh On Sites or Capacity Report
- Bump `APP_VERSION` to **1.6.48**
- Commit at each task’s commit step
- Run tests from the worktree root: `cd C:\Users\BrianColley\LaunchPad\.worktrees\fc-wwpn-site-picker`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/fc_wwpn_report.py` | Site picker UI/JS; filter in `render()`; Excel query param; drop CG filter |
| `launchpad/fc_wwpn_export.py` | `filter_cards_for_fc_export(cards, *, card_id=, card_name=)` |
| `launchpad/health_server.py` | `/api/fc-wwpn-export` reads `card_id` / `card_name`, filters before workbook |
| `launchpad/contingency_groups.py` | “Open in FC WWPN” → `/fc-wwpn` (drop obsolete `?group=`) |
| `launchpad/config.py` | `APP_VERSION = "1.6.48"` |
| `tests/test_contingency_groups_page.py` | Replace CG-filter contract tests with Site picker contracts |
| `tests/test_fc_wwpn_export_filter.py` | Pure filter helper + export query behavior |

---

### Task 0: Confirm worktree baseline

**Files:** none (git only)

**Interfaces:**
- Consumes: existing `.worktrees/fc-wwpn-site-picker` on `feature/fc-wwpn-site-picker`
- Produces: confirmed baseline for Tasks 1–3

- [ ] **Step 1: Confirm branch, version, design spec**

```powershell
cd C:\Users\BrianColley\LaunchPad\.worktrees\fc-wwpn-site-picker
git status -sb
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-23-fc-wwpn-site-picker-design.md
```

Expected: branch `feature/fc-wwpn-site-picker`, version `1.6.47`, design path `True`.

- [ ] **Step 2: No feature commit**

---

### Task 1: Site picker page (replace Contingency-group filter)

**Files:**
- Modify: `launchpad/fc_wwpn_report.py`
- Modify: `launchpad/contingency_groups.py` (Open in FC WWPN link only)
- Modify: `tests/test_contingency_groups_page.py`

**Interfaces:**
- Consumes: `/api/cards` payloads with `id`, `name`, `device_profile`, `fc_available`
- Produces: page contract — `id="site-select"`, label/aria **Site**, `activeSiteId` from `?site=`, `updateSiteOptions()`, `render()` filters by card id; no `filterCardByGroup` / `loadGroups` / `group-select`

- [ ] **Step 1: Write the failing tests**

Replace the Contingency-group filter tests in `tests/test_contingency_groups_page.py` with:

```python
def test_fc_wwpn_report_links_to_contingency_groups():
    assert 'href="/contingency-groups">Contingency Groups</a>' in FC_WWPN_REPORT_HTML


def test_fc_wwpn_report_exposes_site_picker_contract():
    for text in (
        'id="site-select"',
        'aria-label="Site"',
        ">Site</label>",
        'option value="">None</option>',
        "function updateSiteOptions(",
        "function filterCardsBySite(",
        'new URLSearchParams(window.location.search).get("site")',
        'url.searchParams.set("site"',
        'url.searchParams.delete("site")',
    ):
        assert text in FC_WWPN_REPORT_HTML
    for text in (
        'id="group-select"',
        'aria-label="Contingency group"',
        'fetch("/api/contingency-groups")',
        "function filterCardByGroup(",
        "function groupMatchesHost(",
        "function loadGroups(",
        'get("group")',
    ):
        assert text not in FC_WWPN_REPORT_HTML


def test_fc_wwpn_map_modal_uses_filtered_card_list():
    assert "openModal(cards.find((c) => c.id === id));" in FC_WWPN_REPORT_HTML
    assert "openModal(cardsCache.find((c) => c.id === id));" not in FC_WWPN_REPORT_HTML


def test_fc_wwpn_excel_passes_selected_site():
    assert "function downloadExcel(" in FC_WWPN_REPORT_HTML
    assert 'params.set("card_id", activeSiteId)' in FC_WWPN_REPORT_HTML
    assert 'fetch(`/api/fc-wwpn-export?${params.toString()}`)' in FC_WWPN_REPORT_HTML
```

Keep `test_fc_wwpn_report_links_to_contingency_groups`. Remove `test_fc_wwpn_filter_mappings_match_host_wwpns` (CG-only).

Also add (same file or keep elsewhere if already present):

```python
def test_contingency_groups_open_fc_wwpn_without_group_query():
    assert 'window.location.assign(`/fc-wwpn?group=${encodeURIComponent(currentId)}`)' not in CONTINGENCY_GROUPS_HTML
    assert 'window.location.assign("/fc-wwpn")' in CONTINGENCY_GROUPS_HTML
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/test_contingency_groups_page.py::test_fc_wwpn_report_exposes_site_picker_contract tests/test_contingency_groups_page.py::test_fc_wwpn_excel_passes_selected_site tests/test_contingency_groups_page.py::test_contingency_groups_open_fc_wwpn_without_group_query -v
```

Expected: FAIL (old `group-select` / `?group=` still present).

- [ ] **Step 3: Implement Site picker in `fc_wwpn_report.py`**

Hero control (replace Contingency group label/select):

```html
<label for="site-select" class="status">Site</label>
<select id="site-select" class="group-filter" aria-label="Site">
  <option value="">None</option>
</select>
```

Script changes (conceptual — apply in place):

1. Rename `groupSelect` → `siteSelect` (`document.getElementById("site-select")`).
2. Replace `groupsCache` / `activeGroupId` with:

```javascript
let activeSiteId = new URLSearchParams(window.location.search).get("site") || "";
```

3. Remove: `groupHostNames`, `groupWwpns`, `groupMatchesHost`, `groupMatchesVolume`, `hostWwpns`, `filterPorts`, `filterCardByGroup`, `activeGroup`, `updateGroupOptions`, `loadGroups`, and `Promise.all([loadGroups(), loadCards()])` → call `loadCards()` only (after options helpers exist).

4. Add:

```javascript
function filterCardsBySite(cards, siteId) {
  const id = String(siteId || "").trim();
  if (!id) return cards;
  return cards.filter((card) => String(card.id) === id);
}

function updateSiteOptions() {
  const svcCards = cardsCache.filter(isSvcLike).slice().sort((a, b) =>
    String(a.name || "").localeCompare(String(b.name || ""), undefined, { sensitivity: "base" })
  );
  const selected = svcCards.some((card) => String(card.id) === String(activeSiteId))
    ? String(activeSiteId) : "";
  activeSiteId = selected;
  siteSelect.innerHTML = '<option value="">None</option>' + svcCards.map((card) =>
    `<option value="${escapeHtml(card.id)}">${escapeHtml(card.name || card.id)}</option>`
  ).join("");
  siteSelect.value = selected;
}

function render() {
  const all = cardsCache.filter(isSvcLike);
  updateSiteOptions();
  const cards = filterCardsBySite(all, activeSiteId);
  if (!all.length) {
    sitesEl.innerHTML = '<p class="empty">No storage sites with FC data. Register IBM FlashSystem/Storwize/SVC cards, load presets, monitor, and refresh.</p>';
    return;
  }
  if (activeSiteId && !cards.length) {
    sitesEl.innerHTML = '<p class="empty">Selected site not found in the loaded card list.</p>';
    return;
  }
  sitesEl.innerHTML = cards.map(renderSite).join("");
  sitesEl.querySelectorAll(".map-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = Number(btn.getAttribute("data-id"));
      openModal(cards.find((c) => c.id === id));
    });
  });
  if (activeSiteId) {
    statusEl.textContent = `Showing ${cards.length} of ${all.length} site(s)`;
  }
}
```

5. Change listener:

```javascript
siteSelect.addEventListener("change", () => {
  activeSiteId = siteSelect.value;
  const url = new URL(window.location.href);
  if (activeSiteId) url.searchParams.set("site", activeSiteId);
  else url.searchParams.delete("site");
  url.searchParams.delete("group");
  window.history.replaceState({}, "", url);
  render();
});
```

6. Update `downloadExcel` to pass `card_id` when a site is selected (required by tests; API implemented in Task 2):

```javascript
async function downloadExcel() {
  excelBtn.disabled = true;
  statusEl.textContent = "Building Excel workbook…";
  try {
    const params = new URLSearchParams({ open: "1" });
    if (activeSiteId) params.set("card_id", activeSiteId);
    const res = await fetch(`/api/fc-wwpn-export?${params.toString()}`);
    // … keep existing blob / error handling …
  } catch (err) {
    statusEl.textContent = `Excel export failed: ${err.message || err}`;
  } finally {
    excelBtn.disabled = false;
  }
}
```

7. In `loadCards`, after assigning `cardsCache`, call `render()` (which calls `updateSiteOptions`). Avoid overwriting a useful status with the “Showing…” line only when filtered — if you set `${cardsCache.length} site(s) loaded` before `render()`, let `render()` overwrite when `activeSiteId` is set.

- [ ] **Step 4: Fix Contingency Groups deep link**

In `launchpad/contingency_groups.py`, change the Open in FC WWPN handler from:

```javascript
window.location.assign(`/fc-wwpn?group=${encodeURIComponent(currentId)}`);
```

to:

```javascript
window.location.assign("/fc-wwpn");
```

- [ ] **Step 5: Run tests to verify they pass**

```powershell
python -m pytest tests/test_contingency_groups_page.py -v
```

Expected: PASS (all tests in that file).

- [ ] **Step 6: Commit**

```powershell
git add launchpad/fc_wwpn_report.py launchpad/contingency_groups.py tests/test_contingency_groups_page.py
git commit -m "Replace FC WWPN Contingency-group filter with Site picker."
```

---

### Task 2: Export API filters by selected card

**Files:**
- Modify: `launchpad/fc_wwpn_export.py`
- Modify: `launchpad/health_server.py` (`/api/fc-wwpn-export` block ~1916–1960)
- Create: `tests/test_fc_wwpn_export_filter.py`

**Interfaces:**
- Consumes: FC-eligible card dicts from `server.list_cards`
- Produces:
  - `filter_cards_for_fc_export(cards: list[dict[str, Any]], *, card_id: str | None = None, card_name: str | None = None) -> list[dict[str, Any]]`
  - Export query: optional `card_id` (preferred) and/or `card_name` (case-insensitive exact name)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_fc_wwpn_export_filter.py`:

```python
from launchpad.fc_wwpn_export import filter_cards_for_fc_export


def _card(cid: int, name: str) -> dict:
    return {"id": cid, "name": name, "device_profile": "flashsystem_7200", "fc_available": True}


def test_filter_cards_for_fc_export_none_returns_all():
    cards = [_card(1, "Hartford, CT"), _card(2, "Anderson, SC")]
    assert filter_cards_for_fc_export(cards) == cards
    assert filter_cards_for_fc_export(cards, card_id="", card_name="") == cards


def test_filter_cards_for_fc_export_by_card_id():
    cards = [_card(1, "Hartford, CT"), _card(2, "Anderson, SC")]
    out = filter_cards_for_fc_export(cards, card_id="2")
    assert [c["id"] for c in out] == [2]


def test_filter_cards_for_fc_export_by_card_name_case_insensitive():
    cards = [_card(1, "Hartford, CT"), _card(2, "Anderson, SC")]
    out = filter_cards_for_fc_export(cards, card_name="hartford, ct")
    assert [c["id"] for c in out] == [1]


def test_filter_cards_for_fc_export_card_id_wins_over_name():
    cards = [_card(1, "Hartford, CT"), _card(2, "Anderson, SC")]
    out = filter_cards_for_fc_export(cards, card_id="2", card_name="Hartford, CT")
    assert [c["id"] for c in out] == [2]


def test_filter_cards_for_fc_export_unknown_id_returns_empty():
    cards = [_card(1, "Hartford, CT")]
    assert filter_cards_for_fc_export(cards, card_id="99") == []
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/test_fc_wwpn_export_filter.py -v
```

Expected: FAIL with `ImportError` / attribute missing for `filter_cards_for_fc_export`.

- [ ] **Step 3: Implement `filter_cards_for_fc_export`**

Add to `launchpad/fc_wwpn_export.py` (near top after imports / before `build_fc_wwpn_workbook`):

```python
def filter_cards_for_fc_export(
    cards: list[dict[str, Any]],
    *,
    card_id: str | None = None,
    card_name: str | None = None,
) -> list[dict[str, Any]]:
    cid = str(card_id or "").strip()
    if cid:
        return [card for card in cards if str(card.get("id", "")) == cid]
    name = str(card_name or "").strip().lower()
    if name:
        return [
            card
            for card in cards
            if str(card.get("name") or "").strip().lower() == name
        ]
    return list(cards)
```

Ensure `Any` is imported from `typing` if not already.

- [ ] **Step 4: Wire `/api/fc-wwpn-export`**

In `launchpad/health_server.py`, inside the `path == "/api/fc-wwpn-export"` block, after building the FC-eligible `cards` list and before `build_fc_wwpn_workbook(cards)`:

```python
from launchpad.fc_wwpn_export import (
    build_fc_wwpn_workbook,
    filter_cards_for_fc_export,
    workbook_to_bytes,
)

# … existing open_after / try …
card_id = (query.get("card_id") or [""])[0].strip()
card_name = (query.get("card_name") or [""])[0].strip()
cards = filter_cards_for_fc_export(
    cards, card_id=card_id or None, card_name=card_name or None
)
wb, port_count, host_count, map_count = build_fc_wwpn_workbook(cards)
```

Remove the duplicate inline `from launchpad.fc_wwpn_export import build_fc_wwpn_workbook, workbook_to_bytes` if consolidating into one import.

If `card_id` / `card_name` is provided and the filtered list is empty, still return a valid empty workbook (current `build_fc_wwpn_workbook([])` behavior) — do **not** 404.

- [ ] **Step 5: Run tests to verify they pass**

```powershell
python -m pytest tests/test_fc_wwpn_export_filter.py tests/test_contingency_groups_page.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add launchpad/fc_wwpn_export.py launchpad/health_server.py tests/test_fc_wwpn_export_filter.py
git commit -m "Filter FC WWPN Excel export by optional card_id or card_name."
```

---

### Task 3: Version bump and smoke

**Files:**
- Modify: `launchpad/config.py`

**Interfaces:**
- Consumes: Tasks 1–2 complete
- Produces: `APP_VERSION = "1.6.48"`

- [ ] **Step 1: Bump version**

In `launchpad/config.py`:

```python
APP_VERSION = "1.6.48"
```

- [ ] **Step 2: Run focused regression**

```powershell
python -m pytest tests/test_contingency_groups_page.py tests/test_fc_wwpn_export_filter.py -v
python -c "from launchpad.config import APP_VERSION; from launchpad.fc_wwpn_report import FC_WWPN_REPORT_HTML; assert APP_VERSION == '1.6.48'; assert 'id=\"site-select\"' in FC_WWPN_REPORT_HTML; assert 'id=\"group-select\"' not in FC_WWPN_REPORT_HTML; print('ok', APP_VERSION)"
```

Expected: all PASS / `ok 1.6.48`.

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version to 1.6.48 for FC WWPN Site picker."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Replace CG dropdown with Site picker | Task 1 |
| None = all; pick site = one card | Task 1 (`filterCardsBySite`) |
| Label **Site**; sorted by name; value = id | Task 1 |
| Optional `?site=` URL | Task 1 |
| Remove CG filter / `filterCardByGroup` / groups load | Task 1 |
| Keep Contingency Groups nav button | Task 1 (assert kept) |
| Excel follows selection | Task 1 client + Task 2 API |
| Do not invent WAG/`groups=` | Global constraint |
| Version next patch | Task 3 → `1.6.48` |
| Tests: Site label, no CG wiring, export by card | Tasks 1–2 |

## Self-review notes

- No dual Site + Contingency-group controls.
- Contingency Groups “Open in FC WWPN” drops obsolete `?group=` so deep links do not imply a removed filter.
- Empty filter result on export returns empty workbook (no 404).
