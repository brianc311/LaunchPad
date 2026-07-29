# Dark-Theme Report Link Contrast Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle bare content hyperlinks on dark HealthServer report pages to a readable light blue (`a:not(.btn)`), bump to **1.6.79**.

**Architecture:** Duplicate the same small CSS snippet into each dark report page’s `<style>` block (pages do not share a common CSS file today). Leave `.btn` / `.btn.secondary` unchanged.

**Tech Stack:** Python HTML string pages, pytest.

**Spec:** `docs/superpowers/specs/2026-07-29-dark-theme-link-contrast-design.md`

## Global Constraints

- **Worktree:** `.worktrees/dark-theme-link-contrast` on `feature/dark-theme-link-contrast` from `feature/contingency-groups` tip (include design `ce14391` or later)
- Selector exactly: `a:not(.btn)` with color `#9ec1ff`, hover `#c5d9ff`, underline + `text-underline-offset: 2px`
- Do not change `.btn` button colors or copy/URLs
- No Call Home fallback, firmware seed UX, or webpage catalog delete (B/C/D)
- Bump `APP_VERSION` to **1.6.79**
- Commit at each task’s commit step
- Run from: `cd C:\Users\BrianColley\LaunchPad\.worktrees\dark-theme-link-contrast`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/system_connectivity_page.py` | CSS + IBM matrix link readability |
| `launchpad/contingency_groups.py` | CSS + FlashCopy CGs lede links |
| `launchpad/fc_consistgrp.py` | Same CSS (consistency) |
| Other dark pages with same tokens (if present in worktree) | Same CSS snippet when they have a shared `<style>` block: `host_volume_health_page.py`, `volume_find_page.py`, `capacity_report.py`, `fc_wwpn_report.py`, `snapshot_schedule.py` — optional only if they already use the same token header; prefer updating all token-matched pages found by search |
| `launchpad/config.py` | `1.6.79` |
| Tests | Assert CSS on System Connectivity + Contingency Groups; version |

**CSS snippet (verbatim):**

```css
    a:not(.btn) {
      color: #9ec1ff;
      text-decoration: underline;
      text-underline-offset: 2px;
    }
    a:not(.btn):hover { color: #c5d9ff; }
```

---

### Task 0: Confirm baseline

**Files:** none

- [ ] **Step 1: Create worktree**

```powershell
cd C:\Users\BrianColley\LaunchPad
git worktree add .worktrees/dark-theme-link-contrast -b feature/dark-theme-link-contrast feature/contingency-groups
cd .worktrees\dark-theme-link-contrast
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-29-dark-theme-link-contrast-design.md
```

Expected: tip `1.6.78` (or later), spec `True`.

- [ ] **Step 2: No feature commit**

---

### Task 1: Failing tests for link CSS (TDD)

**Files:**
- Modify: `tests/test_system_connectivity_page.py`
- Create or modify: `tests/test_contingency_groups_page.py` (or existing contingency groups HTML test file — search for `CONTINGENCY` / `contingency_groups` tests first)

**Interfaces:**
- Consumes: `SYSTEM_CONNECTIVITY_HTML`; contingency groups HTML constant from `launchpad.contingency_groups`

- [ ] **Step 1: Write failing tests**

```python
def test_system_connectivity_styles_content_links_for_dark_theme():
    from launchpad.system_connectivity_page import SYSTEM_CONNECTIVITY_HTML

    html = SYSTEM_CONNECTIVITY_HTML
    assert "a:not(.btn)" in html
    assert "#9ec1ff" in html
    assert "#c5d9ff" in html
    assert 'href="https://www.ibm.com/support/pages/node/5692850"' in html


def test_contingency_groups_styles_content_links_for_dark_theme():
    # Import the HTML constant actually used by the Contingency Groups page
    # (name may be CONTINGENCY_GROUPS_HTML or similar — match existing tests).
    ...
    assert "a:not(.btn)" in html
    assert "#9ec1ff" in html
    assert 'href="/fc-consistgrp"' in html
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
python -m pytest tests/test_system_connectivity_page.py::test_system_connectivity_styles_content_links_for_dark_theme -v --tb=short
```

- [ ] **Step 3: Commit tests only**

```powershell
git add tests/test_system_connectivity_page.py tests/test_contingency_groups_page.py
git commit -m "Add failing tests for dark-theme content link contrast."
```

---

### Task 2: Add CSS to dark report pages

**Files:**
- Modify: `launchpad/system_connectivity_page.py`
- Modify: `launchpad/contingency_groups.py`
- Modify: `launchpad/fc_consistgrp.py`
- Modify (same snippet): other `launchpad/*` dark report pages that define `--bg: #0b0f14` in a page `<style>` block (exclude pure logic modules). Prefer consistency across token-matched HTML pages found via:

```powershell
rg -l "--bg: #0b0f14" launchpad --glob "*.py"
```

**Interfaces:**
- Produces: verbatim CSS snippet in each target `<style>` block

- [ ] **Step 1: Insert CSS** near other typography rules (after `.hint` / `a` / body rules). Do not alter `.btn` rules.

- [ ] **Step 2: Run tests — PASS**

```powershell
python -m pytest tests/test_system_connectivity_page.py tests/test_contingency_groups_page.py -q --tb=short
```

(If contingency test file name differs, use the file you created/updated in Task 1.)

- [ ] **Step 3: Commit**

```powershell
git add launchpad/system_connectivity_page.py launchpad/contingency_groups.py launchpad/fc_consistgrp.py
# plus any other dark pages updated
git commit -m "Restyle dark-theme content links for readable contrast."
```

---

### Task 3: Version bump to 1.6.79

**Files:**
- Modify: `launchpad/config.py`
- Modify: `tests/test_system_connectivity_version.py`

- [ ] **Step 1: Assert `APP_VERSION == "1.6.79"` (RED)** then set `APP_VERSION = "1.6.79"` (GREEN)

- [ ] **Step 2: Run**

```powershell
python -m pytest tests/test_system_connectivity_version.py tests/test_system_connectivity_page.py -q --tb=short
```

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py tests/test_system_connectivity_version.py
git commit -m "Bump LaunchPad to 1.6.79 for dark-theme link contrast."
```

---

### Task 4: Final verification

- [ ] **Step 1:**

```powershell
python -m pytest tests/test_system_connectivity_page.py tests/test_system_connectivity_version.py tests/test_contingency_groups_page.py -q --tb=short
rg -n "a:not\(\.btn\)" launchpad --glob "*.py"
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
```

Expected: tests PASS; CSS present on System Connectivity + Contingency Groups (+ others updated); `1.6.79`.

- [ ] **Step 2: No commit unless fixes**

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| `a:not(.btn)` colors | 2 |
| System Connectivity IBM link page | 1–2 |
| Contingency / FlashCopy lede links | 1–2 |
| `.btn` unchanged | 2 |
| Version 1.6.79 | 3 |
| No B/C/D scope | Global |
