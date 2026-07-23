# FC WWPN Multi-line Cell Clamp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse multi-line FC WWPN report table cells to one line by default; click toggles expand; Find auto-expands matching cells; clear Find collapses all.

**Architecture:** CSS `line-clamp` on `.cell-clamp` cells in `fc_wwpn_report.py`. After each `render()`, mark multi-line `td`s and wire click. Extend `runFcSearch` to expand matches and to collapse all on empty query. Print media disables clamp.

**Tech Stack:** Embedded HTML/CSS/JS in `fc_wwpn_report.py`, pytest HTML contract tests.

**Spec:** `docs/superpowers/specs/2026-07-23-fc-wwpn-cell-clamp-design.md`

## Global Constraints

- **Worktree:** `.worktrees/fc-wwpn-cell-clamp` on `feature/fc-wwpn-cell-clamp` from `feature/contingency-groups` tip (`APP_VERSION=1.6.55`, includes cell-clamp design commit)
- FC WWPN report tables only — not LUN Builder / Consistency Groups / Capacity
- Clamp: one line + ellipsis; click toggles `is-expanded`
- Find expands matching multi-line cells on the selected site
- Empty Find / clear collapses **all** multi-line cells (manual and search)
- Print: full text (no clamp); Excel unchanged
- Bump `APP_VERSION` to **1.6.56**
- Commit at each task’s commit step
- Run from: `cd C:\Users\BrianColley\LaunchPad\.worktrees\fc-wwpn-cell-clamp`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/fc_wwpn_report.py` | CSS clamp; mark cells; click toggle; Find expand/clear; print unclamp |
| `launchpad/config.py` | `1.6.56` |
| `tests/test_fc_wwpn_page.py` | Contract tests for clamp + Find expand wiring |

---

### Task 0: Confirm baseline

**Files:** none (worktree setup only)

- [ ] **Step 1: Create worktree + branch**

```powershell
cd C:\Users\BrianColley\LaunchPad
git fetch origin
git worktree add .worktrees/fc-wwpn-cell-clamp -b feature/fc-wwpn-cell-clamp feature/contingency-groups
cd .worktrees/fc-wwpn-cell-clamp
git status -sb
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-23-fc-wwpn-cell-clamp-design.md
Test-Path docs\superpowers\plans\2026-07-23-fc-wwpn-cell-clamp.md
```

Expected: `feature/fc-wwpn-cell-clamp`, `1.6.55`, both paths `True`.

- [ ] **Step 2: No feature commit**

---

### Task 1: Clamp CSS, mark cells, click toggle, print unclamp

**Files:**
- Modify: `launchpad/fc_wwpn_report.py` (styles + JS helpers + post-render)
- Modify: `tests/test_fc_wwpn_page.py`

**Interfaces:**
- Produces (in page JS):
  - `function cellNeedsClamp(td)` — true if text has newline, `;`, or scrollHeight > clientHeight + 1
  - `function applyCellClamps(root)` — mark `td` under `root` (default `#sites`) with `cell-clamp`, set `title` / `aria-expanded="false"`, remove stale `is-expanded`
  - `function collapseAllClampedCells(root)` — remove `is-expanded` from all `.cell-clamp` under root
  - Click delegation on `#sites`: toggle `is-expanded` + `aria-expanded` on `.cell-clamp` clicks
- CSS: `.cell-clamp` line-clamp 1; `.cell-clamp.is-expanded` no clamp; `@media print` unclamp

- [ ] **Step 1: Write failing page contract tests**

Add to `tests/test_fc_wwpn_page.py`:

```python
def test_fc_wwpn_exposes_cell_clamp_controls():
    for text in (
        ".cell-clamp",
        "is-expanded",
        "function applyCellClamps(",
        "function collapseAllClampedCells(",
        "function cellNeedsClamp(",
        'aria-expanded',
        "Click to expand",
    ):
        assert text in FC_WWPN_REPORT_HTML
    assert "@media print" in FC_WWPN_REPORT_HTML
    # print must disable clamp
    assert "cell-clamp" in FC_WWPN_REPORT_HTML
    print_block = FC_WWPN_REPORT_HTML[
        FC_WWPN_REPORT_HTML.index("@media print") : FC_WWPN_REPORT_HTML.index("</style>")
    ]
    assert "line-clamp: none" in print_block or "-webkit-line-clamp: unset" in print_block or "overflow: visible" in print_block
```

- [ ] **Step 2: Run to verify fail**

```powershell
cd C:\Users\BrianColley\LaunchPad\.worktrees\fc-wwpn-cell-clamp
python -m pytest tests/test_fc_wwpn_page.py::test_fc_wwpn_exposes_cell_clamp_controls -v
```

Expected: FAIL (missing symbols).

- [ ] **Step 3: Add CSS**

In the `<style>` block of `fc_wwpn_report.py`, after `td.mono { ... }`:

```css
    td.cell-clamp {
      cursor: pointer;
      max-width: 28rem;
      display: -webkit-box;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: normal;
      word-break: break-all;
    }
    td.cell-clamp.is-expanded {
      display: table-cell;
      -webkit-line-clamp: unset;
      overflow: visible;
      max-width: none;
    }
```

Inside `@media print { ... }` add:

```css
      td.cell-clamp, td.cell-clamp.is-expanded {
        display: table-cell;
        -webkit-line-clamp: unset;
        overflow: visible;
        max-width: none;
      }
```

- [ ] **Step 4: Add JS helpers and wire after render**

Near other helpers in the page script, add:

```javascript
    function cellNeedsClamp(td) {
      const text = (td.textContent || "").trim();
      if (!text) return false;
      if (text.includes("\n") || text.includes(";")) return true;
      return td.scrollHeight > td.clientHeight + 1;
    }

    function collapseAllClampedCells(root) {
      const scope = root || document.getElementById("sites");
      if (!scope) return;
      scope.querySelectorAll("td.cell-clamp.is-expanded").forEach((td) => {
        td.classList.remove("is-expanded");
        td.setAttribute("aria-expanded", "false");
      });
    }

    function applyCellClamps(root) {
      const scope = root || document.getElementById("sites");
      if (!scope) return;
      scope.querySelectorAll("td").forEach((td) => {
        td.classList.remove("cell-clamp", "is-expanded");
        td.removeAttribute("aria-expanded");
        td.removeAttribute("title");
        if (!cellNeedsClamp(td)) return;
        td.classList.add("cell-clamp");
        td.setAttribute("aria-expanded", "false");
        td.title = "Click to expand";
      });
    }
```

After the main `render()` finishes writing `#sites` HTML (end of `render` / wherever cards are inserted), call `applyCellClamps()`.

Also call `applyCellClamps()` after any path that re-renders site tables (including Find’s `render()`).

Wire click once (near other listeners):

```javascript
    document.getElementById("sites").addEventListener("click", (event) => {
      const td = event.target.closest("td.cell-clamp");
      if (!td || !document.getElementById("sites").contains(td)) return;
      const open = !td.classList.contains("is-expanded");
      td.classList.toggle("is-expanded", open);
      td.setAttribute("aria-expanded", open ? "true" : "false");
      td.title = open ? "Click to collapse" : "Click to expand";
    });
```

- [ ] **Step 5: Run tests**

```powershell
python -m pytest tests/test_fc_wwpn_page.py -q
```

Expected: PASS (including existing search/WAG contracts).

- [ ] **Step 6: Commit**

```powershell
git add launchpad/fc_wwpn_report.py tests/test_fc_wwpn_page.py
git commit -m "Clamp multi-line FC WWPN table cells with click to expand."
```

---

### Task 2: Find expands matches; empty Find collapses all

**Files:**
- Modify: `launchpad/fc_wwpn_report.py` (`runFcSearch`)
- Modify: `tests/test_fc_wwpn_page.py`

**Interfaces:**
- Consumes: Task 1 `applyCellClamps`, `collapseAllClampedCells`, existing `normalizeWwpn` / `fieldMatchesWwpn` / `fieldMatchesText`
- Produces:
  - `function expandClampedCellsMatching(query, root)` — after clamps applied, expand each `.cell-clamp` whose text matches query; scroll first into view
  - `runFcSearch` empty query → `collapseAllClampedCells()` + status cleared or “Search cleared.”
  - After successful Find `render()` → `applyCellClamps()` then `expandClampedCellsMatching(q)`

- [ ] **Step 1: Write failing tests**

```python
def test_fc_wwpn_find_expands_and_clears_clamped_cells():
    for text in (
        "function expandClampedCellsMatching(",
        "collapseAllClampedCells(",
        "Search cleared.",
    ):
        assert text in FC_WWPN_REPORT_HTML
    # empty query path must collapse
    assert "if (!q)" in FC_WWPN_REPORT_HTML
    empty_idx = FC_WWPN_REPORT_HTML.index("function runFcSearch(")
    chunk = FC_WWPN_REPORT_HTML[empty_idx : empty_idx + 2500]
    assert "collapseAllClampedCells(" in chunk
    assert "expandClampedCellsMatching(" in chunk
```

- [ ] **Step 2: Run to verify fail**

```powershell
python -m pytest tests/test_fc_wwpn_page.py::test_fc_wwpn_find_expands_and_clears_clamped_cells -v
```

Expected: FAIL.

- [ ] **Step 3: Implement expand + wire Find**

```javascript
    function expandClampedCellsMatching(query, root) {
      const scope = root || document.getElementById("sites");
      if (!scope) return;
      const raw = String(query || "").trim();
      if (!raw) return;
      const qText = raw.toLowerCase();
      const qWwpn = normalizeWwpn(raw);
      let first = null;
      scope.querySelectorAll("td.cell-clamp").forEach((td) => {
        const text = td.textContent || "";
        const hit = fieldMatchesText(text, qText) || fieldMatchesWwpn(text, qWwpn);
        if (!hit) return;
        td.classList.add("is-expanded");
        td.setAttribute("aria-expanded", "true");
        td.title = "Click to collapse";
        if (!first) first = td;
      });
      if (first && typeof first.scrollIntoView === "function") {
        first.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    }
```

Update `runFcSearch`:

```javascript
    function runFcSearch() {
      const q = (searchInput.value || "").trim();
      if (!q) {
        collapseAllClampedCells();
        statusEl.textContent = "Search cleared.";
        return;
      }
      // ... existing match logic ...
      const finish = (list, serverMatches) => {
        // on miss paths: render then applyCellClamps only (stay collapsed)
        // on hit paths: after render(), call applyCellClamps(); expandClampedCellsMatching(q);
        ...
      };
    }
```

Concrete finish behavior:

1. Miss (no client, no server): `activeSiteId = ""`; `updateSiteOptions()`; `render()`; `applyCellClamps()`; miss status — stay collapsed.
2. Hit (client or server): set site; `render()`; `applyCellClamps()`; `expandClampedCellsMatching(q)`; found status.

Ensure every `render()` path used by Find already ends with or is followed by `applyCellClamps()` (from Task 1). Call `expandClampedCellsMatching(q)` only on successful hits.

- [ ] **Step 4: Run tests**

```powershell
python -m pytest tests/test_fc_wwpn_page.py tests/test_contingency_groups_page.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/fc_wwpn_report.py tests/test_fc_wwpn_page.py
git commit -m "Expand clamped FC cells on Find match; collapse all when cleared."
```

---

### Task 3: Version bump 1.6.56

**Files:**
- Modify: `launchpad/config.py`

- [ ] **Step 1: Bump**

Set `APP_VERSION = "1.6.56"`.

- [ ] **Step 2: Smoke**

```powershell
python -c "from launchpad.config import APP_VERSION; from launchpad.fc_wwpn_report import FC_WWPN_REPORT_HTML; assert APP_VERSION=='1.6.56'; assert 'cell-clamp' in FC_WWPN_REPORT_HTML; assert 'expandClampedCellsMatching' in FC_WWPN_REPORT_HTML; print('ok')"
python -m pytest tests/test_fc_wwpn_page.py -q
```

Expected: `ok` and PASS.

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version to 1.6.56 for FC WWPN multi-line cell clamp."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| One-line clamp for multi-line cells | 1 |
| Click toggle | 1 |
| Print full text | 1 |
| Find expands matching cells | 2 |
| Clear Find collapses all | 2 |
| Excel unchanged | (no code) |
| Version 1.6.56 | 3 |

## Self-review notes

- Remote WWPNs often use `;` without newlines — `cellNeedsClamp` must treat `;` as multi-line.
- Empty Find previously showed “Enter a WWPN…”; spec requires collapse-all — use `Search cleared.`
- Do not change `/api/fc-wwpn-find` match semantics.
